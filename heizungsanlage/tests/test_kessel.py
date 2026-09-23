#!/usr/bin/env python3
"""Trockenprüfung des Heizungsanlagenmanagers – ohne Heizung, ohne Home Assistant.

Aufruf aus dem Repo:

    python3 kesselmanager/tests/test_kessel.py

Der Manager hängt an einer Anlage, die sonst niemand hat. Damit trotzdem
jemand daran arbeiten kann, ist BSB-LAN hier gefälscht: ``requests.get`` und
``requests.post`` werden ersetzt, und die Antworten sind dieselben JSON-
Strukturen, die ein echtes Gerät liefert.

Geprüft wird vor allem, was in der Praxis schiefgeht: ein abgelehnter Wert,
ein Aussetzer mitten in einer Abfrage, und die Ableitung der Geräteklassen –
denn eine falsche macht aus einem Betriebsstundenzähler einen Messwert ohne
Statistik.

Ein Fall steht hier, weil er einmal falsch war: ``buswritable`` aus ``/JI``
taugt **nicht** als Verbot. Die Zahl und die tatsächliche Sperre entstehen in
BSB-LAN aus verschiedenen Rechnungen, und eine willige Anlage meldet dort
durchaus eine Null.
"""
import json
import os
import threading
import time
import sys
import tempfile

os.environ["DATA_DIR"] = tempfile.mkdtemp()
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "backend"))

import bsb
import katalog
import store

fehler = []


def pruefe(bedingung, text):
    print(f"  {'✓' if bedingung else '✗'} {text}")
    if not bedingung:
        fehler.append(text)


# ── Das gefälschte BSB-LAN ───────────────────────────────────────────────
class Antwort:
    def __init__(self, daten, code=200):
        self._daten, self.status_code = daten, code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise bsb.requests.HTTPError(f"HTTP {self.status_code}")

    def json(self):
        if self._daten is None:
            raise ValueError("kein JSON")
        return self._daten


ANLAGE = {
    "schreibbar": False,
    "abfragen": [],          # Protokoll aller /JQ-Aufrufe
    "gesetzt": [],           # Protokoll aller /JS-Aufrufe
    "aussetzer": set(),      # Bündel, die scheitern sollen
    "status": 1,             # 1 = gesetzt, 2 = nur lesbar, 0 = fehlgeschlagen
}

KATEGORIEN = {"1": {"name": "Zeitschaltprogramm 1", "min": 11, "max": 11.7},
              "5": {"name": "Einstellwerte", "min": 50, "max": 55},
              "13": {"name": "Kessel", "min": 190, "max": 196}}
PARAMETER = {
    "1": {
        "11": {"name": "Montag", "unit": "", "dataType_name": "TIMEPROG",
               "readwrite": 0, "possibleValues": []},
        "11.1": {"name": "Dienstag", "unit": "", "dataType_name": "TIMEPROG",
                 "readwrite": 0, "possibleValues": []},
        # Der Nachbar, der keine Schaltzeit ist – und der früher als achter
        # „Tag“ in der Wochentabelle gelandet wäre.
        "11.9": {"name": "Standardwerte", "unit": "", "dataType_name": "ENUM",
                 "readwrite": 0,
                 "possibleValues": [{"enumValue": "0", "desc": "Nein"}]},
    },
    "5": {
        "50": {"name": "Raumtemperatur Komfortsollwert", "unit": "°C",
               "dataType_name": "TEMP", "readwrite": 0, "precision": 0.1,
               "possibleValues": []},
        "55": {"name": "Trinkwassertemperatur-Nennsollwert", "unit": "°C",
               "dataType_name": "TEMP", "readwrite": 0, "precision": 0.1,
               "possibleValues": []},
    },
    "13": {
        "72": {"name": "Gerätebetriebsstunden", "unit": "h",
               "dataType_name": "VALS", "readwrite": 1, "possibleValues": []},
        "73": {"name": "Starts", "unit": "", "dataType_name": "VALS",
               "readwrite": 1, "possibleValues": []},
        "192": {"name": "Brennerart", "unit": "", "dataType_name": "ENUM",
                "readwrite": 0,
                "possibleValues": [{"enumValue": "0", "desc": "1-stufig"},
                                   {"enumValue": "1", "desc": "2-stufig"}]},
    },
}


def _get(url, timeout=None):
    if "/JI" in url:
        return Antwort({"version": "5.1.18", "bus": "LPB", "busaddr": 0,
                        "buswritable": 1 if ANLAGE["schreibbar"] else 0,
                        "busdevices": [{"dev_id": 0, "dev_name": "WRS-CPU-B2/E",
                                        "dev_fam": 50, "dev_var": 252}]})
    if "/JK=ALL" in url:
        return Antwort(KATEGORIEN)
    if "/JK=" in url:
        return Antwort(PARAMETER.get(url.rsplit("=", 1)[1], {}))
    if "/JQ=" in url:
        gefragt = url.rsplit("=", 1)[1].split(",")
        ANLAGE["abfragen"].append(gefragt)
        if tuple(gefragt) in ANLAGE["aussetzer"]:
            raise bsb.requests.Timeout("Bus belegt")
        raus = {}
        for nr in gefragt:
            for eintraege in PARAMETER.values():
                if nr in eintraege:
                    raus[nr] = {"name": eintraege[nr]["name"], "value": "42",
                                "unit": eintraege[nr]["unit"], "error": 0}
        return Antwort(raus)
    raise AssertionError("unerwarteter Aufruf " + url)


def _post(url, json=None, timeout=None):
    ANLAGE["gesetzt"].append(json)
    return Antwort({json["Parameter"]: {"status": ANLAGE["status"]}})


bsb.requests.get = _get
bsb.requests.post = _post
client = bsb.Bsb("http://kessel.test")


print("=== Der Katalog ===")
k = katalog.aufbauen(client)
pruefe(len(k["kategorien"]) == 3, "alle drei Kategorien sind drin")
pruefe(len(k["parameter"]) == 8, "acht Parameter insgesamt")
pruefe(k["parameter"]["50"]["schreibbar"] is True,
       "readwrite 0 heißt schreibbar – die Umkehrung ist die Falle")
pruefe(k["parameter"]["72"]["schreibbar"] is False, "readwrite 1 heißt nur lesen")
pruefe(k["parameter"]["72"]["kategorie_name"] == "Kessel",
       "der Kategoriename hängt am Parameter")

print("\n=== Die Anlage verrät sich selbst ===")
# Der Kern der Frage „taugt das auch für andere?“. Früher standen die
# Parameternummern der Übersicht und die Kategorien der Zeitprogramme fest im
# Quelltext – und galten damit für genau eine geflashte Parameterliste.
zp = katalog.zeitprogramme(k)
pruefe(list(zp) == ["1"], "die Kategorie mit Schaltzeiten wird gefunden")
pruefe(zp["1"]["tage"] == ["11", "11.1"],
       "und darin nur die Tage – „Standardwerte“ gehört nicht dazu")
pruefe(zp["1"]["name"] == "Zeitschaltprogramm 1", "mit ihrem eigenen Namen")

# BSB-LAN fuehrt eigene Schaltzeiten fuer seine PPS-Emulation. Die sind echt,
# stehen aber im Adapter und nicht in der Heizung - im Reiter waeren sie ein
# fuenftes Programm, das nichts schaltet.
EIGENE = {"kategorien": {"25": {"name": "PPS-Bus", "parameter": ["15050"]}},
          "parameter": {"15050": {"nr": "15050", "name": "Montag",
                                  "dataType_name": "TIMEPROG"}}}
pruefe(katalog.zeitprogramme(EIGENE) == {},
       "was BSB-LAN selbst mitbringt, ist kein Programm der Regelung")

ka = {kachel["titel"]: kachel["nr"] for kachel in katalog.kacheln(k)}
pruefe(ka.get("Betriebsstunden") == "72", "Betriebsstunden über den Namen")
pruefe("Kessel" not in ka,
       "was die Anlage nicht führt, bekommt auch keine Kachel")

print("\n=== Dieselbe Rechnung auf einer fremden Anlage ===")
# Eine Standard-BSB-Anlage: andere Nummern, andere Kategorien, andere Namen.
# Findet der Manager sich hier zurecht, findet er sich überall zurecht.
FREMD = {
    "kategorien": {
        "3": {"name": "Zeitprogramm Heizkreis 1",
              "parameter": ["500", "501", "516"]},
        "20": {"name": "Kessel", "parameter": ["8310", "8330", "8700"]},
    },
    "parameter": {
        "500": {"nr": "500", "name": "Montag", "dataType_name": "TIMEPROG"},
        "501": {"nr": "501", "name": "Dienstag", "dataType_name": "TIMEPROG"},
        "516": {"nr": "516", "name": "Standardwerte", "dataType_name": "ENUM",
                "possibleValues": [{"enumValue": "0", "desc": "Nein"}]},
        "8310": {"nr": "8310", "name": "Kesseltemperatur Istwert",
                 "unit": "°C", "dataType_name": "TEMP"},
        "8330": {"nr": "8330", "name": "Brenner Betriebsstunden Stufe 1",
                 "unit": "h", "dataType_name": "HOURS"},
        "8700": {"nr": "8700", "name": "Außentemperatur", "unit": "°C",
                 "dataType_name": "TEMP"},
    },
}
fzp = katalog.zeitprogramme(FREMD)
pruefe(list(fzp) == ["3"], "das fremde Zeitprogramm sitzt in Kategorie 3")
pruefe(fzp["3"]["tage"] == ["500", "501"], "und führt seine eigenen Nummern")
fka = {kachel["titel"]: kachel["nr"] for kachel in katalog.kacheln(FREMD)}
pruefe(fka.get("Kessel") == "8310", "Kesseltemperatur heißt dort 8310")
pruefe(fka.get("Außen") == "8700", "Außentemperatur 8700 – mit scharfem ß")
pruefe(fka.get("Betriebsstunden") == "8330", "Betriebsstunden 8330")

