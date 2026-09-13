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
    # Kategorien, die im Reiter „Regler“ nicht erscheinen sollen. Jede Anlage
    # schleppt Ecken mit, die ihr Besitzer nie braucht – bei der einen die
    # PPS-Emulation, bei der anderen die Kaskade. Das gehört eingestellt, nicht
    # weggeworfen: Ausgeblendetes ist einen Klick weit weg, nicht weg.
    "versteckte_kategorien": [],
    # Wohin gemeldet wird, wenn der Adapter ausfällt – notify-Dienste von Home
    # Assistant, wie in den übrigen Add-ons. Leer heißt: nur in der Oberfläche.
    # Die Wartezeit hält kurze Funklöcher aus der Meldung heraus; wer bei jedem
    # Ruckler eine Nachricht bekommt, liest ab der dritten keine mehr.
    "melden_an": [],
    "melden_nach_min": 10,
    # Zeigt der Regler beim Öffnen zuerst die zuletzt gelesenen Werte und
    # holt frische erst im Hintergrund? Das ist schnell und fast immer
    # richtig – aber eben nur fast: Wer am Gerät auf dem Kessel selbst dreht,
    # sähe für ein paar Sekunden den alten Stand. Wessen Anlage nur über Home
    # Assistant verstellt wird, für den kann das nicht schiefgehen.
    # Ab Werk aus, weil niemand die fremde Anlage kennt.
    "werte_merken": False,

    # Wer meldet die Werte nach Home Assistant?
    #
    #   "addon"   Der Manager liest und veröffentlicht selbst. Kuratierte
    #             Namen, eigene Geräteklassen – aber nichts kommt an, solange
    #             das Add-on steht.
    #   "bsblan"  BSB-LAN meldet selbst. Es bringt MQTT samt automatischer
    #             Anmeldung mit, fragt den Bus ohnehin ab und legt auch
    #             Bedienelemente an. Der Manager sagt ihm dann nur noch, was
    #             es melden soll – und hält sich mit eigenen Entitäten zurück,
    #             damit nicht zwei Programme dieselbe Anlage doppeln.
    #
    # Ab Werk "addon": Das ist der Zustand, den ein frisch installiertes
    # Add-on vorfindet, und es ändert nichts an einem fremden Gerät, bevor
    # jemand es will.
    "melder": "addon",

    # Was an BSB-LAN übergeben wird, wenn es melden soll. Broker, Benutzer und
    # Passwort kommen nicht von hier, sondern von Home Assistant selbst – der
    # Supervisor reicht sie dem Add-on durch. Niemand muss ein Passwort
    # abtippen, und hier steht keines herum.
    "bsblan_praefix": "BSBLAN",
    "bsblan_geraete_id": "",
    "bsblan_intervall_s": 60,
    "bsblan_einheiten": "ha",     # "ha" | "landes" | "keine"
    "bsblan_art": "einfach",      # "einfach" | "json" | "rich"
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


