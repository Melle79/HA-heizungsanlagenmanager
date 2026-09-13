"""Heizungsanlagenmanager – Dienst, Abfragetakt und REST-Schnittstelle.

Der Manager liest in einem eigenen Faden die ausgewählten Parameter aus der
Heizungsregelung und spiegelt sie nach MQTT. Die Oberfläche sieht denselben
Zustand, den auch Home Assistant bekommt; es gibt keine zweite Wahrheit.
"""
from __future__ import annotations

import ipaddress
import json
import logging
import os
import re
import threading
import time
import urllib.request
from datetime import datetime

from flask import Flask, jsonify, request, send_from_directory

import bsb as bsb_modul
import katalog as katalog_modul
import store
from version import VERSION

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
_LOGGER = logging.getLogger("heizungsanlage")

FRONTEND = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "frontend")

app = Flask(__name__, static_folder=None)

_takt_lock = threading.Lock()
_wecker = threading.Event()
_poll_wecker = threading.Event()
_erreichbar_seit = 0.0
_publisher = None
_letzter_fehler = ""
# Der Katalogaufbau dauert Minuten. Damit die Oberfläche nicht ins Leere
# wartet, läuft er in einem eigenen Faden und meldet hierhin seinen Stand.
_katalog_lauf = {"laeuft": False, "schritt": 0, "gesamt": 0, "name": "",
                 "fehler": ""}


def _client() -> bsb_modul.Bsb:
    e = store.load_config()["einstellungen"]
    return bsb_modul.Bsb(e["bsb_url"], e["passkey"])


def _zeitzone_uebernehmen() -> None:
    """Die Zeitzone von Home Assistant übernehmen – sonst rechnet der
    Container in UTC, und jeder Zeitstempel liegt zwei Stunden daneben."""
    try:
        req = urllib.request.Request(
            "http://supervisor/core/api/config",
            headers={"Authorization": f"Bearer {os.environ.get('SUPERVISOR_TOKEN', '')}"})
        with urllib.request.urlopen(req, timeout=10) as antwort:
            zone = json.loads(antwort.read().decode("utf-8")).get("time_zone")
        if zone:
            os.environ["TZ"] = zone
            time.tzset()
            _LOGGER.info("Zeitzone: %s", zone)
    except Exception as err:  # noqa: BLE001
        _LOGGER.warning("Zeitzone nicht übernommen: %s", err)


# ----------------------------------------------------------------- Takt ----

# So viele Parameter liest der Manager auf Zuruf höchstens. Die Grenze ist
# keine Willkür: 40 Parameter sind gut 20 Sekunden Busverkehr, und länger
# soll niemand auf eine Oberfläche warten – die Heizung erst recht nicht.
MAX_AUF_ZURUF = 40


def _lesen(auswahl=None, nummern=None) -> dict:
    """Parameter lesen und – sofern ausgewählt – nach MQTT spiegeln.

    Ohne ``nummern`` sind die ausgewählten Parameter gemeint, also der
    Regeltakt. Mit ``nummern`` liest der Manager auf Zuruf, etwa für die
    Steuerung: Dort stehen Parameter, die niemand dauerhaft überwachen will,
    deren aktueller Wert aber sichtbar sein muss, bevor man ihn ändert.

    Gelesene Werte landen in beiden Fällen im Zustand. Nach MQTT geht nur die
    Auswahl – ein auf Zuruf gelesener Parameter soll keine Entität anlegen,
    die beim nächsten Blick schon wieder veraltet ist.
    """
    global _letzter_fehler
    with _takt_lock:
        config = store.load_config()
        auswahl = auswahl if auswahl is not None else config["auswahl"]
        state = store.load_state()
        if nummern is not None:
            zu_lesen = [str(n) for n in nummern][:MAX_AUF_ZURUF]
        else:
            zu_lesen = [e["nr"] for e in auswahl]
        if not zu_lesen:
            return {"werte": {}, "hinweis": "Noch nichts ausgewählt"}

        try:
            roh = _client().werte(zu_lesen)
            _letzter_fehler = ""
        except bsb_modul.BsbFehler as err:
            _letzter_fehler = str(err)
            _LOGGER.warning("Lesen fehlgeschlagen: %s", err)
            return {"werte": state["werte"], "fehler": str(err)}

        jetzt = datetime.now().isoformat(timespec="seconds")
        for nr, eintrag in roh.items():
            state["werte"][str(nr)] = {
                "value": eintrag.get("value"),
                "desc": eintrag.get("desc") or "",
                "unit": eintrag.get("unit") or "",
                "name": eintrag.get("name") or "",
                "error": eintrag.get("error"),
                "zeit": jetzt,
            }
        if nummern is None:
            state["letzter_lauf"] = jetzt
        gelesen = len(roh)
        # Ebenso hier: nur die Felder, die dieser Weg verantwortet.
        store.merke_state(werte=state["werte"],
                          letzter_lauf=state["letzter_lauf"])

    # Auf Zuruf gelesene Werte gehen nicht nach MQTT – nur die Auswahl. Und
    # gar nichts, wenn BSB-LAN das Melden übernommen hat.
    if (nummern is None and _publisher is not None
            and config["einstellungen"].get("melder") != "bsblan"):
        try:
            _publisher.werte(auswahl, state["werte"])
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("MQTT-Meldung fehlgeschlagen: %s", err)
    # ``gelesen`` ist, was diesmal über den Bus kam – ``werte`` enthält auch
    # alles früher Gelesene. Die beiden zu verwechseln ließ das Protokoll
    # „126 Werte gelesen“ melden, wo dreizehn abgefragt wurden.
    return {"werte": state["werte"], "letzter_lauf": state["letzter_lauf"],
            "gelesen": gelesen}


# Frederik Holst, der BSB-LAN gebaut hat, rät vom festen Sendeintervall ab:
# Jede Busabfrage dauert ein bis zwei Sekunden, vierzig Parameter im
# Minutentakt belegen den Bus vollständig. Sein Weg – in einem Video über
# Home-Assistant-Automationen gezeigt – ist, jeden Parameter so oft abzufragen,
# wie er es verdient. BSB-LAN hört dafür auf ``<praefix>/poll``. Das Add-on
# nimmt dem Nutzer die Automationen ab und schickt die Aufforderung selbst.
POLL_TAKT_S = 15


