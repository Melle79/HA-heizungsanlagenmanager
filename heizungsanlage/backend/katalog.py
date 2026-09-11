"""Der Parameterkatalog: einmal holen, dann nachschlagen.

Welche Parameter eine Regelung kennt, hängt am Gerät – und bei Weishaupt und
Siemens sogar an der Gerätefamilie. Genau deshalb gibt es die Liste, die
Frederik aus den Rohdaten der Anlage baut: Sie steckt als ``custom_defs`` in
der BSB-LAN-Firmware und macht aus „Parameter 72“ eine
„Gerätebetriebsstunden“.

Dieses Modul liest sie dort ab, wo sie schon aufbereitet ist – über die
JSON-Schnittstelle von BSB-LAN selbst. Das ist robuster, als die ``.h``-Datei
zu zerlegen: Was BSB-LAN ausliefert, ist per Definition das, was auch
tatsächlich geflasht ist.

Der Katalog wird gespeichert, weil sein Aufbau den Bus mehrere Minuten
beschäftigt – 27 Kategorien, jede eine eigene Abfrage.
"""
from __future__ import annotations

import logging
import re
import time

import bsb as bsb_modul
import store

_LOGGER = logging.getLogger(__name__)

# Pause zwischen zwei Kategorien. Der Katalogaufbau ist das Unhöflichste, was
# der Manager je mit dem Bus anstellt; er soll es wenigstens langsam tun.
PAUSE_S = 0.5


def aufbauen(client: "bsb_modul.Bsb", fortschritt=None) -> dict:
    """Alle Kategorien durchgehen und einen flachen Katalog bauen.

    Ergebnis::

        {"kategorien": {"5": {"name": "Einstellwerte", "parameter": ["50", …]}},
         "parameter":  {"50": {"name": …, "unit": …, "readwrite": 0, …}},
         "gebaut_am": "2026-09-11T…", "geraete": [...]}
    """
    info = client.info()
    kategorien = client.kategorien()
    katalog = {"kategorien": {}, "parameter": {},
               "gebaut_am": time.strftime("%Y-%m-%dT%H:%M:%S"),
               "geraete": info.get("busdevices") or [],
               "bus": info.get("bus"), "version": info.get("version")}

    gesamt = len(kategorien)
    for i, (kid, kopf) in enumerate(sorted(kategorien.items(),
                                           key=lambda x: float(x[0]))):
        name = (kopf or {}).get("name") or f"Kategorie {kid}"
        if fortschritt:
            fortschritt(i + 1, gesamt, name)
        try:
            eintraege = client.kategorie(kid)
        except bsb_modul.BsbFehler as err:
            _LOGGER.warning("Kategorie %s (%s) übersprungen: %s", kid, name, err)
            eintraege = {}

        nummern = []
        for nr, eintrag in (eintraege or {}).items():
            if not isinstance(eintrag, dict):
                continue
            nummern.append(nr)
            katalog["parameter"][nr] = {
                "nr": nr,
                "name": eintrag.get("name") or f"Parameter {nr}",
                "kategorie": kid,
                "kategorie_name": name,
                "unit": eintrag.get("unit") or "",
                "dataType_name": eintrag.get("dataType_name") or "",
                # readwrite: 0 heißt bei BSB-LAN les- und schreibbar,
                # 1 heißt nur lesbar. Das ist verdreht zur Erwartung, deshalb
                # steht hier zusätzlich ein sprechendes Feld.
                "readwrite": eintrag.get("readwrite"),
                "schreibbar": eintrag.get("readwrite") == 0,
                "precision": eintrag.get("precision"),
                "isswitch": eintrag.get("isswitch"),
                "possibleValues": eintrag.get("possibleValues") or [],
            }
            katalog["parameter"][nr].update(store.vorschlag(
                katalog["parameter"][nr]))

        katalog["kategorien"][kid] = {"name": name, "parameter": nummern}
        if i + 1 < gesamt:
            time.sleep(PAUSE_S)

    _LOGGER.info("Katalog gebaut: %d Kategorien, %d Parameter",
                 len(katalog["kategorien"]), len(katalog["parameter"]))
    return katalog