print("\n=== Was eine Kachel nicht sein darf ===")
VERWECHSLUNG = {"kategorien": {"1": {"name": "x", "parameter": ["a", "b", "c"]}},
                "parameter": {
                    "a": {"nr": "8311", "name": "Kesseltemperatur Sollwert",
                          "unit": "°C"},
                    "b": {"nr": "8310", "name": "Kesseltemperatur Istwert",
                          "unit": "°C"},
                    "c": {"nr": "8703", "name": "Außentemperatur gedämpft",
                          "unit": "°C"}}}
v = {kachel["titel"]: kachel["nr"] for kachel in katalog.kacheln(VERWECHSLUNG)}
pruefe(v.get("Kessel") == "8310", "der Sollwert wird nicht für den Istwert gehalten")
pruefe(v.get("Außen") is None,
       "und die gedämpfte Außentemperatur nicht für die Außentemperatur")
pruefe(v.get("Außen gedämpft") == "8703", "die bekommt ihre eigene Kachel")

print("\n=== Was Home Assistant bekommen soll ===")
p = k["parameter"]
pruefe(p["50"]["device_class"] == "temperature" and p["50"]["state_class"] == "measurement",
       "°C wird zu temperature/measurement")
pruefe(p["72"]["state_class"] == "total_increasing",
       "Betriebsstunden werden zum Zähler, nicht zum Messwert")
pruefe(p["73"]["state_class"] == "total_increasing",
       "Starts ebenso – auch ohne Einheit")
pruefe(p["192"]["device_class"] == "" and p["192"]["state_class"] == "",
       "eine Aufzählung ist Text, kein Messwert")

print("\n=== Suchen ===")
pruefe(len(katalog.suchen(k, "start")) == 1, "Suche nach Namen")
pruefe(len(katalog.suchen(k, "", nur_schreibbar=True)) == 6, "nur schreibbare")
pruefe(len(katalog.suchen(k, "", kategorie="13")) == 3, "nach Kategorie")
pruefe([e["nr"] for e in katalog.suchen(k, "", kategorie="13")] == ["72", "73", "192"],
       "sortiert nach Parameternummer, nicht alphabetisch")

print("\n=== Abfragen kommen in Häppchen ===")
ANLAGE["abfragen"].clear()
bsb.PAUSE_S = 0            # im Test nicht warten
viele = [str(n) for n in range(1, 31)]
client.werte(viele)
pruefe(len(ANLAGE["abfragen"]) == 3, "30 Parameter werden zu drei Bündeln")
pruefe(all(len(b) <= bsb.BUENDEL for b in ANLAGE["abfragen"]),
       "kein Bündel ist größer als erlaubt")

print("\n=== Ein Aussetzer kostet nicht die ganze Runde ===")
ANLAGE["abfragen"].clear()
ANLAGE["aussetzer"] = {("50", "55")}
ergebnis = client.werte(["50", "55"])
pruefe(ergebnis == {}, "das gescheiterte Bündel liefert nichts")
ANLAGE["aussetzer"] = set()
ergebnis = client.werte(["50", "72"])
pruefe(set(ergebnis) == {"50", "72"}, "danach geht es normal weiter")

print("\n=== buswritable ist kein Tuersteher ===")
# Der Fehler, der das ausgeloest hat: /JI meldet eine Null, obwohl die Anlage
# Aenderungen annimmt. Die beiden Werte entstehen in BSB-LAN aus verschiedenen
# Rechnungen - ein Verbot darauf zu bauen sperrt den Benutzer aus.
ANLAGE["schreibbar"] = False        # BSB-LAN sagt "nur lesen"
ANLAGE["gesetzt"].clear()
client.setzen("50", "21.5")
pruefe(ANLAGE["gesetzt"][-1] == {"Parameter": "50", "Value": "21.5", "Type": "1"},
       "trotz gemeldeter Null wird geschrieben - die Regelung entscheidet")

print("\n=== Schreiben ===")
ANLAGE["schreibbar"] = True
ANLAGE["gesetzt"].clear()
client.setzen("50", "21.5")
pruefe(ANLAGE["gesetzt"][-1] == {"Parameter": "50", "Value": "21.5", "Type": "1"},
       "Parameter, Wert und Typ 1 - eine SET-Nachricht")

print("\n=== Was die Statuszahlen bedeuten ===")
# Der Rueckgabewert von set() in BSB-LAN, und er ist nicht selbsterklaerend:
#   1 = gesetzt, 2 = Parameter ist nur lesbar, 0 = fehlgeschlagen.
# Wer aus Gewohnheit die Null fuer den Erfolg haelt, meldet jede gelungene
# Aenderung als Fehler - genau das ist einmal passiert.
ANLAGE["status"] = 1
client.setzen("50", "55")
pruefe(True, "Status 1 ist der Erfolg und wirft keinen Fehler")

ANLAGE["status"] = 2
try:
    client.setzen("72", "1")
    pruefe(False, "Status 2 meldet einen nur lesbaren Parameter")
except bsb.BsbFehler as err:
    pruefe("nur lesbar" in str(err), "Status 2 meldet einen nur lesbaren Parameter")

ANLAGE["status"] = 0
try:
    client.setzen("50", "999")
    pruefe(False, "Status 0 meldet einen nicht uebernommenen Wert")
except bsb.BsbFehler as err:
    pruefe("nicht uebernommen" in str(err).replace("ü", "ue"),
           "Status 0 meldet einen nicht uebernommenen Wert")

# Meldet BSB-LAN zusaetzlich "nur lesen", steht das als Hinweis dabei -
# hinterher als Erklaerung, nicht vorher als Verbot.
ANLAGE["schreibbar"] = False
try:
    client.setzen("50", "999")
except bsb.BsbFehler as err:
    pruefe("Schreibzugriff" in str(err),
           "dabei wird der BSB-LAN-Schalter als moegliche Ursache genannt")
ANLAGE["status"] = 1
ANLAGE["schreibbar"] = True

print("\n=== Die Fassung steht an einer Stelle ===")
# Sie stand einmal doppelt - in config.yaml und in version.py - und lief
# auseinander: Die Oberflaeche zeigte drei Fassungen lang eine falsche Nummer.
import pathlib, re, version
kopf = (pathlib.Path(__file__).resolve().parent.parent / "config.yaml")
aus_yaml = re.search(r'^version:\s*"?([^"\s]+)"?', kopf.read_text(encoding="utf-8"), re.M)
pruefe(aus_yaml is not None and version.VERSION == aus_yaml.group(1),
       f"version.py und config.yaml sagen dasselbe ({version.VERSION})")

print("\n=== Ordnung im Menue ===")
# 27 Kategorien nebeneinander sind eine Wand aus Knoepfen. Gruppiert wird nach
# den Namen, die die Anlage liefert - Nummern gelten wieder nur fuer eine
# Parameterliste.
MENUE = {"kategorien": {
    "0":  {"name": "Uhrzeit", "parameter": ["1"]},
    "1":  {"name": "Zeitschaltprogramm 1", "parameter": ["11"]},
    "10": {"name": "IO-Test", "parameter": ["90"]},
    "13": {"name": "Heizkreis", "parameter": ["140"]},
    "14": {"name": "Warmwasser", "parameter": ["160"]},
    "19": {"name": "Kessel", "parameter": ["190"]},
    "22": {"name": "Pufferspeicher", "parameter": ["215"]},
    "25": {"name": "PPS-Bus", "parameter": ["15000"]},
    "16": {"name": "", "parameter": ["180"]},
}, "parameter": {}}
g = {gr["titel"]: [k["name"] for k in gr["kategorien"]] for gr in katalog.gruppen(MENUE)}
pruefe(g["Heizen"] == ["Heizkreis"], "der Heizkreis gehoert zum Heizen")
pruefe(g["Trinkwasser"] == ["Warmwasser"], "Warmwasser ist Trinkwasser")
pruefe(g["Wärmeerzeuger"] == ["Kessel"], "der Kessel erzeugt Waerme")
pruefe(g["Speicher"] == ["Pufferspeicher"], "der Puffer speichert")
pruefe(g["Wartung & Diagnose"] == ["IO-Test"],
       "der IO-Test ist Diagnose und nicht Konfiguration")
pruefe(g["Anlage & Konfiguration"] == ["Uhrzeit"], "die Uhrzeit ist Konfiguration")
pruefe(g["Zeitprogramme"] == ["Zeitschaltprogramm 1"], "Schaltzeiten zusammen")
pruefe(g["BSB-LAN selbst"] == ["PPS-Bus"],
       "was jenseits von 10000 liegt, gehoert dem Adapter")
pruefe(g["Weitere"] == ["Kategorie 16"],
       "eine namenlose Kategorie faellt nicht unter den Tisch")
alle = sum(len(v) for v in g.values())
pruefe(alle == len(MENUE["kategorien"]),
       f"jede Kategorie kommt genau einmal vor ({alle})")

# Eine Standard-BSB-Anlage heisst ihre Kategorien anders.
FREMDMENUE = {"kategorien": {
    "3":  {"name": "Zeitprogramm Heizkreis 1", "parameter": ["500"]},
    "5":  {"name": "Ferien Heizkreis 1", "parameter": ["640"]},
    "6":  {"name": "Heizkreis 1", "parameter": ["700"]},
    "10": {"name": "Trinkwasser", "parameter": ["1600"]},
    "16": {"name": "Feuerungsautomat", "parameter": ["2700"]},
    "23": {"name": "Fehler", "parameter": ["6800"]},
    "26": {"name": "Ein-/Ausgangstest", "parameter": ["7700"]},
}, "parameter": {}}
fg = {gr["titel"]: [k["name"] for k in gr["kategorien"]] for gr in katalog.gruppen(FREMDMENUE)}
pruefe(fg["Heizen"] == ["Ferien Heizkreis 1", "Heizkreis 1"],
       "Ferien und Heizkreis einer fremden Anlage landen beim Heizen")
pruefe(fg["Trinkwasser"] == ["Trinkwasser"], "Trinkwasser heisst dort so")
pruefe(fg["Wärmeerzeuger"] == ["Feuerungsautomat"], "der Feuerungsautomat erzeugt")
pruefe(sorted(fg["Wartung & Diagnose"]) == ["Ein-/Ausgangstest", "Fehler"],
       "Fehler und Ausgangstest sind Diagnose")

