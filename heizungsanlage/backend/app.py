"""Heizungsanlagenmanager – Dienst, Abfragetakt und REST-Schnittstelle.

Der Manager liest in einem eigenen Faden die ausgewählten Parameter aus der
Heizungsregelung und spiegelt sie nach MQTT. Die Oberfläche sieht denselben
Zustand, den auch Home Assistant bekommt; es gibt keine zweite Wahrheit.
"""
from __future__ import annotations

import json
import logging
import os
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

    # Auf Zuruf gelesene Werte gehen nicht nach MQTT – nur die Auswahl.
    if nummern is None and _publisher is not None:
        try:
            _publisher.werte(auswahl, state["werte"])
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("MQTT-Meldung fehlgeschlagen: %s", err)
    # ``gelesen`` ist, was diesmal über den Bus kam – ``werte`` enthält auch
    # alles früher Gelesene. Die beiden zu verwechseln ließ das Protokoll
    # „126 Werte gelesen“ melden, wo dreizehn abgefragt wurden.
    return {"werte": state["werte"], "letzter_lauf": state["letzter_lauf"],
            "gelesen": gelesen}


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
        antwort["bsb"] = {
            "version": info.get("version"), "bus": info.get("bus"),
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
    _sofort_lesen()
    return jsonify(neu)


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
    port = int(os.environ.get("INGRESS_PORT", 8099))
    _LOGGER.info("Heizungsanlagenmanager %s startet auf Port %d", VERSION, port)
    app.run(host="0.0.0.0", port=port, threaded=True, use_reloader=False)


if __name__ == "__main__":
    main()
