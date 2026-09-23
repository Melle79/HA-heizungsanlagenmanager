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

    nachtragen(client, katalog)

    _LOGGER.info("Katalog gebaut: %d Kategorien, %d Parameter",
                 len(katalog["kategorien"]), len(katalog["parameter"]))
    return katalog


# Was die Regelung beantwortet, aber in keiner Kategorie von ``/JK`` steht.
# Die Bereichsgrenzen dort lassen Lücken: Kategorie 0 endet bei 0 – ohne die
# Unterparameter 0.1 bis 0.3 –, und die 622x liegen zwischen der letzten
# Kategorie (220) und dem benutzerdefinierten Bereich (ab 10000) im
# Niemandsland. Wer seinen Katalog aus ``/JK`` baut, sieht sie deshalb nie.
#
# Frederik Holst, der BSB-LAN gebaut hat, schreibt dazu: die 622x seien
# „eine der wenigen Telegramme, die auf so ziemlich allen Siemens-Reglern
# gehen“. Deshalb stehen diese wenigen Nummern hier ausnahmsweise fest –
# nachgetragen wird aber nur, was die Anlage auch wirklich beantwortet.
NACHTRAG = {
    "0.1": "Uhrzeit und Datum",
    "0.2": "Uhrzeit und Datum",
    "0.3": "Uhrzeit und Datum",
    "6224": "Geräteinformation",
    "6225": "Geräteinformation",
    "6226": "Geräteinformation",
    "6227": "Geräteinformation",
}


def nachtragen(client, katalog: dict) -> list:
    """Die Lücken von ``/JK`` schließen – durch Nachfragen, nicht durch Raten."""
    offen = [nr for nr in NACHTRAG if nr not in (katalog.get("parameter") or {})]
    if not offen:
        return []
    try:
        roh = client.werte(offen)
    except bsb_modul.BsbFehler as err:
        _LOGGER.info("Nachtrag übersprungen: %s", err)
        return []

    dazu = []
    for nr in offen:
        eintrag = roh.get(nr) or {}
        wert = str(eintrag.get("value") or "").strip()
        if eintrag.get("error") or not wert or wert == "---":
            continue                       # kennt diese Anlage nicht
        kat_name = NACHTRAG[nr]
        kid = _kategorie_fuer(katalog, kat_name, nr)
        kat_name = (katalog["kategorien"].get(kid) or {}).get("name") or kat_name
        katalog["parameter"][nr] = {
            "nr": nr,
            "name": eintrag.get("name") or f"Parameter {nr}",
            "kategorie": kid,
            "kategorie_name": kat_name,
            "unit": eintrag.get("unit") or "",
            "dataType_name": eintrag.get("dataType_name") or "",
            # Nachgetragene Auskünfte sind Auskünfte: nur lesen.
            "readwrite": 1,
            "schreibbar": False,
            "precision": eintrag.get("precision"),
            "isswitch": 0,
            "possibleValues": [],
        }
        katalog["parameter"][nr].update(store.vorschlag(katalog["parameter"][nr]))
        katalog["kategorien"].setdefault(
            kid, {"name": kat_name, "parameter": []})["parameter"].append(nr)
        dazu.append(nr)

    if dazu:
        _LOGGER.info("Nachgetragen, weil /JK sie nicht führt: %s", ", ".join(dazu))
    return dazu


def _kategorie_fuer(katalog: dict, name: str, nr: str = "") -> str:
    """Wohin der Nachtrag gehört.

    Zuerst dorthin, wo der Hauptparameter schon steht: 0.1 gehört zu 0, und
    wie diese Kategorie heißt, entscheidet die Regelung – hier „Uhrzeit“, auf
    der nächsten Anlage vielleicht anders. Eine zweite Kategorie mit einem
    ähnlichen Namen daneben wäre nur verwirrend.
    """
    haupt = str(nr).split(".")[0]
    if haupt and haupt != str(nr):
        for kid, kopf in (katalog.get("kategorien") or {}).items():
            if haupt in ((kopf or {}).get("parameter") or []):
                return kid
    for kid, kopf in (katalog.get("kategorien") or {}).items():
        if (kopf or {}).get("name") == name:
            return kid
    hoechste = max((_nummer(k) for k in (katalog.get("kategorien") or {})),
                   default=0)
    return str(int(hoechste) + 1)


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
    # Kein Messwert, sondern eine Einstellung – und trotzdem eine Kachel wert:
    # Eine Legionellenschaltung, die stillschweigend auf „aus“ steht, merkt
    # man erst, wenn sie jemand sucht. Sie wird darum auch seltener abgefragt
    # als die Messwerte, siehe MINDESTTAKT im Dienst.
    {"titel": "Legionellen", "worte": ["legionellen"], "weg": []},
]