def suchen(katalog: dict, text: str = "", nur_schreibbar: bool = False,
           kategorie: str = "") -> list:
    """Parameter suchen – nach Name, Nummer oder Kategorie."""
    text = (text or "").strip().lower()
    raus = []
    for eintrag in (katalog.get("parameter") or {}).values():
        if kategorie and str(eintrag.get("kategorie")) != str(kategorie):
            continue
        if nur_schreibbar and not eintrag.get("schreibbar"):
            continue
        if text:
            heuhaufen = f"{eintrag.get('nr')} {eintrag.get('name')} " \
                        f"{eintrag.get('kategorie_name')}".lower()
            if text not in heuhaufen:
                continue
        raus.append(eintrag)
    raus.sort(key=lambda e: float(e["nr"]) if _zahl(e["nr"]) else 1e9)
    return raus


def _zahl(text) -> bool:
    try:
        float(text)
        return True
    except (TypeError, ValueError):
        return False


# ─────────────────────────────────────── Was die Anlage von selbst verrät ────
#
# Alles hier drunter ersetzt Zahlen, die einmal fest im Quelltext standen.
# Das war bequem und falsch: „115 ist die Kesseltemperatur“ gilt nur für die
# Parameterliste, die auf *einem* Gerät geflasht ist. Eine Standard-BSB-Anlage
# nennt dieselbe Größe 8310, und die Zeitprogramme sitzen dort in ganz anderen
# Kategorien. Wer den Manager auf seine eigene Heizung setzt, soll ihn nicht
# erst umschreiben müssen.
#
# Also wird gefragt statt angenommen – der Katalog kommt ohnehin aus dem Gerät.

# Der Datentyp, den BSB-LAN einem Schaltzeitenparameter gibt. Er steht in der
# Firmware, nicht in der Geräteliste, und ist damit über alle Anlagen gleich.
TIMEPROG = "TIMEPROG"

# Ab dieser Nummer hört die Regelung auf und BSB-LAN fängt an: 10000–11999
# sind selbst angelegte Parameter, 15000er die PPS-Emulation, 20000er
# angeklemmte One-Wire- und DHT-Fühler. Auch die führen Schaltzeiten, aber
# sie stehen nicht in der Heizung – wer den Reiter „Zeitprogramme“ öffnet,
# sucht die Programme seines Kessels und nicht die des Adapters.
EIGENE_AB = 10000


def _nummer(nr) -> float:
    try:
        return float(nr)
    except (TypeError, ValueError):
        return float("inf")

# Die sechs Kacheln der Übersicht, gesucht über den Namen. ``weg`` hält
# Nachbarn heraus, die sonst zuerst treffen würden – „Kesseltemperatur-
# Sollwert“ ist nicht der Istwert, und „Aussentemperatur gedämpft“ nicht die
# Außentemperatur.
KACHEL_MUSTER = [
    {"titel": "Kessel", "worte": ["kesseltemperatur"],
     "weg": ["soll", "kaskade", "maximum", "minimum", "korrektur"]},
    {"titel": "Vorlauf", "worte": ["vorlauftemperatur"],
     "weg": ["soll", "kaskade", "maximum", "minimum", "korrektur"]},
    {"titel": "Außen", "worte": ["aussentemperatur", "außentemperatur"],
     "weg": ["gedämpft", "gedaempft", "gemischt", "korrektur", "quelle",
             "minimum", "maximum", "lieferant"]},
    {"titel": "Außen gedämpft", "worte": ["gedämpft", "gedaempft"], "weg": []},
    {"titel": "Betriebsstunden", "worte": ["betriebsstunden", "betriebszeit"],
     "weg": ["wartung", "seit", "pumpe", "brenner stufe 2"]},
    {"titel": "Brennerstarts", "worte": ["starts", "startzähler",
                                         "startzaehler"],
     "weg": ["wartung", "seit", "stufe 2"]},
]


def _klein(text) -> str:
    return str(text or "").lower()


def zeitprogramme(katalog: dict) -> dict:
    """Welche Kategorien Schaltzeiten enthalten – und welche Parameter darin.

    Erkannt am Datentyp ``TIMEPROG``, nicht an der Kategorienummer. Damit
    findet der Manager die Programme auf jeder Anlage, und er findet in einer
    Kategorie auch nur die Tage: Nachbarn wie „Standardwerte“ oder
    „Vorwahl“ stehen oft daneben und sind keine Schaltzeiten.
    """
    raus = {}
    parameter = katalog.get("parameter") or {}
    for kid, kopf in (katalog.get("kategorien") or {}).items():
        tage = [nr for nr in (kopf.get("parameter") or [])
                if _klein((parameter.get(nr) or {}).get("dataType_name")) ==
                _klein(TIMEPROG) and _nummer(nr) < EIGENE_AB]
        if tage:
            raus[str(kid)] = {"name": kopf.get("name") or f"Kategorie {kid}",
                              "tage": tage}
    return raus