print("\n=== Gemerkte Werte ===")
# Der Zwischenspeicher gab es schon - er lag nur brach. Wichtig ist, dass ein
# Wert seinen Zeitstempel traegt: Ohne den kann die Oberflaeche nicht sagen,
# wie alt das ist, was sie zeigt, und ein alter Wert saehe aus wie ein frischer.
pruefe(store.standard_einstellungen()["werte_merken"] is False,
       "ab Werk aus - niemand kennt die fremde Anlage")
e = store.validate_einstellungen({"bsb_url": "http://x", "werte_merken": "ja"})
pruefe(e["werte_merken"] is True, "und laesst sich einschalten")

store.save_config({"einstellungen": dict(store.standard_einstellungen(),
                                         bsb_url="http://kessel.test"),
                   "auswahl": []})
store.save_state({"werte": {}, "letzter_lauf": None, "veroeffentlicht": []})
ANLAGE["abfragen"].clear()
import app as anwendung
ergebnis = anwendung._lesen(nummern=["50", "55"])
gemerkt = store.load_state()["werte"]
pruefe(set(gemerkt) == {"50", "55"}, "was auf Zuruf gelesen wird, bleibt gespeichert")
pruefe(bool(gemerkt["50"].get("zeit")), "und traegt den Zeitpunkt, zu dem es galt")
pruefe(ergebnis.get("gelesen") == 2, "die Runde meldet, wie viele sie holte")

# Beim naechsten Oeffnen liegt es da, ohne dass der Bus angefasst wird.
ANLAGE["abfragen"].clear()
pruefe(set(store.load_state()["werte"]) == {"50", "55"} and ANLAGE["abfragen"] == [],
       "das blosse Nachschlagen belegt den Bus nicht")

print("\n=== Welches Programm laeuft ===")
# Die Regelung fuehrt drei Heizprogramme, aktiv ist eines. Die Wahl steckt in
# einem gewoehnlichen Parameter - bei Sven in der 70, deren Name in der
# Parameterliste schlicht falsch ist ("Brauchwassertemperatur-Reduziert-
# sollwert"). Die Auswahlwerte verraten die Wahrheit, nicht der Name.
WAHL = {"kategorien": {"7": {"name": "Betriebsart", "parameter": ["70"]}},
        "parameter": {"70": {"nr": "70", "name": "Brauchwassertemperatur-Reduziertsollwert",
                             "schreibbar": True, "possibleValues": [
                                 {"enumValue": "0", "desc": "Standby"},
                                 {"enumValue": "1", "desc": "Programm 3"},
                                 {"enumValue": "2", "desc": "Programm 2"},
                                 {"enumValue": "3", "desc": "Programm 1"},
                                 {"enumValue": "6", "desc": "Sommer"}]}}}
pw = katalog.programmwahl(WAHL)
pruefe(pw["nr"] == "70", "die Programmwahl wird an ihren Werten erkannt, nicht am Namen")
pruefe(pw["zu"] == {"3": "1", "2": "2", "1": "3"},
       "und die Zuordnung ist verdreht - Programm 1 ist der Wert 3")
pruefe(len(pw["werte"]) == 5, "die ganze Auswahl faehrt mit, auch Standby und Sommer")
pruefe(pw["schreibbar"] is True, "stellbar - man muss nicht an den Kessel laufen")

# Ein einzelnes "Warmwasserprogramm" ist keine Wahl zwischen Programmen.
EINZELN = {"kategorien": {"14": {"name": "Warmwasser", "parameter": ["160"]}},
           "parameter": {"160": {"nr": "160", "name": "Warmwasser-Mode",
                                 "possibleValues": [
                                     {"enumValue": "0", "desc": "24h/Tag"},
                                     {"enumValue": "2", "desc": "Warmwasserprogramm"}]}}}
pruefe(katalog.programmwahl(EINZELN) == {},
       "eine einzelne Erwaehnung wird nicht fuer eine Programmwahl gehalten")
pruefe(katalog.programmwahl({"parameter": {}}) == {},
       "und wo es nichts gibt, wird nichts behauptet")

print("\n=== Das Trinkwasserprogramm haengt an einem anderen Schalter ===")
# Nicht an der Programmwahl, sondern an "Warmwasser-Mode": Nur wenn dort
# "Warmwasserprogramm" steht, gilt die Wochentabelle. Die Falle: Auch die
# Zirkulationspumpe kennt den Wert "Warmwasserprogramm" - sie schaltet aber
# die Pumpe. Der Unterschied steckt im Namen des Parameters.
TWW = {"kategorien": {}, "parameter": {
    "160": {"nr": "160", "name": "Warmwasser-Mode", "schreibbar": True,
            "possibleValues": [{"enumValue": "0", "desc": "24h/Tag"},
                               {"enumValue": "1", "desc": "Heizprogramme mit Vorverlegung"},
                               {"enumValue": "2", "desc": "Warmwasserprogramm"}]},
    "178": {"nr": "178", "name": "Funktion Zirkulationspumpe", "schreibbar": True,
            "possibleValues": [{"enumValue": "0", "desc": "Warmwasser-Mode"},
                               {"enumValue": "1", "desc": "Warmwasserprogramm"}]}}}
tw = katalog.trinkwasserwahl(TWW)
pruefe(tw["nr"] == "160", "der Warmwasser-Mode wird gefunden")
pruefe(tw["programm"] == "2", "und der Wert, bei dem das Programm gilt")
NUR_PUMPE = {"kategorien": {}, "parameter": {"178": TWW["parameter"]["178"]}}
pruefe(katalog.trinkwasserwahl(NUR_PUMPE) == {},
       "die Zirkulationspumpe allein wird nicht dafuer gehalten")

print("\n=== BSB-LANs eigene Einstellungen ===")
# /JL liefert bei 5.1.18 kaputtes JSON: ein leerer Wert bleibt unbeendet.
# Wer daran scheitert, verliert die ganze Auskunft - also flicken.
class Text:
    def __init__(self, t): self.text, self.status_code = t, 200
    def raise_for_status(self): pass
    def json(self): return {}

KAPUTT = '''{
  "45": {
    "parameter": 27,
    "category": "OneWire",
    "name": "Pins",
    "value": "
  },
  "34": {
    "parameter": 14,
    "category": "Logging",
    "name": "Parameter",
    "value": "8700,8310"
  }
}'''
alt_get = bsb.requests.get
bsb.requests.get = lambda url, timeout=None: Text(KAPUTT)
konf = client.konfiguration()
bsb.requests.get = alt_get
pruefe(konf["34"]["value"] == "8700,8310",
       "der unbeendete Wert kostet nicht die ganze Antwort")
pruefe(konf["45"]["value"] == "", "und wird als das gelesen, was er ist: leer")

# Die Optionsnummern aus /JL sind nicht die Feldnamen der Weboberflaeche:
# Der Log-Modus ist Option 53, die 11 sind die Bustelegramme. Einmal
# verwechselt - und die App meldete "BSB-LAN sendet nichts", waehrend es sandte.
pruefe(anwendung.BSBLAN_OPTIONEN.get(53) == "logmodus",
       "der Log-Modus ist Option 53")
pruefe(11 not in anwendung.BSBLAN_OPTIONEN,
       "und Option 11 - die Bustelegramme - wird nicht dafuer gehalten")
pruefe(12 & anwendung.LOGMODUS_MQTT == anwendung.LOGMODUS_MQTT,
       "Log-Modus 12 heisst: an MQTT senden")
pruefe(8 & anwendung.LOGMODUS_MQTT == 0,
       "Log-Modus 8 allein heisst es nicht")

print("\n=== Was ausgeblendet werden darf ===")
e = store.validate_einstellungen({"bsb_url": "http://x", "versteckte_kategorien": ["25", "26", "25"]})
pruefe(e["versteckte_kategorien"] == ["25", "26"], "doppelt genannt zaehlt einmal")
pruefe(store.standard_einstellungen()["versteckte_kategorien"] == [],
       "ab Werk ist nichts ausgeblendet")
try:
    store.validate_einstellungen({"bsb_url": "http://x", "versteckte_kategorien": "25"})
    pruefe(False, "eine Zeichenkette statt einer Liste wird abgelehnt")
except store.ValidationError:
    pruefe(True, "eine Zeichenkette statt einer Liste wird abgelehnt")

print("\n=== Was die Anlage nicht liefert ===")
# An Svens Kessel gefunden: Parameter 116 "Vorlauftemperatur" antwortet mit
# error 7 ("parameter not supported") - die Anlage hat keinen Vorlauffuehler.
# 117 "Ruecklauftemperatur" antwortet mit "---": Parameter da, Klemme leer.
# Beides als Zeichenkette an Home Assistant zu melden, macht aus einem
# Temperatursensor eine kaputte Entitaet.
import mqtt_publisher as mq
pruefe(mq.ohne_wert({"value": "", "error": 7}), "error 7 heisst: kennt die Anlage nicht")
pruefe(mq.ohne_wert({"value": "---", "error": 0}), "--- heisst: keine Klemme belegt")
pruefe(mq.ohne_wert({}), "und gar keine Antwort erst recht")
pruefe(not mq.ohne_wert({"value": "52.7", "error": 0}), "eine Zahl ist eine Zahl")
pruefe(not mq.ohne_wert({"value": "0", "error": 0}), "die Null auch - sie ist kein Nichts")

class Sammler(mq.Publisher):
    def __init__(self):
        self.gesendet = {}
        self.praefix = self.basis = "heizungsanlage"
        self.verfuegbarkeit = "heizungsanlage/availability"
    def _publish(self, topic, payload):
        self.gesendet[topic] = payload

sam = Sammler()
sam.werte([{"nr": "116"}, {"nr": "115"}],
          {"116": {"value": "", "error": 7}, "115": {"value": "52.7", "error": 0}})
pruefe(sam.gesendet["heizungsanlage/p116/state"] == "None",
       "der fehlende Vorlauf wird zu None und damit zu 'unbekannt'")