# Für die Legionellenaufheizung braucht der Manager drei Parameter: den
# Sollwert, seine Obergrenze und den Istwert. Ihre Nummern stehen nirgends
# fest – gesucht wird über die Namen, wie überall in diesem Katalog.
TRINKWASSER_MUSTER = {
    "sollwert": {"worte": ["trinkwassertemperatur-nennsollwert",
                           "warmwassertemperatur-nennsollwert"],
                 "weg": ["maximum", "minimum", "reduziert", "frostschutz"]},
    "maximum": {"worte": ["nennsollwertmaximum"], "weg": []},
    "istwert": {"worte": ["warmwassertemperatur-istwert",
                          "trinkwassertemperatur-istwert",
                          "warmwassertemperatur istwert"],
                "weg": ["2", "soll"]},
    # Der Reduziertsollwert gilt in der Absenkphase – und nur er. Wer nachts
    # aufheizen will, muss ihn mitheben, sonst hält die Regelung stur ihre
    # 40 Grad, ganz gleich, was im Nennsollwert steht.
    "reduziert": {"worte": ["trinkwassertemperatur-reduziertsollwert",
                            "warmwassertemperatur-reduziertsollwert",
                            "warmwassertemperatur reduziertsollwert"],
                  "weg": []},
}


def trinkwasser_regelung(katalog: dict) -> dict:
    """Sollwert, Obergrenze, Istwert und Reduziertsollwert des Trinkwassers.

    Fehlt eines davon, fehlt es: Eine Aufheizung, die den Istwert nicht sieht,
    wüsste nicht, wann sie fertig ist, und eine ohne Obergrenze käme nicht
    über sie hinaus. Der Reduziertsollwert ist die Ausnahme – ohne ihn heizt
    eine Anlage auch auf, nur eben nicht in der Absenkphase.
    """
    parameter = list((katalog.get("parameter") or {}).values())
    parameter.sort(key=lambda e: _nummer(e.get("nr")))
    raus = {}
    for rolle, muster in TRINKWASSER_MUSTER.items():
        for eintrag in parameter:
            name = _klein(eintrag.get("name"))
            if not any(wort in name for wort in muster["worte"]):
                continue
            if any(wort in name for wort in muster["weg"]):
                continue
            if eintrag.get("possibleValues"):
                continue
            raus[rolle] = {"nr": str(eintrag.get("nr")),
                           "name": eintrag.get("name"),
                           "schreibbar": bool(eintrag.get("schreibbar"))}
            break
    return raus


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


# Das Trinkwasserprogramm wird nicht über die Programmwahl geschaltet, sondern
# über einen eigenen Parameter: Bei Sven ist es die 160 „Warmwasser-Mode“ mit
# den Werten „24h/Tag“, „Heizprogramme mit Vorverlegung“ und
# „Warmwasserprogramm“. Nur beim letzten gilt die Wochentabelle.
#
# Die Falle dabei: Auch die 178 „Funktion Zirkulationspumpe“ führt den Wert
# „Warmwasserprogramm“ – sie schaltet aber die Pumpe, nicht das Programm. Der
# Unterschied steckt im Namen des Parameters selbst, nicht in seinen Werten.

_TWW_WERT = re.compile(r"(warm|trink)wasser.?programm", re.I)
_TWW_NAME = re.compile(r"mode|modus|betriebsart|programm", re.I)


def trinkwasserwahl(katalog: dict) -> dict:
    """Der Parameter, der bestimmt, ob das Trinkwasserprogramm gilt."""
    for eintrag in sorted((katalog.get("parameter") or {}).values(),
                          key=lambda e: _nummer(e.get("nr"))):
        if _nummer(eintrag.get("nr")) >= EIGENE_AB:
            continue
        if not _TWW_NAME.search(str(eintrag.get("name") or "")):
            continue
        treffer = ""
        for wert in eintrag.get("possibleValues") or []:
            if _TWW_WERT.search(str(wert.get("desc") or "")):
                treffer = str(wert.get("enumValue"))
                break
        if treffer:
            return {"nr": str(eintrag.get("nr")),
                    "name": eintrag.get("name") or "",
                    "schreibbar": bool(eintrag.get("schreibbar")),
                    "programm": treffer,
                    "werte": [{"wert": str(w.get("enumValue")),
                               "text": str(w.get("desc") or "")}
                              for w in eintrag.get("possibleValues") or []]}
    return {}