def _erreichbarkeit_pruefen() -> None:
    """Antwortet BSB-LAN? – und die Antwort nach Home Assistant melden.

    ``/JI`` fragt nur das Gerät selbst, nicht den Bus: Es kostet die Heizung
    nichts, darf also jede Minute laufen. Gemeldet wird nur, was sich ändert,
    plus einmal je Viertelstunde, damit die Entität nicht als vergessen
    dasteht.
    """
    global _erreichbar_seit
    try:
        info = _client().info()
        jetzt_erreichbar = True
    except bsb_modul.BsbFehler:
        info, jetzt_erreichbar = {}, False

    state = store.load_state()
    vorher = state.get("erreichbar")
    if jetzt_erreichbar != vorher:
        _LOGGER.info("BSB-LAN ist %s", "wieder da" if jetzt_erreichbar else "weg")
    felder = {"erreichbar": jetzt_erreichbar}
    if info:
        felder["info"] = info
    store.merke_state(**felder)

    if _publisher is not None and _publisher.connected.is_set():
        if jetzt_erreichbar != vorher or time.time() - _erreichbar_seit > 900:
            _erreichbar_seit = time.time()
            _publisher.erreichbarkeit_anmelden(info or state.get("info") or {})
            _publisher.erreichbarkeit(jetzt_erreichbar)


def _poll_schleife() -> None:
    faellig = {}
    naechste_pruefung = 0.0
    while True:
        _poll_wecker.wait(timeout=POLL_TAKT_S)
        _poll_wecker.clear()
        try:
            if time.time() >= naechste_pruefung:
                naechste_pruefung = time.time() + 60
                _erreichbarkeit_pruefen()
            config = store.load_config()
            e = config["einstellungen"]
            if e.get("melder") != "bsblan" or _publisher is None:
                faellig.clear()
                continue
            jetzt = time.time()
            dran = []
            eigene = set()
            for eintrag in config["auswahl"]:
                takt = int(eintrag.get("takt_s") or 0)
                if not takt:
                    continue
                nr = str(eintrag["nr"])
                eigene.add(nr)
                if jetzt - faellig.get(nr, 0) >= takt:
                    faellig[nr] = jetzt
                    dran.append(nr)
            # Was nicht mehr ausgewählt ist, muss auch nicht gemerkt werden.
            for nr in list(faellig):
                if nr not in eigene:
                    faellig.pop(nr, None)
            if dran:
                _publisher.abfragen(e.get("bsblan_praefix") or "", dran)
                _LOGGER.info("Abfrage an BSB-LAN: %s", ", ".join(dran))
        except Exception as err:  # noqa: BLE001
            _LOGGER.exception("Abfragetakt fehlgeschlagen: %s", err)


def _horchen_stellen() -> None:
    """Auf das Zustandsthema von BSB-LAN hören – nur wenn es auch melden soll."""
    if _publisher is None:
        return
    e = store.load_config()["einstellungen"]
    praefix = str(e.get("bsblan_praefix") or "").strip("/")
    _publisher.horchen(f"{praefix}/status"
                       if e.get("melder") == "bsblan" and praefix else "")


def bsblan_meldet() -> bool | None:
    """Sagt BSB-LAN dem Broker, dass es da ist?

    ``None`` heißt: Wir wissen es nicht – kein MQTT, ein anderer Melder, oder
    noch nichts gehört. ``False`` ist die Auskunft, auf die es ankommt: Das
    Gerät antwortet auf HTTP, hat den MQTT-Teil aber nicht laufen.
    """
    if _publisher is None or not _publisher.connected.is_set():
        return None
    stand = _publisher.fremd_stand
    if not stand.get("topic") or not stand.get("wert"):
        return None
    return stand["wert"].lower() == "online"


def _takt_schleife() -> None:
    while True:
        try:
            ergebnis = _lesen()
            anzahl = int(ergebnis.get("gelesen") or 0)
            if ergebnis.get("fehler"):
                _LOGGER.warning("Takt mit Fehler: %s", ergebnis["fehler"])
            elif anzahl:
                _LOGGER.info("Takt: %d Werte gelesen", anzahl)
        except Exception as err:  # noqa: BLE001
            _LOGGER.exception("Takt fehlgeschlagen: %s", err)
        pause = int(store.load_config()["einstellungen"]["intervall_s"])
        _wecker.wait(timeout=pause)
        _wecker.clear()


def _sofort_lesen() -> None:
    _wecker.set()


# ---------------------------------------------------------------- MQTT ----

def _mqtt_starten() -> None:
    global _publisher
    host = os.environ.get("MQTT_HOST")
    if not host:
        _LOGGER.warning("Kein MQTT – es entstehen keine Entitäten")
        return
    import mqtt_publisher
    e = store.load_config()["einstellungen"]
    _publisher = mqtt_publisher.Publisher(
        host, os.environ.get("MQTT_PORT", 1883), os.environ.get("MQTT_USER"),
        os.environ.get("MQTT_PASSWORD"), e["praefix"])
    _publisher.on_ready = _discovery_auffrischen
    _publisher.start()
    _horchen_stellen()