def kacheln(katalog: dict) -> list:
    """Die Parameter für die Übersicht – gesucht über den Namen.

    Gefunden wird der mit der kleinsten Nummer, der passt; findet sich für
    eine Kachel nichts, fällt sie weg. Eine leere Übersicht ist ehrlicher als
    eine, die Zahlen einer fremden Anlage anzeigt.
    """
    parameter = list((katalog.get("parameter") or {}).values())
    parameter.sort(key=lambda e: _nummer(e.get("nr")))
    raus = []
    for muster in KACHEL_MUSTER:
        for eintrag in parameter:
            name = _klein(eintrag.get("name"))
            if not any(wort in name for wort in muster["worte"]):
                continue
            if any(wort in name for wort in muster["weg"]):
                continue
            # Ein Sollwert ist kein Messwert, und eine Aufzählung erst recht
            # nicht – beides taugt nicht als Kachel.
            if eintrag.get("possibleValues"):
                continue
            raus.append({"titel": muster["titel"], "nr": eintrag.get("nr"),
                         "name": eintrag.get("name"),
                         "einheit": eintrag.get("unit") or "",
                         "dataType_name": eintrag.get("dataType_name") or "",
                         "schreibbar": bool(eintrag.get("schreibbar"))})
            break
    return raus


# ──────────────────────────────────────────── Ordnung in die Gliederung ────
#
# 27 Kategorien nebeneinander sind eine Wand aus Knöpfen. Am Gerät auf dem
# Kessel blättert man sich durch – hier sieht man alles auf einmal, und das
# ist keine Übersicht, sondern eine Liste.
#
# Also Gruppen. Sie kommen aus den Namen, die die Anlage selbst liefert, denn
# feste Kategorienummern gelten wieder nur für eine Parameterliste. Was in
# keine Gruppe passt, verschwindet nicht – es landet unter „Weitere“.

GRUPPEN = [
    {"titel": "Zeitprogramme", "worte": ["zeitprogramm", "zeitschaltprogramm",
                                         "schaltzeiten", "time program"]},
    {"titel": "Heizen", "worte": ["heizkreis", "raumführung", "raumfuehrung",
                                  "einstellwerte", "betriebsart", "urlaub",
                                  "ferien", "kennlinie", "heating circuit"]},
    {"titel": "Trinkwasser", "worte": ["trinkwasser", "warmwasser", "tww",
                                       "legionell", "dhw", "hot water"]},
    {"titel": "Wärmeerzeuger", "worte": ["kessel", "brenner", "feuerung",
                                         "kaskade", "abgas", "solar",
                                         "wärmepumpe", "waermepumpe",
                                         "zusatzerzeuger", "erzeuger",
                                         "boiler", "burner"]},
    {"titel": "Speicher", "worte": ["puffer", "speicher", "schwimmbad",
                                    "buffer", "storage"]},
    {"titel": "Wartung & Diagnose", "worte": ["status", "fehler", "wartung",
                                              "service", "diagnose", "test",
                                              "störung", "stoerung", "error",
                                              "maintenance"]},
    {"titel": "Anlage & Konfiguration", "worte": ["anlage", "konfiguration",
                                                  "option", "uhrzeit", "datum",
                                                  "bedien", "lpb", "eingang",
                                                  "ausgang", "system", "time",
                                                  "config"]},
]

# Alles ab hier gehört BSB-LAN selbst und nicht der Regelung: eigene
# Parameter, die PPS-Emulation, angeklemmte One-Wire-Fühler. Für die meisten
# ist das leerer Platz – deshalb eine eigene Gruppe, die man wegklicken kann.
GRUPPE_BSBLAN = "BSB-LAN selbst"
GRUPPE_REST = "Weitere"