pruefe(sam.gesendet["heizungsanlage/p115/state"] == "52.7",
       "der Kessel meldet seinen Wert")

# Die Kachel-Nutzlast traegt den Datentyp mit: Ohne ihn kann die Oberflaeche
# nicht sagen, was ein leerer Wert bedeutet.
kachel = katalog.kacheln(k)[0]
pruefe("dataType_name" in kachel and "schreibbar" in kachel,
       "eine Kachel weiss, was fuer ein Parameter sie zeigt")

print("\n=== Zwei Schreiber, eine Datei ===")
# Der Fehler, der das ausgeloest hat: Der Takt laedt den Zustand, liest vier
# Sekunden lang ueber den Bus und schreibt dann seine Kopie zurueck - mitsamt
# allem, was inzwischen jemand anderes eingetragen hatte. Der Merker fuer die
# Geraetekennung ging so bei jedem Start verloren, und das Abraeumen der alten
# Entitaeten lief immer wieder von vorn.
store.save_state({"werte": {"50": {"value": "21"}}, "letzter_lauf": "frueher",
                  "veroeffentlicht": [], "geraet": "", "praefix": ""})
alte_kopie = store.load_state()          # was der Takt in der Hand haelt
store.merke_state(geraet="heizungsanlage", praefix="heizungsanlage")
# ... und jetzt schreibt der Takt, wie er es tut: nur seine eigenen Felder.
store.merke_state(werte=alte_kopie["werte"], letzter_lauf="jetzt")
danach = store.load_state()
pruefe(danach["geraet"] == "heizungsanlage",
       "der Merker ueberlebt den Takt, der gleichzeitig schreibt")
pruefe(danach["letzter_lauf"] == "jetzt", "und der Takt schreibt trotzdem sein Feld")

print("\n=== Eine Umbenennung räumt hinter sich auf ===")
# Discovery-Nachrichten sind "retained": Sie liegen im Broker, bis jemand sie
# ueberschreibt. Ohne Abraeumen stuenden nach einer Umbenennung zwei Geraete in
# Home Assistant - das alte fuer immer "nicht verfuegbar".
import mqtt_publisher

class StummerBroker(mqtt_publisher.Publisher):
    def __init__(self):
        self.gesendet = []
        self.praefix = self.basis = "heizungsanlage"
        self.verfuegbarkeit = "heizungsanlage/availability"

    def _publish(self, topic, payload):
        self.gesendet.append((topic, payload))

broker = StummerBroker()
broker.altes_geraet_abraeumen("kesselmanager", "kesselmanager", ["p72", "p115"])
themen = dict(broker.gesendet)
pruefe(themen.get("homeassistant/sensor/kesselmanager/p72/config") == "",
       "die alte Anmeldung wird mit leerer Nutzlast zurueckgenommen")
pruefe(themen.get("kesselmanager/p115/state") == "",
       "auch die alten Werte werden geraeumt")
pruefe(themen.get("kesselmanager/availability") == "",
       "und die Verfuegbarkeit des alten Geraets")
pruefe(all("heizungsanlage" not in t for t, _ in broker.gesendet),
       "das neue Geraet bleibt dabei unangetastet")
pruefe(mqtt_publisher.DEVICE_ID == "heizungsanlage",
       "die Kennung steht an einer Stelle und heisst heizungsanlage")

# Wer von der alten Fassung kommt, hat "kesselmanager" als Praefix gespeichert.
# Bliebe es stehen, schriebe das umbenannte Geraet seine Werte genau auf die
# Themen, die der Aufraeumer gerade leert.
store.save_config({"einstellungen": dict(store.standard_einstellungen(),
                                         praefix="kesselmanager"),
                   "auswahl": []})
pruefe(store.load_config()["einstellungen"]["praefix"] == "heizungsanlage",
       "das alte Praefix wandert beim Laden auf die neue Kennung")
store.save_config({"einstellungen": dict(store.standard_einstellungen(),
                                         praefix="eigenesthema"),
                   "auswahl": []})
pruefe(store.load_config()["einstellungen"]["praefix"] == "eigenesthema",
       "ein selbst gewaehltes Praefix bleibt unangetastet")

print("\n=== Einstellungen werden geprüft ===")
e = store.validate_einstellungen({"bsb_url": "192.168.1.50"})
pruefe(e["bsb_url"] == "http://192.168.1.50", "eine Adresse ohne Schema bekommt eins")
pruefe(store.standard_einstellungen()["schreiben_erlaubt"] is False,
       "ab Werk ist das Stellen gesperrt")
for feld, wert, was in (("intervall_s", 5, "ein zu kurzes Intervall"),
                        ("intervall_s", "bald", "ein unsinniges Intervall"),
                        ("bsb_url", "", "eine leere Adresse"),
                        ("praefix", "a b/c", "ein Präfix mit Sonderzeichen")):
    try:
        store.validate_einstellungen({feld: wert})
        pruefe(False, f"{was} wird abgelehnt")
    except store.ValidationError:
        pruefe(True, f"{was} wird abgelehnt")

print("\n=== Übernahme durch ein anderes Add-on ===")
# Der Heizungsplaner soll Sollwerte fuehren koennen. Das Add-on bleibt dabei
# eigenstaendig: ohne Eintrag aendert sich nichts, und was eingetragen ist,
# laesst sich wieder loesen.
pruefe(store.load_uebernahme() == {}, "ab Werk fuehrt niemand etwas")

quelle, eintrag = store.validate_uebernahme(
    {"quelle": "Heizungsplaner", "name": "Heizungsplaner",
     "hinweis": "Sollwerte kommen aus dem Wochenplan",
     "parameter": ["710", "712", "710"]})
pruefe(quelle == "heizungsplaner", "die Kennung wird kleingeschrieben")
pruefe(eintrag["parameter"] == ["710", "712"], "doppelte Nummern zaehlen einmal")
store.save_uebernahme({quelle: eintrag})

nach_nummer = store.uebernommen_von(store.load_uebernahme())
pruefe(nach_nummer["710"]["name"] == "Heizungsplaner",
       "zu jeder Nummer laesst sich nachschlagen, wer sie fuehrt")
pruefe("711" not in nach_nummer, "was niemand angemeldet hat, bleibt frei")

# Zwei Quellen auf demselben Parameter sind ein Versehen - aber ein stiller
# Wechsel waere schlimmer als eine feste Regel.
store.save_uebernahme({"a": {"name": "A", "parameter": ["710"], "zeit": ""},
                       "b": {"name": "B", "parameter": ["710"], "zeit": ""}})
pruefe(store.uebernommen_von(store.load_uebernahme())["710"]["quelle"] == "a",
       "bei zwei Anmeldungen gilt die erste")

for falsch, was in (({"quelle": "", "parameter": []}, "eine Anmeldung ohne Quelle"),
                    ({"quelle": "a b", "parameter": []}, "eine Quelle mit Leerzeichen"),
                    ({"quelle": "gut", "parameter": "710"}, "eine Parameterliste, die keine ist")):
    try:
        store.validate_uebernahme(falsch)
        pruefe(False, f"{was} wird abgelehnt")
    except store.ValidationError:
        pruefe(True, f"{was} wird abgelehnt")

store.save_uebernahme({})
pruefe(store.load_uebernahme() == {}, "und das Aufheben raeumt wieder alles weg")

print("\n=== Die Auswahl wird geprüft ===")
a = store.validate_auswahl([{"nr": "50", "name": "X"}, {"nr": "50", "name": "X"}])
pruefe(len(a) == 1, "ein doppelt angehakter Parameter zählt einmal")
try:
    store.validate_auswahl([{"name": "ohne Nummer"}])
    pruefe(False, "ein Eintrag ohne Parameternummer wird abgelehnt")
except store.ValidationError:
    pruefe(True, "ein Eintrag ohne Parameternummer wird abgelehnt")

print("\n=== Die Schnittstelle, so wie der Planer sie ruft ===")
# Bis hierher waren es Bausteine. Jetzt die Wege selbst - mit Flasks
# Testkunden, ohne Netz, ohne laufendes Add-on.
store.save_uebernahme({})
store.save_config({"einstellungen": dict(store.standard_einstellungen(),
                                         bsb_url="http://kessel.test",
                                         schreiben_erlaubt=True),
                   "auswahl": []})
store.save_katalog(k)
import app as anwendung
anwendung._client.cache_clear() if hasattr(anwendung._client, "cache_clear") else None
kunde = anwendung.app.test_client()

antwort = kunde.get("/api/uebernahme")
pruefe(antwort.get_json() == {"quellen": {}, "parameter": {}},
       "ohne Eintrag fuehrt niemand etwas")

antwort = kunde.put("/api/uebernahme", json={
    "quelle": "heizungsplaner", "name": "Heizungsplaner",
    "hinweis": "Sollwerte aus dem Wochenplan", "parameter": ["50"]})
pruefe(antwort.status_code == 200
       and antwort.get_json()["parameter"]["50"]["quelle"] == "heizungsplaner",
       "der Planer meldet an, was er fuehrt")

ANLAGE["gesetzt"].clear()
antwort = kunde.post("/api/setzen", json={"nr": "50", "wert": "21.0"})
pruefe(antwort.status_code == 409, "von Hand wird der Parameter nicht gestellt")
pruefe("Heizungsplaner" in antwort.get_json()["fehler"],
       "und die Meldung nennt den, der ihn fuehrt")
pruefe(ANLAGE["gesetzt"] == [], "es ging auch wirklich nichts an den Bus")

antwort = kunde.post("/api/setzen",
                     json={"nr": "50", "wert": "21.0", "quelle": "heizungsplaner"})
pruefe(antwort.status_code == 200, "der Planer selbst darf schreiben")
pruefe(ANLAGE["gesetzt"][-1]["Parameter"] == "50", "und der Wert geht an den Bus")

antwort = kunde.post("/api/setzen", json={"nr": "55", "wert": "55"})
pruefe(antwort.status_code == 200,
       "ein nicht uebernommener Parameter bleibt frei stellbar")