def _discovery_auffrischen() -> None:
    """Entitäten anmelden – und die abgewählter Parameter wieder abräumen."""
    if _publisher is None or not _publisher.connected.is_set():
        return
    # Erst hier importiert, wie oben auch: Ohne Broker soll die Oberfläche
    # auch ohne paho-mqtt laufen.
    import mqtt_publisher
    try:
        config = store.load_config()
        state = store.load_state()
        katalog = store.load_katalog()

        # Diese eine Entität bleibt in jeder Betriebsart: Sie sagt nichts über
        # die Heizung, sondern über die Verbindung zu ihr.
        _publisher.erreichbarkeit_anmelden(state.get("info") or {})
        _publisher.erreichbarkeit(bool(state.get("erreichbar")))

        # Meldet BSB-LAN selbst, hält der Manager sich heraus – und räumt ab,
        # was er früher angemeldet hat. Zwei Absender für dieselbe Anlage
        # sind keine Redundanz, sondern zwei Wahrheiten in einem Diagramm.
        if config["einstellungen"].get("melder") == "bsblan":
            alt = state.get("veroeffentlicht") or []
            if alt:
                _publisher.altes_geraet_abraeumen(
                    state.get("geraet") or mqtt_publisher.DEVICE_ID,
                    state.get("praefix") or _publisher.praefix, alt)
            store.merke_state(veroeffentlicht=[],
                              geraet=mqtt_publisher.DEVICE_ID,
                              praefix=_publisher.praefix)
            _LOGGER.info("BSB-LAN meldet selbst – der Manager hält sich heraus")
            return
        # Kategorienamen mitgeben, damit sie als Attribut erscheinen.
        auswahl = []
        for eintrag in config["auswahl"]:
            angereichert = dict(eintrag)
            aus_katalog = (katalog.get("parameter") or {}).get(eintrag["nr"]) or {}
            angereichert["kategorie_name"] = aus_katalog.get("kategorie_name", "")
            auswahl.append(angereichert)
        # Wurde die Kennung geändert, gehören die Anmeldungen der alten
        # zurückgenommen – sonst steht in Home Assistant für immer ein zweites,
        # totes Gerät. Das passiert einmal, beim ersten Start danach.
        # Fehlt der Merker, stammt der Zustand aus einer Fassung vor 1.5.0 –
        # und die hießen ausnahmslos „kesselmanager“. Nur wenn damals etwas
        # angemeldet wurde, gibt es auch etwas abzuräumen.
        altes_geraet = state.get("geraet") or (
            store.ALTE_KENNUNG if state.get("veroeffentlicht") else "")
        if altes_geraet and altes_geraet != mqtt_publisher.DEVICE_ID:
            _publisher.altes_geraet_abraeumen(
                altes_geraet, state.get("praefix") or altes_geraet,
                state.get("veroeffentlicht") or [])
            state["veroeffentlicht"] = []

        aktuell = _publisher.discovery(auswahl, katalog,
                                       state.get("veroeffentlicht") or [])
        # Nur diese drei Felder fortschreiben. Der Takt hält zur selben Zeit
        # seine eigene Kopie des Zustands; wer die ganze Datei schreibt,
        # macht die Änderung des anderen zunichte.
        store.merke_state(veroeffentlicht=aktuell,
                          geraet=mqtt_publisher.DEVICE_ID,
                          praefix=_publisher.praefix)
        _publisher.werte(auswahl, state.get("werte") or {})
        _LOGGER.info("Discovery veröffentlicht (%d Parameter)", len(aktuell))
    except Exception as err:  # noqa: BLE001
        _LOGGER.warning("Discovery fehlgeschlagen: %s", err)


# ----------------------------------------------------------- Oberfläche ----

@app.route("/")
def index():
    return send_from_directory(FRONTEND, "index.html")


@app.route("/<path:datei>")
def statisch(datei: str):
    if datei.startswith("api/"):
        return jsonify({"fehler": "unbekannter Aufruf"}), 404
    return send_from_directory(FRONTEND, datei)


@app.route("/api/sprache")
def api_sprache():
    """Welche Sprache führt Home Assistant?

    Ein eigener, winziger Endpunkt statt eines Feldes im Status: Die
    Übersetzung soll stehen, bevor die ersten Daten eintreffen – sonst blitzt
    die deutsche Fassung kurz auf.

    Deutsch ist die Quelle. Wer eine andere Sprache eingestellt hat, bekommt
    die passende Datei, und wenn es keine gibt, Englisch; fehlt auch das,
    bleibt es bei Deutsch. Eine halbe Übersetzung ist besser als eine leere
    Oberfläche.
    """
    return jsonify({"sprache": _ha_sprache()})


def _supervisor(pfad: str):
    """Etwas beim Supervisor nachfragen. Gibt None, wenn es nicht geht."""
    token = os.environ.get("SUPERVISOR_TOKEN")
    if not token:
        return None
    try:
        req = urllib.request.Request(
            f"http://supervisor/{pfad.lstrip('/')}",
            headers={"Authorization": f"Bearer {token}"})
        with urllib.request.urlopen(req, timeout=8) as antwort:
            return json.load(antwort)
    except Exception as err:                      # noqa: BLE001
        _LOGGER.info("Supervisor (%s) antwortet nicht: %s", pfad, err)
        return None


def _ist_adresse(text: str) -> bool:
    """Eine IP-Adresse, die auch ein Gerät im Hausnetz anwählen kann."""
    try:
        ipaddress.ip_address(str(text).strip())
        return True
    except ValueError:
        return False


def broker_fuer_bsblan() -> str:
    """Die Broker-Adresse, unter der **BSB-LAN** ihn erreicht.

    Der Supervisor nennt dem Add-on ``core-mosquitto`` – das ist ein Name aus
    dem Docker-Netz von Home Assistant. Für das Add-on stimmt er, für einen
    ESP32 im Hausnetz ist er nicht auflösbar: Der Adapter versucht dann alle
    zehn Sekunden eine Verbindung, die es nicht geben kann, und meldet nichts
    mehr. Also fragen wir den Supervisor nach der Adresse des Rechners, auf
    dem Home Assistant läuft.

    Kommt dabei nichts Brauchbares heraus, ist die richtige Antwort **kein
    Wert**: Dann bleibt stehen, was in BSB-LAN steht. Eine unerreichbare
    Adresse hineinzuschreiben ist schlimmer, als nichts zu tun.
    """
    host = str(os.environ.get("MQTT_HOST") or "").strip()
    port = os.environ.get("MQTT_PORT", 1883)
    if _ist_adresse(host):
        return f"{host}:{port}"

    netz = _supervisor("network/info") or {}
    for schnittstelle in (netz.get("data") or netz).get("interfaces") or []:
        if not schnittstelle.get("enabled"):
            continue
        adresse = ((schnittstelle.get("ipv4") or {}).get("address") or [None])[0]
        adresse = str(adresse or "").split("/")[0]
        if _ist_adresse(adresse):
            if schnittstelle.get("primary"):
                return f"{adresse}:{port}"
    # Keine als primär markiert? Dann die erste brauchbare.
    for schnittstelle in (netz.get("data") or netz).get("interfaces") or []:
        adresse = ((schnittstelle.get("ipv4") or {}).get("address") or [None])[0]
        adresse = str(adresse or "").split("/")[0]
        if _ist_adresse(adresse):
            return f"{adresse}:{port}"
    return ""


