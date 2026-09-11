"""Was der Heizungsanlagenmanager sich merkt: Einstellungen, Auswahl, Parameterkatalog.

Drei Dateien unter ``/data``, alle als JSON:

``config.json``   Einstellungen und die Auswahl der Parameter
``katalog.json``  der von BSB-LAN gelesene Parameterkatalog (Zwischenspeicher)
``state.json``    Laufzeitzustand – zuletzt gelesene Werte, Zeitstempel

Getrennt, weil sie sich verschieden schnell ändern: Der Katalog wird einmal
geholt und liegt dann monatelang still, die Werte ändern sich alle paar
Minuten. Läge beides in einer Datei, schriebe der Manager den ganzen Katalog
bei jedem Takt neu auf die Speicherkarte.
"""
from __future__ import annotations

import json
import logging
import os
import threading

_LOGGER = logging.getLogger(__name__)

DATA_DIR = os.environ.get("DATA_DIR", "/data")
CONFIG_FILE = os.path.join(DATA_DIR, "config.json")
KATALOG_FILE = os.path.join(DATA_DIR, "katalog.json")
STATE_FILE = os.path.join(DATA_DIR, "state.json")

_lock = threading.Lock()


class ValidationError(ValueError):
    """Eine Eingabe, die so nicht gespeichert werden darf."""


STANDARD_EINSTELLUNGEN = {
    # Adresse von BSB-LAN. Ohne die geht nichts, deshalb steht sie ganz oben.
    # Ab Werk leer: Jede Anlage steht woanders im Netz, und eine fremde
    # Adresse als Vorgabe führt nur dazu, dass jemand minutenlang sucht,
    # warum nichts kommt. Ohne Adresse meldet der Manager offen "keine
    # Verbindung" und zeigt auf die Einstellungen.
    "bsb_url": "",
    "passkey": "",
    # Wie oft die ausgewählten Parameter gelesen werden. Fünf Minuten sind für
    # eine Heizung reichlich – ihre Trägheit misst sich in Stunden, nicht in
    # Sekunden, und jeder Takt belegt den Bus.
    "intervall_s": 300,
    # Doppelte Sicherung zum Schreiben: Auch wenn BSB-LAN es erlaubt, rührt
    # der Manager nichts an, solange dieser Schalter aus ist.
    "schreiben_erlaubt": False,
    "praefix": "heizungsanlage",
}

# Aus Einheit und Namen lässt sich meist ableiten, was Home Assistant wissen
# will. Die Tabelle ist bewusst kurz: Was nicht drinsteht, wird ein schlichter
# Sensor – das ist immer noch besser als eine falsche Geräteklasse.
EINHEIT_KLASSE = {
    "°C": ("temperature", "measurement"),
    "°F": ("temperature", "measurement"),
    "K": ("temperature", "measurement"),
    "%": (None, "measurement"),
    "bar": ("pressure", "measurement"),
    "kW": ("power", "measurement"),
    "kWh": ("energy", "total_increasing"),
    "A": ("current", "measurement"),
    "V": ("voltage", "measurement"),
    "h": ("duration", "measurement"),
    "min": ("duration", "measurement"),
    "s": ("duration", "measurement"),
    "l/h": (None, "measurement"),
    "m3": ("volume", "total_increasing"),
}

# Wörter, die einen Zählerstand verraten. Zählerstände wachsen nur und gehören
# als "total_increasing" gemeldet – dann baut Home Assistant von selbst eine
# Langzeitstatistik daraus.
ZAEHLER_WORTE = ("betriebsstunden", "starts", "laufzeit", "zähler", "menge",
                 "verbrauch", "arbeit")


def vorschlag(eintrag: dict) -> dict:
    """Was der Manager für einen Parameter vorschlägt, bevor jemand eingreift."""
    einheit = (eintrag.get("unit") or "").strip()
    name = (eintrag.get("name") or "").lower()
    klasse, verlauf = EINHEIT_KLASSE.get(einheit, (None, None))

    if any(wort in name for wort in ZAEHLER_WORTE):
        verlauf = "total_increasing"
        if not einheit:
            klasse = None

    # Aufzählungen (Betriebsart, Statusmeldungen) sind Text, keine Messwerte.
    if eintrag.get("possibleValues"):
        klasse, verlauf = None, None

    # Datum und Uhrzeit ebenso.
    if (eintrag.get("dataType_name") or "").upper() in ("DTTM", "HHMM", "DDMM", "TMSTP"):
        klasse, verlauf = None, None

    return {"device_class": klasse or "", "state_class": verlauf or "",
            "einheit": einheit}


# ------------------------------------------------------------ Dateizugriff ----

def _read(pfad: str, ersatz):
    try:
        with open(pfad, encoding="utf-8") as datei:
            return json.load(datei)
    except FileNotFoundError:
        return ersatz
    except (OSError, json.JSONDecodeError) as err:
        _LOGGER.error("%s ist unlesbar (%s) – es gilt die Vorgabe", pfad, err)
        return ersatz