antwort = kunde.delete("/api/uebernahme/heizungsplaner")
pruefe(antwort.get_json() == {"quellen": {}, "parameter": {}},
       "die Uebernahme laesst sich aufheben - das Add-on bleibt eigenstaendig")
antwort = kunde.post("/api/setzen", json={"nr": "50", "wert": "21.0"})
pruefe(antwort.status_code == 200, "danach stellt man wieder selbst")

# Eine leere Liste ist die Abmeldung: Das Aufraeumen soll ein Aufruf sein.
kunde.put("/api/uebernahme", json={"quelle": "x", "parameter": ["50"]})
kunde.put("/api/uebernahme", json={"quelle": "x", "parameter": []})
pruefe(kunde.get("/api/uebernahme").get_json()["quellen"] == {},
       "eine leere Liste meldet ab")
store.save_uebernahme({})

print("\n=== BSB-LAN meldet, der Manager richtet ein ===")
# Der Weg, um den es geht: Das Add-on liest BSB-LANs Einstellungen, aendert
# nur das Noetige und laesst das Geraet senden. Zugangsdaten kommen vom
# Supervisor - niemand tippt ein Passwort ab, und keines wird gespeichert.
KONFIG = {
  "32": {"parameter": 53, "category": "Logging", "name": "Log-Modus", "value": "1"},
  "33": {"parameter": 13, "category": "Logging", "name": "Logintervall", "value": "30"},
  "34": {"parameter": 14, "category": "Logging", "name": "Parameter", "value": "8700"},
  "37": {"parameter": 36, "category": "MQTT", "name": "Broker", "value": "alt:1883"},
  "38": {"parameter": 37, "category": "MQTT", "name": "Username", "value": "wer"},
  "39": {"parameter": 38, "category": "MQTT", "name": "Passwort", "value": "altespw"},
  "40": {"parameter": 40, "category": "MQTT", "name": "Geraete-ID", "value": ""},
  "41": {"parameter": 39, "category": "MQTT", "name": "Topic", "value": "ALT"},
  "42": {"parameter": 59, "category": "MQTT", "name": "Discovery", "value": "0"},
  "43": {"parameter": 35, "category": "MQTT", "name": "Verwenden", "value": "1"},
  "44": {"parameter": 58, "category": "MQTT", "name": "Einheiten", "value": "0"},
}
GERAET = {"konfig": json.loads(json.dumps(KONFIG)), "geschrieben": [], "befehle": []}

class JLAntwort:
    def __init__(self): self.status_code = 200
    @property
    def text(self): return json.dumps(GERAET["konfig"])
    def raise_for_status(self): pass
    def json(self): return {}

_alt_get, _alt_post = bsb.requests.get, bsb.requests.post
def _get2(url, timeout=None):
    if url.endswith("/JL"):
        return JLAntwort()
    if "/M" in url and "!" in url:
        GERAET["befehle"].append(url.rsplit("/", 1)[1])
        return JLAntwort()
    if url.rsplit("/", 1)[-1] in ("N", "NE"):
        GERAET["neustart"] = url.rsplit("/", 1)[-1]
        return JLAntwort()
    return _get(url, timeout)
def _post2(url, json=None, timeout=None):
    if url.endswith("/JW"):
        GERAET["geschrieben"].append(json)
        for k, v in (json or {}).items():
            GERAET["konfig"][k]["value"] = v["value"]
        return JLAntwort()
    return _post(url, json=json, timeout=timeout)
bsb.requests.get, bsb.requests.post = _get2, _post2

# Eine IP, wie der Supervisor sie auf einem Rechner mit eigenem Broker nennt.
# Der Docker-Name „core-mosquitto“ kommt weiter unten dran – er ist der Fall,
# der BSB-LAN einmal stumm gemacht hat.
os.environ["MQTT_HOST"] = "192.168.1.222"
os.environ["MQTT_PORT"] = "1883"
os.environ["MQTT_USER"] = "ha"
os.environ["MQTT_PASSWORD"] = "geheim"
store.save_config({"einstellungen": dict(store.standard_einstellungen(),
                                         bsb_url="http://kessel.test",
                                         melder="bsblan", bsblan_praefix="HEIZUNG",
                                         bsblan_intervall_s=60),
                   "auswahl": [{"nr": "50", "name": "X"}, {"nr": "72", "name": "Y"}]})

# Der Fehler, der zweimal passiert ist: Ein Name, den das Einrichten setzen
# will, fehlt in der Optionszuordnung - und wird stillschweigend uebersprungen.
# Erst traf es Benutzer und Passwort, dann die Einheiten.
bekannt = set(anwendung.BSBLAN_OPTIONEN.values())
fehlend = [n for n in anwendung.BSBLAN_SOLL_NAMEN if n not in bekannt]
pruefe(not fehlend, f"jede Einstellung hat eine Optionsnummer (fehlt: {fehlend})")

antwort = kunde.post("/api/bsblan/einrichten").get_json()
pruefe(antwort.get("offen") == [], f"alles kam an: {antwort}")
pruefe(GERAET["konfig"]["37"]["value"] == "192.168.1.222:1883",
       "der Broker kommt von Home Assistant, nicht aus einem Formular")
pruefe(GERAET["konfig"]["41"]["value"] == "HEIZUNG", "das Praefix aus den Einstellungen")
pruefe(GERAET["konfig"]["42"]["value"] == "1", "Auto-Discovery wird eingeschaltet")
pruefe(GERAET["konfig"]["33"]["value"] == "60", "und das Intervall gesetzt")
pruefe(GERAET["konfig"]["44"]["value"] == "1",
       "die Einheiten werden auf die von Home Assistant gestellt")
# 1 = auf SD-Karte schreiben. Das darf das Einrichten nicht abschalten.
pruefe(int(GERAET["konfig"]["32"]["value"]) & 1 == 1,
       "was das Geraet sonst tut, bleibt unangetastet")
pruefe(int(GERAET["konfig"]["32"]["value"]) & 4 == 4, "senden ist eingeschaltet")
# Der Fehler, der das Schreiben lautlos wirkungslos machte: BSB-LAN nimmt nur
# "parameter" und "value". Wer den ganzen Eintrag aus /JL zurueckgibt, bekommt
# eine leere Antwort und keine Aenderung - ohne jede Fehlermeldung.
for stapel in GERAET["geschrieben"]:
    for eintrag in stapel.values():
        pruefe(set(eintrag) == {"parameter", "value"},
               f"nur parameter und value gehen raus, nicht {sorted(eintrag)}")
        break
    break
gesendet = json.dumps(GERAET["geschrieben"])
pruefe("geheim" in gesendet and GERAET["konfig"]["39"]["value"] == "geheim",
       "das Passwort geht an das Geraet ...")
pruefe(GERAET["konfig"]["38"]["value"] == "ha", "der Benutzer ebenso")
antwort_text = json.dumps(antwort)
pruefe("geheim" not in antwort_text and "altespw" not in antwort_text,
       "... aber nicht in die Rueckmeldung")
pruefe("Zugangsdaten" in antwort["geschrieben"]
       and "mqtt_passwort" not in antwort_text,
       "sie werden nur als \"Zugangsdaten\" gemeldet")

antwort = kunde.put("/api/bsblan/parameter").get_json()
pruefe(GERAET["konfig"]["34"]["value"] == "50,72",
       "die Auswahl steht jetzt als Log-Liste im Geraet")
# Die Reihenfolge ist keine Kosmetik: BSB-LAN widerruft nur, was es gerade
# fuehrt. Erst die Liste zu aendern hiesse, die neuen Eintraege zu widerrufen
# und fuer jeden entfernten Parameter eine Karteileiche zu hinterlassen.
pruefe(GERAET["befehle"] == ["M0!0", "M1!0"],
       f"abmelden, aendern, anmelden - in dieser Reihenfolge ({GERAET['befehle']})")
pruefe(antwort["vollstaendig"] is True, "und wird zurueckgelesen statt geglaubt")

# Der umgekehrte Weg.
GERAET["konfig"]["34"]["value"] = "50,55,72"
uebernommen = kunde.post("/api/bsblan/uebernehmen").get_json()
pruefe([e["nr"] for e in uebernommen] == ["50", "55", "72"],
       "BSB-LANs eigene Liste laesst sich uebernehmen")
pruefe(uebernommen[0]["name"] == "Raumtemperatur Komfortsollwert",
       "mit den Namen aus dem Katalog")

# Der Fehler, der eine Anlage 50 Minuten lang stumm gemacht hat: Der Supervisor
# nennt dem Add-on „core-mosquitto“ – ein Name aus dem Docker-Netz. Für einen
# ESP32 im Hausnetz ist er nicht auflösbar. Lieber nichts schreiben als eine
# unerreichbare Adresse: Was im Gerät steht, funktioniert wenigstens.
os.environ["MQTT_HOST"] = "core-mosquitto"
GERAET["konfig"]["37"]["value"] = "192.168.1.222:1883"
GERAET["konfig"]["38"]["value"] = "ha"
antwort = kunde.post("/api/bsblan/einrichten").get_json()
pruefe(GERAET["konfig"]["37"]["value"] == "192.168.1.222:1883",
       "ein Docker-Name ersetzt keine erreichbare Broker-Adresse")
pruefe(GERAET["konfig"]["38"]["value"] == "ha",
       "und die Zugangsdaten bleiben dann auch stehen")
pruefe("hinweis" in antwort, f"das sagt die Rueckmeldung auch: {antwort.get('hinweis')}")
pruefe(anwendung.broker_fuer_bsblan() == "",
       "ohne Supervisor und ohne IP gibt es keine Adresse")
os.environ["MQTT_HOST"] = "192.168.1.222"
pruefe(anwendung.broker_fuer_bsblan() == "192.168.1.222:1883",
       "eine IP wird unveraendert durchgereicht")

# Der eigene Takt je Parameter: Frederiks Rat, nicht alles gleich oft zu holen.
gespeichert = kunde.put("/api/auswahl", json=[
    {"nr": "115", "name": "Kessel", "takt_s": 60},
    {"nr": "72", "name": "Stunden"}]).get_json()