# BSB-LAN prüft selbst gegen bsb-lan.de/bsb-version.h, wenn man es einschaltet.
# Dieselbe Quelle, damit hier nichts anderes herauskommt als dort.
VERSIONSQUELLE = "http://bsb-lan.de/bsb-version.h"
_neueste = {"stand": 0.0, "version": ""}


def bsblan_neueste() -> str:
    """Die neueste veröffentlichte BSB-LAN-Fassung, höchstens täglich geholt."""
    if _neueste["version"] and time.time() - _neueste["stand"] < 86400:
        return _neueste["version"]
    try:
        with urllib.request.urlopen(VERSIONSQUELLE, timeout=8) as antwort:
            text = antwort.read().decode("utf-8", "replace")
    except Exception as err:                      # noqa: BLE001
        _LOGGER.info("Fassung von bsb-lan.de nicht abrufbar: %s", err)
        _neueste["stand"] = time.time()           # nicht im Minutentakt nerven
        return _neueste["version"]
    teile = []
    for name in ("MAJOR", "MINOR", "PATCH"):
        treffer = re.search(rf'#define\s+{name}\s+"([^"]+)"', text)
        if not treffer:
            return _neueste["version"]
        teile.append(treffer.group(1))
    _neueste.update({"stand": time.time(), "version": ".".join(teile)})
    return _neueste["version"]


def _aelter(hier: str, dort: str) -> bool:
    """Ist die geflashte Fassung älter als die veröffentlichte?"""
    def zahlen(text):
        return [int(t) for t in re.findall(r"\d+", str(text).split("-")[0])][:3]
    a, b = zahlen(hier), zahlen(dort)
    return bool(a and b and a < b)


def _ha_sprache() -> str:
    """Die Spracheinstellung von Home Assistant, oder Deutsch."""
    token = os.environ.get("SUPERVISOR_TOKEN")
    if not token:
        return "de"
    try:
        req = urllib.request.Request(
            "http://supervisor/core/api/config",
            headers={"Authorization": f"Bearer {token}"})
        with urllib.request.urlopen(req, timeout=8) as antwort:
            config = json.load(antwort)
    except Exception as err:                      # noqa: BLE001
        _LOGGER.info("Sprache nicht abfragbar: %s", err)
        return "de"
    # „de-DE“ und „de“ sind dieselbe Sprache – der Landesteil interessiert hier
    # nicht, es gibt keine Datei je Region.
    return str(config.get("language") or "de").split("-")[0].lower()


@app.route("/api/status")
def api_status():
    config = store.load_config()
    state = store.load_state()
    katalog = store.load_katalog()
    antwort = {
        "version": VERSION,
        "letzter_lauf": state.get("letzter_lauf"),
        "ausgewaehlt": len(config["auswahl"]),
        "katalog_parameter": len(katalog.get("parameter") or {}),
        "katalog_gebaut_am": katalog.get("gebaut_am"),
        "katalog_lauf": dict(_katalog_lauf),
        "fehler": _letzter_fehler,
        "mqtt": _publisher is not None and _publisher.connected.is_set(),
        "schreiben_erlaubt": config["einstellungen"]["schreiben_erlaubt"],
    }
    # Fährt beim Statusabruf mit, damit die Oberfläche mitbekommt, wenn ein
    # anderes Add-on etwas übernimmt – ohne dafür eigens zu fragen.
    uebernahme = store.load_uebernahme()
    antwort["uebernahme_quellen"] = uebernahme
    antwort["uebernahme"] = store.uebernommen_von(uebernahme)
    try:
        info = _client().info()
        antwort["verbunden"] = True
        neueste = bsblan_neueste()
        antwort["bsblan_meldet"] = bsblan_meldet()
        antwort["bsb"] = {
            "version": info.get("version"), "bus": info.get("bus"),
            "neueste": neueste,
            "veraltet": _aelter(info.get("version") or "", neueste),
            "busaddr": info.get("busaddr"), "busdest": info.get("busdest"),
            "buswritable": bool(info.get("buswritable")),
            "geraete": info.get("busdevices") or [],
        }
    except bsb_modul.BsbFehler as err:
        antwort["verbunden"] = False
        antwort["bsb_fehler"] = str(err)
    return jsonify(antwort)


@app.route("/api/einstellungen", methods=["GET", "PUT"])
def api_einstellungen():
    config = store.load_config()
    if request.method == "GET":
        return jsonify(config["einstellungen"])
    try:
        neu = store.validate_einstellungen(request.get_json(force=True) or {})
    except store.ValidationError as err:
        return jsonify({"fehler": str(err)}), 400
    config["einstellungen"] = neu
    store.save_config(config)
    # Wer hier umschaltet, wer melden soll, erwartet es sofort: Beim Wechsel
    # auf BSB-LAN werden die eigenen Entitäten abgeräumt, beim Wechsel zurück
    # wieder angemeldet. Ohne das bliebe der alte Zustand bis zum nächsten
    # Verbindungsaufbau stehen – und in Home Assistant stünde beides.
    _discovery_auffrischen()
    _horchen_stellen()

    # Speichern heißt speichern, wo es wirkt. Meldet BSB-LAN, gehen Präfix,
    # Geräte-ID, Intervall, Einheiten und MQTT-Art gleich ins Gerät – sonst
    # stünde hier das neue Präfix und BSB-LAN meldete weiter unter dem alten.
    # Genauso hält es die Auswahl weiter unten.
    antwort = dict(neu)
    if neu.get("melder") == "bsblan":
        try:
            antwort["bsblan"] = _bsblan_einrichten()
        except bsb_modul.BsbFehler as err:
            _LOGGER.warning("BSB-LAN nicht eingerichtet: %s", err)
            antwort["bsblan"] = {"fehler": str(err)}

    _sofort_lesen()
    return jsonify(antwort)