def gruppen(katalog: dict) -> list:
    """Die Kategorien in Gruppen – in fester Reihenfolge, ohne Verluste.

    Ergebnis::

        [{"titel": "Heizen", "kategorien": [{"id": "13", "name": "Heizkreis",
                                             "anzahl": 12}]}]

    Jede Kategorie kommt genau einmal vor: Sie fällt in die erste Gruppe,
    deren Wörter passen. Die Reihenfolge oben ist deshalb nicht beliebig –
    „IO-Test“ soll bei der Diagnose landen und nicht bei der Konfiguration.
    """
    zuordnung = {g["titel"]: [] for g in GRUPPEN}
    zuordnung[GRUPPE_BSBLAN] = []
    zuordnung[GRUPPE_REST] = []

    for kid, kopf in sorted((katalog.get("kategorien") or {}).items(),
                            key=lambda x: _nummer(x[0])):
        nummern = kopf.get("parameter") or []
        eintrag = {"id": str(kid),
                   "name": (kopf.get("name") or "").strip() or f"Kategorie {kid}",
                   "anzahl": len(nummern)}
        # Eine Kategorie, deren Parameter allesamt jenseits der Grenze liegen,
        # gehört BSB-LAN – unabhängig davon, wie sie heißt.
        if nummern and all(_nummer(nr) >= EIGENE_AB for nr in nummern):
            zuordnung[GRUPPE_BSBLAN].append(eintrag)
            continue
        name = _klein(eintrag["name"])
        for gruppe in GRUPPEN:
            if any(wort in name for wort in gruppe["worte"]):
                zuordnung[gruppe["titel"]].append(eintrag)
                break
        else:
            zuordnung[GRUPPE_REST].append(eintrag)

    reihenfolge = [g["titel"] for g in GRUPPEN] + [GRUPPE_BSBLAN, GRUPPE_REST]
    return [{"titel": titel, "kategorien": zuordnung[titel]}
            for titel in reihenfolge if zuordnung[titel]]


# ─────────────────────────────────────────── Welches Programm gerade läuft ────
#
# Diese Regelung führt drei Heizprogramme, aber nur eines davon ist aktiv. Die
# Wahl steckt in einem gewöhnlichen Parameter: bei Sven ist es die Nummer 70,
# deren Auswahlwerte „Standby, Programm 3, Programm 2, Programm 1, Nenn,
# Reduziert, Sommer“ heißen. Die Nummer ist nichts Allgemeines – der Weg
# dahin schon: Wer eine Aufzählung führt, in der mehrfach „Programm <Zahl>“
# steht, der meint damit die Programmwahl.
#
# Der Name des Parameters taugt dafür nicht. In Svens Liste heißt 70
# „Brauchwassertemperatur-Reduziertsollwert“ – das ist schlicht falsch, die
# Auswahlwerte verraten die Wahrheit.

_PROGRAMM = re.compile(r"programm\s*(\d+)", re.I)


def programmwahl(katalog: dict) -> dict:
    """Der Parameter, der bestimmt, welches Zeitprogramm läuft.

    Ergebnis ``{"nr": "70", "name": …, "zu": {"1": "3", "2": "2", "3": "1"}}``
    – von der Programmnummer auf den Wert, den der Parameter dafür annimmt.
    Findet sich nichts, kommt ein leeres Verzeichnis zurück: Dann sagt die
    Oberfläche nichts, statt etwas zu behaupten.
    """
    beste = None
    for eintrag in sorted((katalog.get("parameter") or {}).values(),
                          key=lambda e: _nummer(e.get("nr"))):
        if _nummer(eintrag.get("nr")) >= EIGENE_AB:
            continue
        zu = {}
        for wert in eintrag.get("possibleValues") or []:
            treffer = _PROGRAMM.search(str(wert.get("desc") or ""))
            if treffer:
                zu.setdefault(treffer.group(1), str(wert.get("enumValue")))
        # Eine einzelne Erwähnung ist Zufall – „Warmwasserprogramm“ etwa.
        # Erst mehrere nummerierte Programme sind eine Wahl.
        if len(zu) >= 2:
            beste = {"nr": str(eintrag.get("nr")),
                     "name": eintrag.get("name") or "",
                     "schreibbar": bool(eintrag.get("schreibbar")),
                     "zu": zu,
                     # Die ganze Auswahl, nicht nur die Programme: Standby,
                     # Sommer und Dauerbetrieb gehören zur selben Entscheidung
                     # und sollen dort stehen, wo sie getroffen wird.
                     "werte": [{"wert": str(w.get("enumValue")),
                                "text": str(w.get("desc") or "")}
                               for w in eintrag.get("possibleValues") or []]}
            break
    return beste or {}