takte = {e["nr"]: e.get("takt_s") for e in gespeichert}
pruefe(takte.get("115") == 60 and takte.get("72") == 0,
       f"ein eigener Takt wird gespeichert, ohne Angabe gilt der Grundtakt: {takte}")
antwort = kunde.put("/api/auswahl", json=[{"nr": "115", "name": "K", "takt_s": 5}])
pruefe(antwort.status_code == 400, "ein Takt von fünf Sekunden wird abgelehnt")

# Abgefragt wird über MQTT, und zwar ohne retain: Ein liegengebliebener
# Abfragebefehl würde den Bus bei jedem Verbindungsaufbau erneut belasten.
class _Klient:
    def __init__(self): self.gesendet = []
    def publish(self, topic, payload, retain=False):
        self.gesendet.append((topic, payload, retain))

import mqtt_publisher
melder = mqtt_publisher.Publisher.__new__(mqtt_publisher.Publisher)
melder._client = _Klient()
melder.connected = threading.Event(); melder.connected.set()
melder.abfragen("BSBLAN", ["115", "72"])
pruefe(melder._client.gesendet == [("BSBLAN/poll", "115,72", False)],
       f"die Abfrage geht an BSBLAN/poll, ohne retain: {melder._client.gesendet}")
melder.abfragen("BSBLAN", [])
pruefe(len(melder._client.gesendet) == 1, "ohne faellige Parameter geht nichts raus")

# Der Zustand, der wie „läuft“ aussieht: BSB-LAN antwortet auf HTTP, hat aber
# den MQTT-Teil nie gestartet. Sein Zustandsthema verrät es.
class _Nachricht:
    def __init__(self, topic, nutz): self.topic, self.payload = topic, nutz

lauscher = mqtt_publisher.Publisher.__new__(mqtt_publisher.Publisher)
lauscher._client = _Klient()
lauscher._client.subscribe = lambda t: None
lauscher._client.unsubscribe = lambda t: None
lauscher.connected = threading.Event(); lauscher.connected.set()
lauscher._horcht = ""
lauscher._horcht_werte = ""
lauscher._horcht_discovery = ""
lauscher.fremde_discovery = {}
lauscher.fremde_werte = {}
lauscher.auf_wert = None
lauscher.fremd_stand = {"topic": "", "wert": "", "zeit": 0.0}
lauscher.horchen("BSBLAN/status")
anwendung._publisher = lauscher
pruefe(anwendung.bsblan_meldet() is None, "ohne Nachricht wird nichts behauptet")
lauscher._nachricht(None, None, _Nachricht("BSBLAN/status", b"online"))
pruefe(anwendung.bsblan_meldet() is True, "„online“ heisst: es meldet")
lauscher._nachricht(None, None, _Nachricht("BSBLAN/status", b"offline"))
pruefe(anwendung.bsblan_meldet() is False, "„offline“ ist die Auskunft, auf die es ankommt")
lauscher._nachricht(None, None, _Nachricht("BSBLAN/anderes", b"online"))
pruefe(anwendung.bsblan_meldet() is False, "andere Themen aendern daran nichts")
anwendung._publisher = None

# Die Erreichbarkeit ist eine eigene Entitaet - sie sagt nichts ueber die
# Heizung, sondern ueber die Verbindung zu ihr, und darum meldet der Manager
# sie auch dann, wenn BSB-LAN das Melden uebernommen hat.
melder2 = mqtt_publisher.Publisher.__new__(mqtt_publisher.Publisher)
melder2._client = _Klient()
melder2.connected = threading.Event(); melder2.connected.set()
melder2.basis = "heizungsanlage"
melder2.verfuegbarkeit = "heizungsanlage/availability"
melder2.erreichbarkeit_anmelden({})
melder2.erreichbarkeit(False)
themen = [t for t, _, _ in melder2._client.gesendet]
pruefe(any(t.endswith("binary_sensor/heizungsanlage/bsblan_erreichbar/config")
           for t in themen), f"die Entitaet wird angemeldet: {themen}")
anmeldung = json.loads(melder2._client.gesendet[0][1])
pruefe(anmeldung.get("device_class") == "connectivity"
       and anmeldung.get("availability_topic") == "heizungsanlage/availability",
       "als Verbindungssensor, der mit dem Add-on verschwindet")
pruefe(melder2._client.gesendet[-1][1] == "OFF",
       "und ihr Zustand geht als OFF hinaus, wenn nichts antwortet")

melder2._client.gesendet.clear()
melder2.sendet_anmelden({}); melder2.sendet(False)
themen2 = [t for t, _, _ in melder2._client.gesendet]
pruefe(any(t.endswith("binary_sensor/heizungsanlage/bsblan_meldet/config")
           for t in themen2), "auch „meldet“ ist eine eigene Entitaet")
melder2._client.gesendet.clear()
melder2.sendet_abmelden()
pruefe([n for _, n, _ in melder2._client.gesendet] == ["", ""],
       "und sie verschwindet, wenn der Manager selbst meldet")

# Der Meldeweg gehoert in die Einstellungen, nicht in eine Automation.
gesendet = []
anwendung.ha_notify = lambda dienst, titel, text: gesendet.append((dienst, titel)) or True
store.save_config({"einstellungen": dict(store.load_config()["einstellungen"],
                                         melden_an=["notify.test"],
                                         melden_nach_min=10),
                   "auswahl": store.load_config()["auswahl"]})

anwendung._stoerung_melden("weg", False, None)
pruefe(gesendet == [], "vor Ablauf der Wartezeit wird nichts gemeldet")
lage = store.load_state()["stoerung"]
store.merke_state(stoerung=dict(lage, seit=lage["seit"] - 601))
anwendung._stoerung_melden("weg", False, None)
pruefe(len(gesendet) == 1 and "antwortet nicht" in gesendet[0][1],
       f"nach der Wartezeit genau einmal: {gesendet}")
anwendung._stoerung_melden("weg", False, None)
pruefe(len(gesendet) == 1, "und kein zweites Mal fuer dieselbe Stoerung")
anwendung._stoerung_melden("", True, True)
pruefe(len(gesendet) == 2 and "zurueck" in gesendet[1][1].replace("ü", "ue"),
       f"die Entwarnung kommt hinterher: {gesendet}")
anwendung._stoerung_melden("", True, True)
pruefe(len(gesendet) == 2, "aber nur einmal")

# Was die Uebersicht braucht, ergaenzt der Manager beim Speichern selbst -
# sonst bliebe seine Startseite leer, weil BSB-LAN nur meldet, was in seiner
# Liste steht. Ein Parameter, den die Anlage nicht beantwortet, wird dabei
# nicht erzwungen: Er waere eine ewig leere Entitaet.
kachel_nummern = [x["nr"] for x in katalog.kacheln(store.load_katalog())]
pruefe(bool(kachel_nummern), f"die Uebersicht kennt Kacheln: {kachel_nummern}")
store.merke_state(werte={kachel_nummern[0]: {"value": "---", "error": 7}})
pflicht = anwendung.pflicht_nummern()
pruefe(kachel_nummern[0] not in pflicht,
       "ein Parameter ohne Antwort wird nicht erzwungen")
# Eine Einstellung aendert sich nur, wenn jemand sie aendert - sie im
# Fuenfminutentakt zu erfragen waere Buszeit fuer nichts.
takte_pflicht = set(pflicht.values())
pruefe(takte_pflicht <= {anwendung.MINDESTTAKT_S, anwendung.MINDESTTAKT_STELLBAR_S},
       f"jede Pflichtkachel hat einen Mindesttakt: {pflicht}")
gespeichert = kunde.put("/api/auswahl", json=[{"nr": "999", "name": "Fremd"}]).get_json()
nummern = [e["nr"] for e in gespeichert]
pruefe(all(nr in nummern for nr in pflicht),
       f"die Pflichtparameter stehen danach in der Auswahl: {nummern}")
store.merke_state(werte={})

# Unter dem Praefix liegen auch Nachrichten frueherer Listen. Sie kommen beim
# Abonnieren alle auf einmal an und saehen dann taufrisch aus - uebernommen
# wird deshalb nur, was auch wirklich gemeldet wird.
class _Melder:
    fremde_werte = {"115": {"wert": "54.0", "zeit": time.time()},
                    "9999": {"wert": "alt", "zeit": time.time()}}

anwendung._publisher = _Melder()
kunde.put("/api/auswahl", json=[{"nr": "115", "name": "Kessel"}])
store.merke_state(werte={})
anwendung._werte_aus_mqtt()
gehoert = store.load_state()["werte"]
pruefe("115" in gehoert and gehoert["115"]["quelle"] == "mqtt",
       "ein gemeldeter Wert wird uebernommen")
pruefe("9999" not in gehoert,
       "eine Karteileiche unter demselben Praefix nicht")
anwendung._publisher = None

# Ob BSB-LAN schreiben laesst, steht in seiner Konfiguration - nicht in /JI.
# Dessen buswritable meldete auf Svens Anlage 0, waehrend Schreiben lief.
anwendung._schreib_stand.update({"zeit": 0.0, "frei": None})
GERAET["konfig"]["4"] = {"parameter": 33, "name": "Schreibzugriff (Ebene)",
                         "value": "2"}
pruefe(anwendung.bsblan_schreibt() is True, "Ebene 2 heisst: schreiben erlaubt")
anwendung._schreib_stand.update({"zeit": 0.0, "frei": None})
GERAET["konfig"]["4"]["value"] = "0"
pruefe(anwendung.bsblan_schreibt() is False, "Ebene 0 heisst: gesperrt")
pruefe(anwendung.bsblan_schreibt() is False, "und die Antwort wird gemerkt")

# Eine Kachel, die erst mit einer neuen Fassung dazukommt, stuende sonst als
# "nicht ausgewaehlt" auf der Uebersicht, bis jemand zufaellig speichert.
# Pflicht wird nur, was die Anlage auch beantwortet - also erst einen Stand
# hinterlegen, sonst gilt der Wert als unbekannt und wird nicht erzwungen.
store.merke_state(werte={nr: {"value": "1", "error": 0, "zeit": "2026-09-13T12:00:00"}
                         for nr in kachel_nummern})