# ------------------------------------------------------------- Übernahme ----
#
# Die Schnittstelle für andere Add-ons – gedacht für den Heizungsplaner, offen
# für jedes andere. Wer hier etwas einträgt, sagt: „Diese Parameter führe ich,
# stellt sie nicht von Hand.“ Mehr passiert nicht: Gelesen wird weiter alles,
# und die Oberfläche bleibt vollständig bedienbar.

@app.route("/api/uebernahme", methods=["GET"])
def api_uebernahme():
    uebernahme = store.load_uebernahme()
    return jsonify({"quellen": uebernahme,
                    "parameter": store.uebernommen_von(uebernahme)})


@app.route("/api/uebernahme", methods=["PUT", "POST"])
def api_uebernahme_setzen():
    """Eine Quelle meldet an, welche Parameter sie führt.

    Eine leere Liste ist die Abmeldung – so braucht ein Add-on beim Aufräumen
    keinen zweiten Aufruf zu kennen.
    """
    try:
        quelle, eintrag = store.validate_uebernahme(
            request.get_json(force=True) or {})
    except store.ValidationError as err:
        return jsonify({"fehler": str(err)}), 400

    uebernahme = store.load_uebernahme()
    if eintrag["parameter"]:
        eintrag["zeit"] = eintrag["zeit"] or datetime.now().isoformat(
            timespec="seconds")
        uebernahme[quelle] = eintrag
        _LOGGER.info("%s führt jetzt %d Parameter", eintrag["name"],
                     len(eintrag["parameter"]))
    else:
        uebernahme.pop(quelle, None)
        _LOGGER.info("Übernahme durch %s aufgehoben", quelle)
    store.save_uebernahme(uebernahme)
    return jsonify({"quellen": uebernahme,
                    "parameter": store.uebernommen_von(uebernahme)})


@app.route("/api/uebernahme/<quelle>", methods=["DELETE"])
def api_uebernahme_loesen(quelle):
    """Die Übernahme aufheben – der Knopf in der Oberfläche.

    Damit bleibt das Add-on eigenständig: Was ein anderes Programm hält, kann
    der Mensch davor jederzeit wieder an sich nehmen.
    """
    uebernahme = store.load_uebernahme()
    weg = uebernahme.pop(str(quelle), None)
    store.save_uebernahme(uebernahme)
    if weg:
        _LOGGER.info("Übernahme durch %s von Hand aufgehoben", quelle)
    return jsonify({"quellen": uebernahme,
                    "parameter": store.uebernommen_von(uebernahme)})


# ------------------------------------------------- BSB-LAN meldet selbst ----
#
# BSB-LAN bringt eigenes MQTT mit, samt Auto-Discovery für Home Assistant. Wo
# das eingeschaltet ist, melden **zwei** Programme dieselbe Anlage – doppelte
# Entitäten, doppelte Last auf einem Bus mit 4800 Baud. Der Manager kann das
# nicht stillschweigend ändern; er kann es sichtbar machen.

# Die Einträge aus /JL, auf die es ankommt. Der Schlüssel ist die Option-
# nummer, die BSB-LAN selbst vergibt – der Index davor ist nicht stabil.
BSBLAN_OPTIONEN = {
    53: "logmodus",       # nicht 11 – das sind die Bustelegramme
    13: "logintervall", 14: "logparameter",
    36: "mqtt_broker", 37: "mqtt_user", 38: "mqtt_passwort",
    39: "mqtt_praefix", 40: "mqtt_geraete_id",
    35: "mqtt_art", 58: "mqtt_einheiten", 59: "mqtt_discovery",
}
# Jeder Name, den das Einrichten setzen will, muss hier oben vorkommen – sonst
# wird er stillschweigend übersprungen. Zweimal ist mir genau das passiert:
# erst bei den Zugangsdaten, dann bei den Einheiten. Eine Prüfung wacht
# seitdem darüber.
BSBLAN_SOLL_NAMEN = ("mqtt_broker", "mqtt_user", "mqtt_passwort", "mqtt_praefix",
                     "mqtt_geraete_id", "mqtt_art", "mqtt_einheiten",
                     "mqtt_discovery", "logintervall", "logmodus")
# Was aus dieser Liste die Oberfläche nie zu sehen bekommt. Die Zugangsdaten
# müssen durchgereicht werden, damit BSB-LAN den Broker erreicht – gezeigt
# oder zurückgemeldet werden sie nicht.
BSBLAN_GEHEIM = ("mqtt_user", "mqtt_passwort")
# Der Log-Modus ist ein Bitfeld, in der Reihenfolge der Häkchen auf der
# Einstellungsseite: 1 = auf SD-Karte schreiben, 2 = 24-Stunden-Mittel,
# 4 = an MQTT-Broker senden, 8 = nur die Log-Parameter, 16 = UDP. Svens 12
# heißt also: senden, und zwar nur die Log-Parameter.
LOGMODUS_MQTT = 4


# Die Werte, die BSB-LAN für seine Auswahllisten erwartet. Sie stehen so in
# der Weboberfläche des Geräts; hier übersetzt, damit in den Einstellungen
# Wörter stehen und keine Zahlen.
BSBLAN_ART = {"einfach": "1", "json": "2", "rich": "3"}
BSBLAN_EINHEITEN = {"landes": "0", "ha": "1", "keine": "2"}
LOGMODUS_NUR_LOG = 8


def _bsblan_lesen() -> tuple:
    """Die Einstellungen von BSB-LAN – roh und nach Namen sortiert."""
    roh = _client().konfiguration()
    nach_name = {}
    for schluessel, eintrag in roh.items():
        if not isinstance(eintrag, dict):
            continue
        name = BSBLAN_OPTIONEN.get(eintrag.get("parameter"))
        if name:
            nach_name[name] = {"schluessel": schluessel, "eintrag": eintrag,
                               "wert": eintrag.get("value")}
    return roh, nach_name


