#!/usr/bin/env python3
"""Trockenprüfung des Kesselmanagers – ohne Heizung, ohne Home Assistant.

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

print("\n=== Die Auswahl wird geprüft ===")
a = store.validate_auswahl([{"nr": "50", "name": "X"}, {"nr": "50", "name": "X"}])
pruefe(len(a) == 1, "ein doppelt angehakter Parameter zählt einmal")
try:
    store.validate_auswahl([{"name": "ohne Nummer"}])
    pruefe(False, "ein Eintrag ohne Parameternummer wird abgelehnt")
except store.ValidationError:
    pruefe(True, "ein Eintrag ohne Parameternummer wird abgelehnt")

print(f"\n{'ALLE PRÜFUNGEN BESTANDEN' if not fehler else str(len(fehler)) + ' FEHLER'}")
sys.exit(1 if fehler else 0)