config = store.load_config()
config["auswahl"] = [e for e in config["auswahl"]
                     if str(e["nr"]) not in anwendung.pflicht_nummern()]
store.save_config(config)
dazu = anwendung.pflicht_nachtragen()
pruefe(bool(dazu), f"fehlende Pflichtparameter werden im Betrieb nachgetragen: {dazu}")
pruefe(anwendung.pflicht_nachtragen() == [],
       "und beim zweiten Mal ist nichts mehr zu tun")

# Eigene Namen fuer Parameter, deren Beschriftung nicht zur Anlage passt.
antwort = kunde.put("/api/namen", json={"70": "Betriebsart", "71": "  "}).get_json()
pruefe(antwort["namen"] == {"70": "Betriebsart"},
       f"leere Namen fallen weg: {antwort['namen']}")
pruefe(store.load_config()["namen"] == {"70": "Betriebsart"},
       "und der Name steht in der Konfiguration")
kunde.put("/api/auswahl", json=[{"nr": "70", "name": "Brauchwasser..."}])
kunde.put("/api/namen", json={"70": "Betriebsart"})
eintrag = [e for e in store.load_config()["auswahl"] if e["nr"] == "70"][0]
pruefe(eintrag["anzeige"] == "Betriebsart",
       "die Entitaet heisst dann auch so")
zu_lang = kunde.put("/api/namen", json={"70": "x" * 61})
pruefe(zu_lang.status_code == 400, "ein zu langer Name wird abgelehnt")
kunde.put("/api/namen", json={})

# Meldet BSB-LAN, vergibt dessen Firmware die Namen der Entitaeten. Der
# Manager schreibt die Anmeldung mit derselben unique_id zurueck - nur der
# Name aendert sich, und der urspruengliche wird gemerkt.
melder3 = mqtt_publisher.Publisher.__new__(mqtt_publisher.Publisher)
melder3._client = _Klient()
melder3.connected = threading.Event(); melder3.connected.set()
melder3.basis = "heizungsanlage"
melder3.fremde_discovery = {
    "homeassistant/select/BSB-LAN/70-50-252-2120/config":
        json.dumps({"unique_id": "70-50-252-2120", "name": "00-07 Brauchwasser...",
                    "state_topic": "~/status"})}
anwendung._publisher = melder3
store.save_config(dict(store.load_config(), namen={"70": "Betriebsart"}))
geaendert = anwendung.discovery_aufbessern()
pruefe(geaendert == ["70"], f"die Anmeldung wird erneuert: {geaendert}")
neu_anmeldung = json.loads(melder3._client.gesendet[-1][1])
pruefe(neu_anmeldung["name"] == "Betriebsart"
       and neu_anmeldung["unique_id"] == "70-50-252-2120"
       and neu_anmeldung["state_topic"] == "~/status",
       "mit neuem Namen, aber sonst unveraendert")
# Und das, was BSB-LAN gar nicht mitschickt: das Verfuegbarkeitsthema. Ohne
# es bleibt jede Entitaet "verfuegbar", auch wenn der Adapter laengst weg ist.
praefix = store.load_config()["einstellungen"]["bsblan_praefix"]
pruefe(neu_anmeldung.get("avty_t") == f"{praefix}/status",
       f"und mit Verfuegbarkeitsthema: {neu_anmeldung.get('avty_t')}")
pruefe(anwendung.discovery_aufbessern() == [],
       "und beim zweiten Mal ist nichts mehr zu tun")
pruefe(store.load_state()["namen_original"]["70"].startswith("00-07"),
       "der Name der Firmware wird gemerkt")

# Wer den eigenen Namen loescht, bekommt den alten zurueck.
store.save_config(dict(store.load_config(), namen={}))
anwendung.discovery_aufbessern()
zurueck = json.loads(melder3._client.gesendet[-1][1])
pruefe(zurueck["name"].startswith("00-07"), "geloescht heisst: wieder wie vorher")

# Seit BSB-LAN 5.1.19 schickt die Firmware das Verfuegbarkeitsthema selbst
# mit - dann darf der Manager nicht die Kurzform danebenschreiben, das waere
# nach der Abkuerzungsaufloesung derselbe Schluessel zweimal.
melder3.fremde_discovery = {
    "homeassistant/sensor/BSB-LAN/115-50-252-2120/config":
        json.dumps({"unique_id": "115-50-252-2120", "name": "Kessel",
                    "availability_topic": f"{praefix}/status"})}
melder3._client.gesendet.clear()
pruefe(anwendung.discovery_aufbessern() == [],
       "was die Firmware selbst mitschickt, wird nicht doppelt gesetzt")
anwendung._publisher = None

# Die Legionellenaufheizung: hochsetzen, warten, zurueckstellen - und der
# Rueckweg steht im Zustand, bevor der Hinweg beginnt.
TW = {
    "55": {"name": "Trinkwassertemperatur-Nennsollwert", "unit": "°C",
           "dataType_name": "TEMP", "readwrite": 0, "possibleValues": []},
    "164": {"name": "Warmwassertemperatur-Nennsollwertmaximum", "unit": "°C",
            "dataType_name": "TEMP", "readwrite": 0, "possibleValues": []},
    "118": {"name": "Warmwassertemperatur-Istwert", "unit": "°C",
            "dataType_name": "TEMP", "readwrite": 2, "possibleValues": []},
}
PARAMETER["5"].update(TW)
alt_katalog = store.load_katalog()
store.save_katalog({"kategorien": {}, "parameter": {
    nr: dict(e, nr=nr, schreibbar=(e["readwrite"] == 0)) for nr, e in TW.items()}})

tw = katalog.trinkwasser_regelung(store.load_katalog())
pruefe(tw["sollwert"]["nr"] == "55" and tw["maximum"]["nr"] == "164"
       and tw["istwert"]["nr"] == "118",
       f"Sollwert, Obergrenze und Istwert werden aus dem Katalog erkannt: "
       f"{ {r: t['nr'] for r, t in tw.items()} }")
pruefe("reduziert" not in tw,
       "eine Anlage ohne Reduziertsollwert fuehrt keinen - und das ist kein "
       "Grund, die Aufheizung zu verweigern")

config = store.load_config()
config["einstellungen"] = dict(config["einstellungen"], schreiben_erlaubt=True)
store.save_config(config)
store.merke_state(legionellen_lauf={}, legionellen_letzter={})

ANLAGE["gesetzt"].clear()
anwendung.legionellen_starten(von_hand=True)
pruefe(anwendung.legionellen_lage()["phase"] == "laeuft", "die Aufheizung laeuft")
zurueck = store.load_state()["legionellen_lauf"]["zurueck"]
pruefe(zurueck == {"sollwert": "42", "maximum": "42"},
       f"der Rueckweg steht fest, bevor geschrieben wird: {zurueck}")
ziel = store.load_config()["einstellungen"]["legionellen"]["ziel"]
gesetzt = [(g["Parameter"], g["Value"]) for g in ANLAGE["gesetzt"]]
pruefe(gesetzt == [("164", f"{ziel:.1f}"), ("55", f"{ziel:.1f}")],
       f"erst die Obergrenze, dann der Sollwert: {gesetzt}")

ANLAGE["gesetzt"].clear()
anwendung.legionellen_beenden("von Hand beendet")
gesetzt = [(g["Parameter"], g["Value"]) for g in ANLAGE["gesetzt"]]
pruefe(gesetzt == [("55", "42"), ("164", "42")],
       f"und zurueck erst der Sollwert, dann die Grenze: {gesetzt}")
pruefe(store.load_state()["legionellen_letzter"]["ergebnis"] == "von Hand beendet",
       "der Lauf wird im Zustand vermerkt")
pruefe(not store.load_state()["legionellen_lauf"], "und der Lauf ist beendet")

# Mit Reduziertsollwert: Er gilt in der Absenkphase, und nur er. Wer ihn
# stehen laesst, heizt nachts vergeblich - die Regelung haelt seine 40 Grad,
# egal welcher Nennsollwert darueber steht.
TW_RED = {"162": {"name": "Warmwassertemperatur-Reduziertsollwert",
                  "unit": "°C", "dataType_name": "TEMP", "readwrite": 0,
                  "possibleValues": []}}
PARAMETER["5"].update(TW_RED)
store.save_katalog({"kategorien": {}, "parameter": {
    nr: dict(e, nr=nr, schreibbar=(e["readwrite"] == 0))
    for nr, e in {**TW, **TW_RED}.items()}})
tw = katalog.trinkwasser_regelung(store.load_katalog())
pruefe(tw.get("reduziert", {}).get("nr") == "162",
       f"der Reduziertsollwert wird erkannt: {tw.get('reduziert')}")
pruefe(tw["sollwert"]["nr"] == "55",
       "und er wird nicht mit dem Nennsollwert verwechselt")

store.merke_state(legionellen_lauf={}, legionellen_letzter={})
ANLAGE["gesetzt"].clear()
anwendung.legionellen_starten(von_hand=True)
zurueck = store.load_state()["legionellen_lauf"]["zurueck"]
pruefe(zurueck == {"sollwert": "42", "maximum": "42", "reduziert": "42"},
       f"auch fuer den Reduziertsollwert steht der Rueckweg fest: {zurueck}")
gesetzt = [(g["Parameter"], g["Value"]) for g in ANLAGE["gesetzt"]]
pruefe(gesetzt == [("164", f"{ziel:.1f}"), ("55", f"{ziel:.1f}"),
                   ("162", f"{ziel:.1f}")],
       f"Grenze, Nennsollwert, Reduziertsollwert - in dieser Reihenfolge: "
       f"{gesetzt}")

ANLAGE["gesetzt"].clear()
anwendung.legionellen_beenden("von Hand beendet")
gesetzt = [(g["Parameter"], g["Value"]) for g in ANLAGE["gesetzt"]]
pruefe(gesetzt == [("162", "42"), ("55", "42"), ("164", "42")],
       f"und zurueck in umgekehrter Reihenfolge: {gesetzt}")