@app.route("/api/bsblan")
def api_bsblan():
    """Was BSB-LAN von sich aus nach Home Assistant meldet.

    Zugangsdaten kommen hier nicht vor: Benutzername und Passwort des Brokers
    stehen in derselben Datei, gehen diese Oberfläche aber nichts an.
    """
    try:
        roh = _bsblan_lesen()
    except bsb_modul.BsbFehler as err:
        return jsonify({"lesbar": False, "fehler": str(err)})

    gefunden = {name: teil["wert"] for name, teil in roh[1].items()}
    roh = roh[0]

    try:
        modus = int(gefunden.get("logmodus") or 0)
    except (TypeError, ValueError):
        modus = 0
    liste = [t.strip() for t in str(gefunden.get("logparameter") or "").split(",")
             if t.strip()]
    return jsonify({
        "lesbar": True,
        "sendet": bool(modus & LOGMODUS_MQTT),
        "parameter": liste,
        "anzahl": len(liste),
        "intervall_s": gefunden.get("logintervall"),
        "broker": gefunden.get("mqtt_broker"),
        "praefix": gefunden.get("mqtt_praefix"),
        "discovery": str(gefunden.get("mqtt_discovery")) == "1",
        "nur_logparameter": bool(modus & LOGMODUS_NUR_LOG),
        "art": str(gefunden.get("mqtt_art") or ""),
        "einheiten_ha": str(gefunden.get("mqtt_einheiten") or "") == "1",
    })


def _bsblan_einrichten() -> dict:
    """BSB-LAN so einstellen, dass es selbst nach Home Assistant meldet.

    Broker, Benutzer und Passwort kommen vom Supervisor – dieselben, mit denen
    das Add-on selbst am Broker hängt. Sie werden hier durchgereicht und
    **nirgends angezeigt oder gespeichert**; wer das Passwort seines Brokers
    nicht abtippen will, muss es auch nicht.

    Geschrieben wird nur, was sich unterscheidet, und danach wird
    zurückgelesen: Was das Gerät hinterher sagt, ist die Wahrheit, nicht was
    wir ihm geschickt haben.
    """
    e = store.load_config()["einstellungen"]
    if not os.environ.get("MQTT_HOST"):
        raise bsb_modul.BsbFehler("Home Assistant hat keinen MQTT-Broker – "
                                  "ohne den kann BSB-LAN nirgendwohin melden")
    broker = broker_fuer_bsblan()

    roh, nach_name = _bsblan_lesen()

    try:
        modus = int(nach_name.get("logmodus", {}).get("wert") or 0)
    except (TypeError, ValueError):
        modus = 0

    soll = {
        "mqtt_broker": broker,
        "mqtt_user": os.environ.get("MQTT_USER") or "",
        "mqtt_passwort": os.environ.get("MQTT_PASSWORD") or "",
        "mqtt_praefix": e["bsblan_praefix"],
        "mqtt_geraete_id": e["bsblan_geraete_id"],
        "mqtt_art": BSBLAN_ART[e["bsblan_art"]],
        "mqtt_einheiten": BSBLAN_EINHEITEN[e["bsblan_einheiten"]],
        "mqtt_discovery": "1",
        "logintervall": str(e["bsblan_intervall_s"]),
        # Senden, und nur die Log-Parameter – alles andere am Modus bleibt,
        # wie es war. Wer auf SD-Karte schreibt, soll das weiter tun.
        "logmodus": str(modus | LOGMODUS_MQTT | LOGMODUS_NUR_LOG),
    }

    # Ohne erreichbare Adresse gehören Broker und Zugangsdaten nicht ins Gerät:
    # Sie würden eine laufende Verbindung gegen eine unmögliche eintauschen.
    if not broker:
        for name in ("mqtt_broker", "mqtt_user", "mqtt_passwort"):
            soll.pop(name, None)
        _LOGGER.warning("Keine von außen erreichbare Broker-Adresse gefunden – "
                        "Broker und Zugangsdaten in BSB-LAN bleiben, wie sie sind")

    aenderungen, geschrieben = {}, []
    for name, wert in soll.items():
        teil = nach_name.get(name)
        if teil is None:
            continue                      # kennt dieses BSB-LAN nicht
        if str(teil["wert"]) == str(wert):
            continue                      # steht schon so da
        aenderungen[teil["schluessel"]] = {**teil["eintrag"], "value": wert}
        geschrieben.append(name)

    if aenderungen:
        _client().konfiguration_schreiben(aenderungen)

    _, danach = _bsblan_lesen()
    # Passwörter tauchen in der Rückmeldung nicht auf.
    offen = [name for name in soll
             if name not in BSBLAN_GEHEIM
             and name in danach and str(danach[name]["wert"]) != str(soll[name])]
    geschrieben = [name for name in geschrieben if name not in BSBLAN_GEHEIM] + \
                  (["Zugangsdaten"] if any(n in BSBLAN_GEHEIM for n in geschrieben)
                   else [])
    _LOGGER.info("BSB-LAN eingerichtet: %s geschrieben, %s offen",
                 len(geschrieben), offen)
    antwort = {"geschrieben": geschrieben, "offen": offen}
    if not broker:
        antwort["hinweis"] = ("Die Adresse des Brokers ließ sich nicht "
                              "ermitteln – Broker und Zugangsdaten in BSB-LAN "
                              "blieben unangetastet.")
    return antwort


@app.route("/api/bsblan/einrichten", methods=["POST"])
def api_bsblan_einrichten():
    """Der Weg von außen – die Oberfläche geht ihn beim Speichern mit."""
    try:
        return jsonify(_bsblan_einrichten())
    except bsb_modul.BsbFehler as err:
        return jsonify({"fehler": str(err)}), 502


