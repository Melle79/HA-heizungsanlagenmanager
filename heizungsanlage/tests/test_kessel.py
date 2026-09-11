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
import os
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
e = store.validate_einstellungen({"bsb_url": "192.168.0.170"})
pruefe(e["bsb_url"] == "http://192.168.0.170", "eine Adresse ohne Schema bekommt eins")
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

print(f"\n{'ALLE PRÜFUNGEN BESTANDEN' if not fehler else str(len(fehler)) + ' FEHLER'}")
sys.exit(1 if fehler else 0)