# Ein Reduziertsollwert, den die Anlage nur lesen laesst, wird nicht
# angefasst - und haelt die Aufheizung trotzdem nicht auf.
store.save_katalog({"kategorien": {}, "parameter": {
    nr: dict(e, nr=nr, schreibbar=(nr != "162" and e["readwrite"] == 0))
    for nr, e in {**TW, **TW_RED}.items()}})
store.merke_state(legionellen_lauf={}, legionellen_letzter={})
ANLAGE["gesetzt"].clear()
anwendung.legionellen_starten(von_hand=True)
gesetzt = [g["Parameter"] for g in ANLAGE["gesetzt"]]
pruefe(gesetzt == ["164", "55"],
       f"ein nur lesbarer Reduziertsollwert wird uebergangen: {gesetzt}")
anwendung.legionellen_beenden("von Hand beendet")
store.save_katalog({"kategorien": {}, "parameter": {
    nr: dict(e, nr=nr, schreibbar=(e["readwrite"] == 0)) for nr, e in TW.items()}})
PARAMETER["5"].pop("162", None)

# Ein abgebrochener Lauf - etwa durch einen Neustart des Add-ons - wird beim
# naechsten Takt zurueckgestellt. Sonst bliebe der Speicher heiss.
store.merke_state(legionellen_lauf={"phase": "laeuft", "seit": 0,
                                    "zurueck": {"sollwert": "48", "maximum": "48"},
                                    "hoechster": None, "erreicht_seit": 0})
ANLAGE["gesetzt"].clear()
anwendung._legionellen_takt()
pruefe([g["Value"] for g in ANLAGE["gesetzt"]] == ["48", "48"],
       "ein abgebrochener Lauf wird zurueckgestellt")

config = store.load_config()
config["einstellungen"] = dict(config["einstellungen"], schreiben_erlaubt=False)
store.save_config(config)
try:
    anwendung.legionellen_starten()
    pruefe(False, "ohne Freigabe darf nichts geschrieben werden")
except bsb.BsbFehler:
    pruefe(True, "ohne Freigabe darf nichts geschrieben werden")

store.save_katalog(alt_katalog)
for nr in TW:
    PARAMETER["5"].pop(nr, None)

# Eine Bestaetigung fuer eine fremde Nummer ist keine Bestaetigung. BSB-LANs
# JSON-Leser unterscheidet Schluessel am ersten Buchstaben; wer zu viel
# mitschickt, bekommt eine Antwort fuer einen Parameter, den er nie nannte.
_alt_post3 = bsb.requests.post
def _post_falsch(url, json=None, timeout=None):
    return Antwort({"0": {"status": 1}})          # geantwortet wird fuer 0
bsb.requests.post = _post_falsch
try:
    client.setzen("39", "BSBLAN")
    pruefe(False, "eine Antwort fuer die falsche Nummer wird abgelehnt")
except bsb.BsbFehler as err:
    pruefe("gefragt war 39" in str(err),
           f"eine Antwort fuer die falsche Nummer wird abgelehnt: {err}")
def _post_leer(url, json=None, timeout=None):
    return Antwort({})
bsb.requests.post = _post_leer
try:
    client.setzen("39", "BSBLAN")
    pruefe(False, "und eine leere Antwort ebenso")
except bsb.BsbFehler:
    pruefe(True, "und eine leere Antwort ebenso")
def _post_komma(url, json=None, timeout=None):
    return Antwort({"39.0": {"status": 1}})       # dieselbe Nummer, anders geschrieben
bsb.requests.post = _post_komma
pruefe(client.setzen("39", "BSBLAN")["39.0"]["status"] == 1,
       "dieselbe Nummer in anderer Schreibweise gilt")
bsb.requests.post = _alt_post3

# Der Katalog traegt nach, was /JK nicht fuehrt - aber nur, was antwortet.
kat_test = {"kategorien": {"1": {"name": "Uhrzeit und Datum", "parameter": ["0"]}},
            "parameter": {"0": {"nr": "0"}}}
class _Client:
    def werte(self, nummern):
        return {"6224": {"name": "Geräte-Identifikation", "value": "WRS-CPU-B2/E",
                         "unit": "", "error": 0},
                "0.1": {"name": "Uhrzeit", "value": "09:58:03", "unit": "", "error": 0},
                "6225": {"name": "Geräte-Familie", "value": "", "error": 7}}
dazu = katalog.nachtragen(_Client(), kat_test)
pruefe(set(dazu) == {"6224", "0.1"}, f"nachgetragen wird, was antwortet: {dazu}")
pruefe("6225" not in kat_test["parameter"], "was error 7 meldet, bleibt draussen")
pruefe(kat_test["parameter"]["0.1"]["kategorie"] == "1"
       and kat_test["parameter"]["0.1"]["kategorie_name"] == "Uhrzeit und Datum",
       "ein Unterparameter landet bei seinem Hauptparameter")
pruefe(kat_test["parameter"]["6224"]["kategorie"] != "1",
       "und was keinen Hauptparameter hat, bekommt eine eigene Kategorie")
pruefe(kat_test["parameter"]["6224"]["schreibbar"] is False,
       "nachgetragene Auskuenfte sind nur lesbar")

# Ein abgelehnter Wert ist keine Stoerung - die Regelung hat ja geantwortet.
# Gezaehlt wird nur, was gar nicht ankommt, und erst der zweite Fehlversuch
# zeigt, dass der Weg selbst nicht funktioniert.
store.merke_state(schreibfehler={})
anwendung.schreiben_vermerken("50", "BSB-LAN hat nicht geantwortet")
pruefe(anwendung.schreiben_haengt() == {}, "ein einzelner Fehlversuch meldet nichts")
anwendung.schreiben_vermerken("50", "BSB-LAN hat nicht geantwortet")
haengt = anwendung.schreiben_haengt()
pruefe(haengt.get("anzahl") == 2 and "Parameter 50" in haengt.get("letzter", ""),
       f"der zweite schon: {haengt.get('letzter')}")
anwendung.schreiben_vermerken("50")
pruefe(anwendung.schreiben_haengt() == {},
       "und ein gelungener Schreibvorgang raeumt die Reihe ab")

# Die Unterscheidung steckt in der Ausnahme selbst.
try:
    client.setzen("39", "x")   # Antwort kommt vom Geraet, Status 0
except bsb.BsbFehler as err:
    pruefe(getattr(err, "stoerung", False) is False,
           "ein abgelehnter Wert ist keine Stoerung")

# Das Protokoll haelt fest, was jemand getan hat - und nicht jeden Takt.
store.protokoll_eintragen("stellen", "50 Komfortsollwert auf 23 gestellt")
store.protokoll_eintragen("fehler", "50 nicht gestellt: Zeitueberschreitung")
eintraege = store.protokoll_lesen(5)
pruefe(eintraege[0]["art"] == "fehler" and eintraege[1]["art"] == "stellen",
       "das juengste steht oben")
pruefe(all(e.get("zeit") for e in eintraege), "jeder Eintrag traegt eine Zeit")
for i in range(store.PROTOKOLL_LAENGE + 20):
    store.protokoll_eintragen("stellen", f"Eintrag {i}")
pruefe(len(store.protokoll_lesen()) == store.PROTOKOLL_LAENGE,
       f"das Protokoll waechst nicht ueber {store.PROTOKOLL_LAENGE} Eintraege")

# Neustart geht ueber /N. /NE waere ein Buchstabe mehr und das EEPROM leer.
GERAET["befehle"].clear()
kunde.post("/api/bsblan/neustart")
pruefe(GERAET.get("neustart") == "N", f"der Neustart nutzt /N, nicht /NE ({GERAET.get('neustart')})")

# Und im Betrieb: Wer die Auswahl speichert, findet sie in BSB-LAN wieder.
kunde.put("/api/auswahl", json=[{"nr": "115", "name": "Kessel"}])
gefuehrt = GERAET["konfig"]["34"]["value"].split(",")
pruefe("115" in gefuehrt, "auch das Speichern der Auswahl wandert dorthin")
# Und die Pflichtparameter der Uebersicht sind gleich mitgegangen.
pruefe(all(nr in gefuehrt for nr in anwendung.pflicht_nummern()),
       f"samt dem, was die Uebersicht braucht: {gefuehrt}")

# Dasselbe gilt fuer die Einstellungen: Wer speichert, erwartet, dass es dort
# ankommt, wo es wirkt. Vorher stand das neue Praefix im Add-on und BSB-LAN
# meldete weiter unter dem alten - dafuer gab es einen eigenen Knopf.
gespeichert = kunde.put("/api/einstellungen", json=dict(
    store.load_config()["einstellungen"], bsblan_praefix="NEUESTHEMA")).get_json()
pruefe(GERAET["konfig"]["41"]["value"] == "NEUESTHEMA",
       "Speichern traegt das Praefix gleich in BSB-LAN ein")
pruefe("mqtt_praefix" in (gespeichert.get("bsblan") or {}).get("geschrieben", []),
       "und die Antwort sagt, was dort geaendert wurde")
pruefe("bsblan" not in store.load_config()["einstellungen"],
       "die Rueckmeldung wird nicht mitgespeichert")

# Meldet der Manager selbst, hat BSB-LAN damit nichts zu tun.
GERAET["konfig"]["41"]["value"] = "UNBERUEHRT"
ohne = kunde.put("/api/einstellungen", json=dict(
    store.load_config()["einstellungen"], melder="addon",
    bsblan_praefix="EGAL")).get_json()
pruefe(GERAET["konfig"]["41"]["value"] == "UNBERUEHRT" and "bsblan" not in ohne,
       "als eigener Melder schreibt das Speichern nichts ins Geraet")

bsb.requests.get, bsb.requests.post = _alt_get, _alt_post
store.save_config({"einstellungen": dict(store.standard_einstellungen(),
                                         bsb_url="http://kessel.test"),
                   "auswahl": []})

print(f"\n{'ALLE PRÜFUNGEN BESTANDEN' if not fehler else str(len(fehler)) + ' FEHLER'}")
sys.exit(1 if fehler else 0)