def _bsblan_parameter_schreiben() -> dict:
    """Die Auswahl als Log-Parameterliste an BSB-LAN geben.

    Das ist der Kern der Sache: Was hier angehakt ist, meldet BSB-LAN – ohne
    dass der Manager dieselben Werte ein zweites Mal über den Bus holt.

    Zurückgelesen wird immer: Was das Gerät hinterher führt, zählt, nicht was
    wir ihm geschickt haben. BSB-LAN kürzt lange Listen stillschweigend.
    """
    nummern = [str(e["nr"]) for e in store.load_config()["auswahl"]]
    client = _client()
    _, nach_name = _bsblan_lesen()
    teil = nach_name.get("logparameter")
    if teil is None:
        raise bsb_modul.BsbFehler("Dieses BSB-LAN kennt keine Log-Parameterliste")
    liste = ",".join(nummern)
    if str(teil["wert"]) != liste:
        # Erst abmelden, was jetzt noch drinsteht: BSB-LAN widerruft nur, was
        # es gerade führt. Wer die Liste zuerst ändert, lässt für jeden
        # entfernten Parameter eine Entität zurück, die niemand mehr abmeldet –
        # sie steht „retained“ im Broker und in Home Assistant für immer.
        vorher = [t.strip() for t in str(teil["wert"] or "").split(",") if t.strip()]
        entfallen = [nr for nr in vorher if nr not in nummern]
        if entfallen:
            _LOGGER.info("%d Parameter fallen weg – erst abmelden", len(entfallen))
            client.discovery(False)
        client.konfiguration_schreiben(
            {teil["schluessel"]: {**teil["eintrag"], "value": liste}})
        # ... und die neue Liste anmelden.
        client.discovery(True)
    _, danach = _bsblan_lesen()
    steht = [t.strip() for t in
             str(danach["logparameter"]["wert"] or "").split(",") if t.strip()]
    _LOGGER.info("BSB-LAN meldet jetzt %d von %d Parametern",
                 len(steht), len(nummern))
    return {"parameter": steht, "anzahl": len(steht),
            "vollstaendig": steht == nummern}


@app.route("/api/bsblan/neustart", methods=["POST"])
def api_bsblan_neustart():
    """Den Adapter neu starten – ``/N``, nicht ``/NE``.

    Der Unterschied ist ein Buchstabe und die halbe Konfiguration: ``/NE``
    löscht zusätzlich das EEPROM. Hier wird nur neu gestartet; alle
    Einstellungen bleiben stehen.
    """
    try:
        _client().neustart()
    except bsb_modul.BsbFehler as err:
        return jsonify({"fehler": str(err)}), 502
    return jsonify({"neustart": True})


@app.route("/api/bsblan/parameter", methods=["PUT"])
def api_bsblan_parameter():
    try:
        return jsonify(_bsblan_parameter_schreiben())
    except bsb_modul.BsbFehler as err:
        return jsonify({"fehler": str(err)}), 502


@app.route("/api/bsblan/uebernehmen", methods=["POST"])
def api_bsblan_uebernehmen():
    """Was BSB-LAN heute meldet, als Auswahl übernehmen.

    Der umgekehrte Weg – für alle, die ihre Liste dort über Jahre gepflegt
    haben und sie nicht noch einmal zusammenklicken wollen.
    """
    try:
        _, nach_name = _bsblan_lesen()
    except bsb_modul.BsbFehler as err:
        return jsonify({"fehler": str(err)}), 502
    nummern = [t.strip() for t in
               str(nach_name.get("logparameter", {}).get("wert") or "").split(",")
               if t.strip()]
    katalog = store.load_katalog()
    neu = []
    for nr in nummern:
        eintrag = (katalog.get("parameter") or {}).get(nr) or {}
        neu.append({"nr": nr, "name": eintrag.get("name") or f"Parameter {nr}",
                    "anzeige": "", "einheit": eintrag.get("unit") or "",
                    "device_class": eintrag.get("device_class") or "",
                    "state_class": eintrag.get("state_class") or ""})
    config = store.load_config()
    config["auswahl"] = store.validate_auswahl(neu)
    store.save_config(config)
    _discovery_auffrischen()
    return jsonify(config["auswahl"])


# --------------------------------------------------------------- Katalog ----

@app.route("/api/katalog")
def api_katalog():
    katalog = store.load_katalog()
    # Zeitprogramme und Übersichtskacheln werden hier abgeleitet und nicht
    # mitgespeichert: So bekommt auch ein Katalog, der unter einer älteren
    # Fassung entstanden ist, die Erkennung – ohne ihn über den Bus neu
    # einlesen zu müssen. Das Rechnen kostet nichts, es ist reines Sortieren.
    return jsonify({
        "gebaut_am": katalog.get("gebaut_am"),
        "geraete": katalog.get("geraete") or [],
        "kategorien": katalog.get("kategorien") or {},
        "zeitprogramme": katalog_modul.zeitprogramme(katalog),
        "gruppen": katalog_modul.gruppen(katalog),
        "programmwahl": katalog_modul.programmwahl(katalog),
        "trinkwasserwahl": katalog_modul.trinkwasserwahl(katalog),
        "kacheln": katalog_modul.kacheln(katalog),
        "anzahl": len(katalog.get("parameter") or {}),
    })


@app.route("/api/katalog/suche")
def api_katalog_suche():
    katalog = store.load_katalog()
    treffer = katalog_modul.suchen(
        katalog,
        request.args.get("q", ""),
        request.args.get("rw") == "1",
        request.args.get("kat", ""))
    grenze = int(request.args.get("max", 400))
    return jsonify({"anzahl": len(treffer), "parameter": treffer[:grenze]})


def _katalog_bauen() -> None:
    global _katalog_lauf
    try:
        def fortschritt(i, gesamt, name):
            _katalog_lauf.update({"schritt": i, "gesamt": gesamt, "name": name})

        katalog = katalog_modul.aufbauen(_client(), fortschritt)
        store.save_katalog(katalog)
        _katalog_lauf["fehler"] = ""
    except bsb_modul.BsbFehler as err:
        _katalog_lauf["fehler"] = str(err)
        _LOGGER.warning("Katalogaufbau fehlgeschlagen: %s", err)
    except Exception as err:  # noqa: BLE001
        _katalog_lauf["fehler"] = str(err)
        _LOGGER.exception("Katalogaufbau fehlgeschlagen")
    finally:
        _katalog_lauf["laeuft"] = False


@app.route("/api/katalog/aufbauen", methods=["POST"])
def api_katalog_aufbauen():
    """Den Katalog neu einlesen – dauert Minuten, läuft deshalb nebenher."""
    if _katalog_lauf["laeuft"]:
        return jsonify({"fehler": "Der Katalog wird gerade schon gelesen"}), 409
    _katalog_lauf.update({"laeuft": True, "schritt": 0, "gesamt": 0,
                          "name": "", "fehler": ""})
    threading.Thread(target=_katalog_bauen, daemon=True).start()
    return jsonify({"gestartet": True})