def _write(pfad: str, daten) -> None:
    os.makedirs(os.path.dirname(pfad), exist_ok=True)
    # Erst daneben schreiben, dann umbenennen: Ein Stromausfall mitten im
    # Schreiben hinterlässt sonst eine halbe Datei, und der Manager startet
    # beim nächsten Mal ohne Auswahl.
    vorlaeufig = pfad + ".neu"
    with open(vorlaeufig, "w", encoding="utf-8") as datei:
        json.dump(daten, datei, ensure_ascii=False, indent=1)
    os.replace(vorlaeufig, pfad)


def _merge(vorgabe: dict, gespeichert: dict) -> dict:
    raus = dict(vorgabe)
    for schluessel, wert in (gespeichert or {}).items():
        if schluessel in vorgabe and isinstance(vorgabe[schluessel], dict) \
                and isinstance(wert, dict):
            raus[schluessel] = _merge(vorgabe[schluessel], wert)
        elif schluessel in vorgabe:
            raus[schluessel] = wert
    return raus


# ------------------------------------------------------------------ Config ----

def standard_einstellungen() -> dict:
    return json.loads(json.dumps(STANDARD_EINSTELLUNGEN))


# Bis Fassung 1.4.1 hieß das Add-on „Kesselmanager“, und so hießen auch die
# Entitäten. Wer von damals kommt, hat das Wort noch als MQTT-Präfix in seinen
# Einstellungen stehen – und würde die neuen Werte ausgerechnet auf die
# Themen schreiben, die beim Umbenennen abgeräumt werden.
ALTE_KENNUNG = "kesselmanager"


def load_config() -> dict:
    with _lock:
        roh = _read(CONFIG_FILE, {})
    einstellungen = _merge(standard_einstellungen(),
                           (roh or {}).get("einstellungen") or {})
    if einstellungen.get("praefix") == ALTE_KENNUNG:
        einstellungen["praefix"] = STANDARD_EINSTELLUNGEN["praefix"]
    return {
        "einstellungen": einstellungen,
        "auswahl": list((roh or {}).get("auswahl") or []),
    }


def save_config(config: dict) -> None:
    with _lock:
        _write(CONFIG_FILE, config)


def validate_einstellungen(roh: dict) -> dict:
    e = _merge(standard_einstellungen(), roh or {})
    url = str(e["bsb_url"] or "").strip().rstrip("/")
    if url and not url.startswith(("http://", "https://")):
        url = "http://" + url
    if not url:
        raise ValidationError("Ohne Adresse von BSB-LAN geht nichts")
    e["bsb_url"] = url
    e["passkey"] = str(e["passkey"] or "").strip().strip("/")
    try:
        e["intervall_s"] = int(e["intervall_s"])
    except (TypeError, ValueError):
        raise ValidationError("Das Abfrageintervall muss eine Zahl sein")
    if not 30 <= e["intervall_s"] <= 3600:
        raise ValidationError("Das Abfrageintervall muss zwischen 30 und 3600 "
                              "Sekunden liegen")
    e["schreiben_erlaubt"] = bool(e["schreiben_erlaubt"])
    praefix = str(e["praefix"] or "").strip().strip("/") or "heizungsanlage"
    if not praefix.replace("_", "").replace("-", "").isalnum():
        raise ValidationError("Das MQTT-Präfix darf nur Buchstaben, Ziffern, "
                              "Bindestrich und Unterstrich enthalten")
    e["praefix"] = praefix
    return e


def validate_auswahl(roh) -> list:
    if not isinstance(roh, list):
        raise ValidationError("Die Auswahl muss eine Liste sein")
    raus, gesehen = [], set()
    for eintrag in roh:
        if not isinstance(eintrag, dict):
            raise ValidationError("Ungültiger Eintrag in der Auswahl")
        nr = str(eintrag.get("nr", "")).strip()
        if not nr:
            raise ValidationError("Ein Eintrag ohne Parameternummer")
        if nr in gesehen:      # doppelte Auswahl ist keine Fehlermeldung wert
            continue
        gesehen.add(nr)
        raus.append({
            "nr": nr,
            "name": str(eintrag.get("name") or "").strip(),
            "anzeige": str(eintrag.get("anzeige") or "").strip(),
            "einheit": str(eintrag.get("einheit") or "").strip(),
            "device_class": str(eintrag.get("device_class") or "").strip(),
            "state_class": str(eintrag.get("state_class") or "").strip(),
        })
    return raus


# ----------------------------------------------------------------- Katalog ----

def load_katalog() -> dict:
    with _lock:
        katalog = _read(KATALOG_FILE, {})
    return katalog if isinstance(katalog, dict) else {}


def save_katalog(katalog: dict) -> None:
    with _lock:
        _write(KATALOG_FILE, katalog)


# ------------------------------------------------------------------ Zustand ----

def load_state() -> dict:
    with _lock:
        state = _read(STATE_FILE, {})
    if not isinstance(state, dict):
        state = {}
    state.setdefault("werte", {})            # nr -> {value, desc, zeit, error}
    state.setdefault("letzter_lauf", None)
    state.setdefault("veroeffentlicht", [])  # welche Entitäten angemeldet sind
    # Unter welcher Kennung und welchem Präfix das zuletzt geschah. Weicht es
    # beim Start ab, wurde umbenannt – dann gehört das Alte abgeräumt.
    state.setdefault("geraet", "")
    state.setdefault("praefix", "")
    return state


def save_state(state: dict) -> None:
    with _lock:
        _write(STATE_FILE, state)