def validate_namen(roh) -> dict:
    """Eigene Namen für Parameter – Nummer auf Bezeichnung.

    Die Namen der Regelung sind nicht immer die der Anlage: Parameter 70 heißt
    in der Liste „Brauchwassertemperatur-Reduziertsollwert“ und ist in
    Wahrheit die Betriebsart. Wer das einmal herausgefunden hat, soll es
    aufschreiben können, statt es jedes Mal neu zu wissen.
    """
    if not isinstance(roh, dict):
        raise ValidationError("Die Namen müssen als Zuordnung kommen")
    raus = {}
    for nr, name in roh.items():
        nr = str(nr).strip()
        name = str(name or "").strip()
        if not nr:
            continue
        if len(name) > 60:
            raise ValidationError(f"Der Name für Parameter {nr} ist zu lang "
                                  "(höchstens 60 Zeichen)")
        if name:
            raus[nr] = name
    return raus


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
        "namen": dict((roh or {}).get("namen") or {}),
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

    e["werte_merken"] = bool(e.get("werte_merken"))

    e["melden_an"] = [str(d).strip() for d in (e.get("melden_an") or [])
                      if str(d).strip()]
    try:
        e["melden_nach_min"] = int(e["melden_nach_min"])
    except (TypeError, ValueError):
        raise ValidationError("Die Wartezeit vor einer Meldung muss eine Zahl sein")
    if not 1 <= e["melden_nach_min"] <= 1440:
        raise ValidationError("Die Wartezeit liegt zwischen einer Minute und "
                              "einem Tag")

    if e.get("melder") not in ("addon", "bsblan"):
        raise ValidationError("„melder“ kennt nur „addon“ und „bsblan“.")
    praefix = str(e.get("bsblan_praefix") or "").strip().strip("/") or "BSBLAN"
    if not praefix.replace("_", "").replace("-", "").isalnum():
        raise ValidationError("Das BSB-LAN-Präfix darf nur Buchstaben, Ziffern, "
                              "Strich und Unterstrich enthalten.")
    e["bsblan_praefix"] = praefix
    e["bsblan_geraete_id"] = str(e.get("bsblan_geraete_id") or "").strip()[:32]
    try:
        e["bsblan_intervall_s"] = int(e["bsblan_intervall_s"])
    except (TypeError, ValueError):
        raise ValidationError("Das BSB-LAN-Logintervall muss eine Zahl sein")
    if not 10 <= e["bsblan_intervall_s"] <= 3600:
        raise ValidationError("Das BSB-LAN-Logintervall muss zwischen 10 und "
                              "3600 Sekunden liegen")
    if e.get("bsblan_einheiten") not in ("ha", "landes", "keine"):
        raise ValidationError("Unbekannte Einheiten-Einstellung für BSB-LAN")
    if e.get("bsblan_art") not in ("einfach", "json", "rich"):
        raise ValidationError("Unbekannte MQTT-Art für BSB-LAN")

    versteckt = e.get("versteckte_kategorien")
    if versteckt is None:
        versteckt = []
    if not isinstance(versteckt, list):
        raise ValidationError("„versteckte_kategorien“ muss eine Liste sein.")
    e["versteckte_kategorien"] = sorted(
        {str(k).strip() for k in versteckt if str(k).strip()},
        key=lambda k: float(k) if k.replace(".", "", 1).isdigit() else 1e9)
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
        # 0 heißt: kein eigener Takt, es gilt der Grundtakt von BSB-LAN.
        try:
            takt = int(eintrag.get("takt_s") or 0)
        except (TypeError, ValueError):
            raise ValidationError(f"Ungültiger Takt bei Parameter {nr}")
        if takt and not 30 <= takt <= 86400:
            raise ValidationError("Ein eigener Takt liegt zwischen 30 Sekunden "
                                  "und einem Tag")
        raus.append({
            "nr": nr,
            "takt_s": takt,
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


def merke_state(**felder) -> None:
    """Einzelne Felder im Zustand fortschreiben – lesen, ändern, schreiben.

    ``save_state`` schreibt die ganze Datei aus einer Kopie, die der Aufrufer
    vorher geladen hat. Wer sie lange hält, macht dazwischen jede fremde
    Änderung rückgängig: Der Takt las beim Start den Zustand, brauchte vier
    Sekunden für 126 Werte über den Bus – und schrieb hinterher den Merker
    wieder weg, mit dem sich das Add-on gerade die neue Kennung notiert hatte.
    Das Abräumen der alten Entitäten lief deshalb bei **jedem** Start erneut.

    Hier wird innerhalb der Sperre gelesen und geschrieben, und nur die
    genannten Felder werden angefasst.
    """
    with _lock:
        state = _read(STATE_FILE, {})
        if not isinstance(state, dict):
            state = {}
        state.update(felder)
        _write(STATE_FILE, state)


# ───────────────────────────────────────── Übernahme durch andere Add-ons ────
#
# Der Heizungsplaner soll Sollwerte und Schaltzeiten übernehmen können. Damit
# das niemanden überrascht, steht hier, wer gerade was führt: Die Oberfläche
# legt diese Parameter still und schreibt dazu, wer sie hat.
#
# Zwei Dinge sind dabei Absicht:
#
# * **Eigenständig bleibt eigenständig.** Ist nichts eingetragen – und ab
#   Werk ist nichts eingetragen –, verhält sich das Add-on wie zuvor. Es
#   braucht den Planer nicht, es lässt ihm nur Platz.
# * **Wer davorsteht, behält das letzte Wort.** Eine Übernahme lässt sich in
#   der Oberfläche mit einem Klick aufheben. Eine Sperre, die man nicht lösen
#   kann, ist keine Zusammenarbeit, sondern eine Geiselnahme.

UEBERNAHME_FILE = os.path.join(DATA_DIR, "uebernahme.json")


def load_uebernahme() -> dict:
    """{quelle: {name, hinweis, parameter: [...], zeit}} – meist leer."""
    with _lock:
        roh = _read(UEBERNAHME_FILE, {})
    if not isinstance(roh, dict):
        return {}
    raus = {}
    for quelle, eintrag in roh.items():
        if not isinstance(eintrag, dict):
            continue
        raus[str(quelle)] = {
            "name": str(eintrag.get("name") or quelle),
            "hinweis": str(eintrag.get("hinweis") or ""),
            "parameter": [str(nr) for nr in (eintrag.get("parameter") or [])],
            "zeit": eintrag.get("zeit") or "",
        }
    return raus


def save_uebernahme(daten: dict) -> None:
    with _lock:
        _write(UEBERNAHME_FILE, daten)


def validate_uebernahme(roh: dict) -> tuple:
    """Eine Anmeldung prüfen. Ergebnis: (quelle, eintrag)."""
    if not isinstance(roh, dict):
        raise ValidationError("Die Anmeldung muss ein Objekt sein.")
    quelle = str(roh.get("quelle") or "").strip().lower()
    if not quelle or not quelle.replace("_", "").replace("-", "").isalnum():
        raise ValidationError(
            "„quelle“ fehlt oder enthält Sonderzeichen – erlaubt sind "
            "Buchstaben, Ziffern, Strich und Unterstrich.")
    parameter = roh.get("parameter")
    if not isinstance(parameter, list):
        raise ValidationError("„parameter“ muss eine Liste sein.")
    nummern = []
    for nr in parameter:
        nr = str(nr).strip()
        if not nr:
            continue
        if nr not in nummern:
            nummern.append(nr)
    return quelle, {
        "name": str(roh.get("name") or quelle).strip()[:60],
        "hinweis": str(roh.get("hinweis") or "").strip()[:200],
        "parameter": nummern,
        "zeit": roh.get("zeit") or "",
    }


def uebernommen_von(uebernahme: dict) -> dict:
    """Umgedreht nachschlagbar: {parameternummer: {quelle, name, hinweis}}.

    Führen zwei Quellen denselben Parameter, gewinnt die zuerst eingetragene.
    Das ist selten und immer ein Versehen – aber ein stiller Wechsel wäre
    schlimmer als eine feste Regel.
    """
    raus = {}
    for quelle, eintrag in (uebernahme or {}).items():
        for nr in eintrag.get("parameter") or []:
            raus.setdefault(str(nr), {
                "quelle": quelle, "name": eintrag.get("name") or quelle,
                "hinweis": eintrag.get("hinweis") or "",
                "zeit": eintrag.get("zeit") or "",
            })
    return raus