# --------------------------------------------------------------- Auswahl ----

@app.route("/api/auswahl", methods=["GET", "PUT"])
def api_auswahl():
    config = store.load_config()
    if request.method == "GET":
        # Aus dem Katalog dazugelegt statt mitgespeichert: Datentyp und
        # Schreibrecht ändern sich mit der Firmware, nicht mit der Auswahl.
        # Die Oberfläche braucht sie, um zu erklären, was ein leerer Wert
        # bedeutet – bei einem Fühler etwas anderes als bei einem Datum.
        katalog = store.load_katalog()
        angereichert = []
        for eintrag in config["auswahl"]:
            aus_katalog = (katalog.get("parameter") or {}).get(eintrag["nr"]) or {}
            angereichert.append({
                **eintrag,
                "dataType_name": aus_katalog.get("dataType_name", ""),
                "schreibbar": aus_katalog.get("schreibbar"),
            })
        return jsonify(angereichert)
    try:
        neu = store.validate_auswahl(request.get_json(force=True) or [])
    except store.ValidationError as err:
        return jsonify({"fehler": str(err)}), 400
    config["auswahl"] = neu
    store.save_config(config)
    _discovery_auffrischen()

    # Meldet BSB-LAN, wandert die Auswahl gleich dorthin: Sonst hakt jemand
    # etwas an und wundert sich, dass in Home Assistant nichts erscheint.
    if config["einstellungen"].get("melder") == "bsblan":
        try:
            _bsblan_parameter_schreiben()
        except bsb_modul.BsbFehler as err:
            _LOGGER.warning("Auswahl nicht an BSB-LAN übergeben: %s", err)

    _sofort_lesen()
    return jsonify(neu)


@app.route("/api/werte")
def api_werte():
    state = store.load_state()
    return jsonify({"werte": state.get("werte") or {},
                    "letzter_lauf": state.get("letzter_lauf")})


@app.route("/api/lesen", methods=["POST"])
def api_lesen():
    """Jetzt lesen, statt auf den nächsten Takt zu warten.

    Ohne Angabe sind die ausgewählten Parameter gemeint. Mit ``{"nr": [...]}``
    liest der Manager genau diese – das braucht die Steuerung, in der auch
    Parameter stehen, die niemand dauerhaft überwacht.
    """
    daten = request.get_json(silent=True) or {}
    nummern = daten.get("nr")
    if nummern is not None and not isinstance(nummern, list):
        return jsonify({"fehler": "„nr“ erwartet eine Liste"}), 400
    ergebnis = _lesen(nummern=nummern)
    if nummern is not None and len(nummern) > MAX_AUF_ZURUF:
        ergebnis["hinweis"] = (
            f"Nur die ersten {MAX_AUF_ZURUF} von {len(nummern)} Parametern "
            f"gelesen – mehr auf einmal wäre dem Bus nicht zuzumuten. "
            f"Grenz die Liste mit Suche oder Kategorie ein.")
    return jsonify(ergebnis)


# -------------------------------------------------------------- Schreiben ----

@app.route("/api/setzen", methods=["POST"])
def api_setzen():
    """Einen Parameter in der Regelung stellen.

    Zwei Schalter müssen dafür stehen: der in BSB-LAN (``buswritable``) und
    der eigene unter *Einstellungen*. Beide sind ab Werk aus. Das ist Absicht –
    ein falscher Sollwert lässt im Winter eine Wohnung auskühlen, und das soll
    niemandem aus Versehen passieren.
    """
    config = store.load_config()
    if not config["einstellungen"]["schreiben_erlaubt"]:
        return jsonify({"fehler": "Das Stellen ist in den Einstellungen des "
                                  "Heizungsanlagenmanagers noch nicht freigegeben"}), 403
    daten = request.get_json(force=True) or {}
    nr = str(daten.get("nr", "")).strip()
    wert = daten.get("wert")
    if not nr or wert in (None, ""):
        return jsonify({"fehler": "Parameter und Wert werden beide gebraucht"}), 400

    katalog = store.load_katalog()
    eintrag = (katalog.get("parameter") or {}).get(nr)
    if eintrag and not eintrag.get("schreibbar"):
        return jsonify({"fehler": f"Parameter {nr} „{eintrag.get('name')}“ ist "
                                  f"laut Regelung nur lesbar"}), 400

    # Hat ein anderes Add-on diesen Parameter übernommen, schreibt hier nur
    # dieses selbst – erkennbar an „quelle“ im Rumpf. Für alle anderen wäre
    # es ein Tauziehen: Der Planer stellte den Wert beim nächsten Takt zurück,
    # und niemand verstünde, warum die Eingabe nicht hält.
    besitzer = store.uebernommen_von(store.load_uebernahme()).get(nr)
    if besitzer and str(daten.get("quelle") or "") != besitzer["quelle"]:
        return jsonify({
            "fehler": f"Parameter {nr} wird vom {besitzer['name']} geführt. "
                      f"Zum selbst Stellen die Übernahme aufheben.",
            "uebernahme": besitzer,
        }), 409
    try:
        antwort = _client().setzen(nr, wert)
    except bsb_modul.BsbFehler as err:
        return jsonify({"fehler": str(err)}), 400

    _LOGGER.info("Parameter %s auf %s gestellt", nr, wert)
    _sofort_lesen()
    return jsonify({"gesetzt": True, "antwort": antwort})


def main() -> None:
    _zeitzone_uebernehmen()
    _mqtt_starten()
    threading.Thread(target=_takt_schleife, daemon=True).start()
    threading.Thread(target=_poll_schleife, daemon=True).start()
    port = int(os.environ.get("INGRESS_PORT", 8099))
    _LOGGER.info("Heizungsanlagenmanager %s startet auf Port %d", VERSION, port)
    app.run(host="0.0.0.0", port=port, threaded=True, use_reloader=False)


if __name__ == "__main__":
    main()
