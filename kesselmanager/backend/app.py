"""Kesselmanager – Dienst, Abfragetakt und REST-Schnittstelle.

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
_LOGGER = logging.getLogger("kesselmanager")

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

def _lesen(auswahl=None) -> dict:
    """Die ausgewählten Parameter einmal lesen und nach MQTT spiegeln."""
    global _letzter_fehler
    with _takt_lock:
        config = store.load_config()
        auswahl = auswahl if auswahl is not None else config["auswahl"]
        state = store.load_state()
        if not auswahl:
            return {"werte": {}, "hinweis": "Noch nichts ausgewählt"}

        try:
            roh = _client().werte([e["nr"] for e in auswahl])
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
        state["letzter_lauf"] = jetzt
        store.save_state(state)

    if _publisher is not None:
        try:
            _publisher.werte(auswahl, state["werte"])
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("MQTT-Meldung fehlgeschlagen: %s", err)
    return {"werte": state["werte"], "letzter_lauf": state["letzter_lauf"]}


def _takt_schleife() -> None:
    while True:
        try:
            ergebnis = _lesen()
            anzahl = len(ergebnis.get("werte") or {})
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
        aktuell = _publisher.discovery(auswahl, katalog,
                                       state.get("veroeffentlicht") or [])
        state["veroeffentlicht"] = aktuell
        store.save_state(state)
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


# --------------------------------------------------------------- Katalog ----

@app.route("/api/katalog")
def api_katalog():
    katalog = store.load_katalog()
    return jsonify({
        "gebaut_am": katalog.get("gebaut_am"),
        "geraete": katalog.get("geraete") or [],
        "kategorien": katalog.get("kategorien") or {},
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
        return jsonify(config["auswahl"])
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
    """Jetzt lesen, statt auf den nächsten Takt zu warten."""
    return jsonify(_lesen())


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
                                  "Kesselmanagers noch nicht freigegeben"}), 403
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
    _LOGGER.info("Kesselmanager %s startet auf Port %d", VERSION, port)
    app.run(host="0.0.0.0", port=port, threaded=True, use_reloader=False)


if __name__ == "__main__":
    main()
