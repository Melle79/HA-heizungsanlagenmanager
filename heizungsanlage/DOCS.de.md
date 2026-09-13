# Heizungsanlagenmanager

Der Heizungsanlagenmanager bringt die Heizungsregelung nach Home Assistant – über
[BSB-LAN](https://github.com/fredlcore/BSB-LAN), einen kleinen ESP32 am Bus
des Reglers.

Er tut fünf Dinge:

* **Bedienen.** Die ganze Regelung, Kategorie für Kategorie, mit derselben
  Gliederung wie am Gerät auf dem Kessel – und Zeitschaltprogramme als
  Wochentabelle statt als Zeichenkette.
* **Auswählen.** Aus allen Parametern, die deine Regelung kennt, hakst du die
  an, die dich interessieren. Nur diese werden zu Entitäten.
* **Melden lassen.** Entweder meldet das Add-on sie selbst – oder es richtet
  BSB-LAN so ein, dass der Adapter es tut, und hält sich dann heraus.
* **Stellen.** Sollwerte und Betriebsarten ändern – hinter zwei Schaltern, die
  beide ab Werk aus sind.
* **Bescheid bekommen.** Wenn der Adapter ausfällt oder aufhört zu melden,
  geht eine Nachricht an einen notify-Dienst deiner Wahl.

## Inhalt

1. [Sprache](#sprache)
2. [Voraussetzungen](#voraussetzungen)
3. [Der Parameterkatalog](#der-parameterkatalog)
4. [Die Übersicht](#die-übersicht)
5. [Der Reiter „Regelung“](#der-reiter-regelung)
6. [Zeitschaltprogramme](#zeitschaltprogramme)
7. [Stellen: die zwei Schalter](#stellen-die-zwei-schalter)
8. [Der Reiter „Home Assistant“](#der-reiter-home-assistant)
9. [Auswahl: was nach Home Assistant geht](#auswahl-was-nach-home-assistant-geht)
10. [Die Fassung von BSB-LAN](#die-fassung-von-bsb-lan)
11. [Wer meldet nach Home Assistant?](#wer-meldet-nach-home-assistant)
12. [Gemerkte Werte](#gemerkte-werte)
13. [Gelesen wird auf Zuruf](#gelesen-wird-auf-zuruf)
14. [Der Bus ist langsam](#der-bus-ist-langsam)
15. [Übernahme durch andere Add-ons](#übernahme-durch-andere-add-ons)
16. [Zusammenspiel mit dem Heizungsplaner](#zusammenspiel-mit-dem-heizungsplaner)

## Sprache

Die Oberfläche spricht Deutsch und Englisch. Welche Sprache erscheint,
entscheidet Home Assistant – das Add-on fragt beim Laden nach und stellt sich
darauf ein. Umschalten muss man nichts.

**Deutsch ist die Quelle**: Der deutsche Satz ist zugleich der Schlüssel, unter
dem die Übersetzung steht. Das klingt unorthodox und hat einen handfesten
Vorteil – ein vergessener Eintrag fällt nicht aus, er bleibt deutsch stehen,
statt als Platzhalter zu erscheinen.

**Was die Regelung sagt, bleibt, wie sie es sagt.** Kategorien, Parameternamen
und Auswahlwerte kommen aus deinem Gerät; sie stehen genauso da wie am Gerät
auf dem Kessel. Vier von 27 Kategorien zu übersetzen ergäbe eine Scheinordnung,
während die übrigen Namen deutsch blieben – und wer BSB-LAN auf Englisch
stellt, bekommt sie von dort ohnehin englisch.

Eine weitere Sprache ist eine Datei: `frontend/sprachen/<code>.js` nach dem
Muster von `en.js` kopieren, die rechte Seite übersetzen, fertig. Am Code
ändert sich nichts.

## Voraussetzungen

Ein laufendes BSB-LAN im selben Netz und ein MQTT-Broker in Home Assistant.
Beides wird beim Start geprüft; fehlt der Broker, läuft die Oberfläche
trotzdem, es entstehen nur keine Entitäten.

**Welche Anlagen?** Alle, die BSB-LAN bedient – BSB, LPB und PPS, also die
Siemens-Regelungen hinter Brötje, Elco, Weishaupt, Atlantic, Baxi und
anderen. Der Heizungsanlagenmanager kennt keine einzige Parameternummer auswendig: Was
auf der Übersicht steht und welche Kategorien Schaltzeiten führen, leitet er
aus dem Katalog deiner eigenen Anlage ab – aus den Namen und aus dem
Datentyp, den BSB-LAN vergibt. Findet er für eine Kachel nichts, bleibt sie
weg, statt eine fremde Zahl anzuzeigen.

Was der Manager **nicht** leisten kann, ist mehr zu wissen als BSB-LAN: Führt
deine Firmware einen Parameter nicht, gibt es ihn hier auch nicht. Und ob
sich ein Wert stellen lässt, entscheidet am Ende die Regelung selbst.

## Der Parameterkatalog

Welche Parameter eine Regelung kennt, hängt am Gerät. Bei Siemens-Reglern –
und damit bei Weishaupt, Brötje, Elco und vielen anderen – unterscheidet sich
das sogar zwischen Gerätefamilien. Deshalb gibt es die **angepasste
Parameterliste**, die der BSB-LAN-Entwickler aus den Rohdaten einer Anlage
baut und die als `BSB_LAN_custom_defs.h` in die Firmware kommt.

Der Heizungsanlagenmanager liest diese Liste nicht aus der Datei, sondern **aus BSB-LAN
selbst**. Das ist robuster: Was BSB-LAN ausliefert, ist per Definition das, was
auch tatsächlich geflasht ist. Aus „Parameter 72“ wird so
„Gerätebetriebsstunden“.

Einlesen musst du den Katalog einmal – und danach nur noch, wenn du die
Firmware mit einer neuen Liste geflasht hast. Es dauert ein bis zwei Minuten,
weil jede Kategorie einzeln über den Bus geht.

## Die Übersicht

Die Startseite zeigt die üblichen Messwerte als Kacheln. Welche das sind,
**schlägt der Manager vor** – gesucht über die Namen im Katalog deiner Anlage:
Kesseltemperatur, Vorlauf, Außentemperatur, Betriebsstunden, Brennerstarts,
Legionellenschaltung. Findet sich für eine Kachel nichts, fällt sie weg; eine
leere Übersicht ist ehrlicher als eine mit Zahlen einer fremden Anlage.

**Der Vorschlag ist kein Gesetz.** Unter *Übersicht anpassen* stellst du sie
selbst zusammen: Reihenfolge über ↑ und ↓, eigene Beschriftung je Kachel,
Entfernen über ✕, und über die Auswahlliste kommt jeder Parameter deiner
Anlage dazu. *Vorschlag laden* holt den abgeleiteten Satz zurück, ohne ihn
gleich zu speichern – so lässt sich vergleichen. Speicherst du eine leere
Liste, gilt wieder der Vorschlag.

Was auf der Übersicht steht, **wird auch gemeldet**: Der Manager trägt diese
Parameter in die Auswahl ein und hält sie dort fest (Vermerk *für die
Übersicht*), denn sonst bekäme er die Werte gar nicht.

## Der Reiter „Regelung“

![Zeitschaltprogramm als Wochentabelle](https://raw.githubusercontent.com/Melle79/HA-heizungsanlagenmanager/main/heizungsanlage/doku/bilder/regelung.png)


Hier bedienst du die Anlage so, wie du es am Gerät auf dem Kessel tätest –
**mit derselben Gliederung**. Die 27 Kategorien kommen nicht von mir, sondern
aus der Regelung selbst: *Uhrzeit*, *Einstellwerte*, *Urlaub*, *Betriebsart*,
*Heizkreis*, *Warmwasser*, *Kessel* und so weiter. Niemand muss etwas
sortieren; die Anlage weiß am besten, was zusammengehört.

Das Menü hat zwei Stufen: oben die **Bereiche** – *Heizen*, *Trinkwasser*,
*Wärmeerzeuger*, *Speicher*, *Wartung & Diagnose*, *Anlage & Konfiguration* –,
darunter die Kategorien des gewählten Bereichs, darunter das Formular. Ein
Bereich mit nur einer Kategorie öffnet sie gleich mit.

Über **Anpassen** blendest du aus, was deine Anlage nicht braucht: die
Kaskade, wenn nur ein Kessel dasteht, den Pufferspeicher, wenn keiner
angeschlossen ist, und alles, was BSB-LAN für sich selbst mitbringt.
Ausgeblendet heißt nicht gelöscht – ein Klick holt es zurück.

Wählst du eine Kategorie, liest der Manager ihre Werte und zeigt sie an.
Kategorien sind klein – meist zwischen zwei und dreißig Parametern –, das geht
in wenigen Sekunden. Stellbare Parameter bekommen gleich das passende
Bedienelement: ein Zahlenfeld bei Temperaturen, eine Auswahlliste bei
Betriebsarten, ein Textfeld sonst.

Die Zeitschaltprogramme stehen im selben Menü – eine Zeile Text wäre dort
keine brauchbare Bedienung, deshalb erscheint statt der Parameterliste eine
Wochentabelle.

## Zeitschaltprogramme

Vier Programme – Heizkreis 1, 2, 3 und Trinkwasser –, jedes mit sieben Tagen
und **drei Schaltfenstern je Tag**. Sie stehen im Bereich *Zeitprogramme* und
erscheinen als Tabelle mit Uhrzeitfeldern: eine Zeile je Tag, drei Von-Bis-
Paare nebeneinander.

Oben in der Tafel steht, ob dieses Programm **gerade läuft** – denn aktiv ist
immer nur eines. Welches, entscheidet ein gewöhnlicher Parameter der Regelung;
der Manager erkennt ihn daran, dass seine Auswahlwerte mehrfach „Programm
<Zahl>“ heißen, nicht an seinem Namen (der kann in einer angepassten
Parameterliste durchaus falsch sein). Die Auswahl steht gleich daneben: Du
schaltest von hier aus zwischen den Programmen um, ebenso auf Standby, Sommer
oder Dauerbetrieb – dafür muss niemand in den Heizungskeller.

Ein leeres Fenster heißt „wird nicht benutzt“. Das ✕ am Zeilenende leert einen
ganzen Tag.

Zwei Knöpfe sparen die meiste Tipparbeit: **Montag auf Mo–Fr übertragen** und
**Montag auf alle Tage übertragen**.

Geändert wird erst beim Speichern, und auch dann nur die Tage, die du angefasst
hast – sie sind während der Bearbeitung farbig markiert. Vor dem Schreiben
zeigt eine Rückfrage die Zeiten im Klartext. Lehnt die Regelung einen Tag ab,
hört der Manager sofort auf, statt blind weiterzuschreiben.

Technisch steht hinter jedem Tag eine Zeichenkette, wie BSB-LAN sie liefert und
erwartet:

```
06:00-22:00 ##:##-##:## ##:##-##:##
```

Das ist zum Ablesen brauchbar und zum Einstellen unzumutbar – deshalb der
Editor.

## Stellen: die zwei Schalter

Ein falscher Sollwert lässt im Winter eine Wohnung auskühlen. Deshalb müssen
zum Stellen **zwei** Schalter stehen:

1. in **BSB-LAN** selbst (dort heißt es `buswritable`),
2. unter *Einstellungen → Schreibzugriff* in diesem Add-on.

Beide sind ab Werk aus. Der Reiter *Regelung* zeigt jederzeit, welcher von
beiden noch fehlt. Zusätzlich nimmt der Manager nur Parameter an, die die
Regelung selbst als beschreibbar meldet, und fragt vor jeder Änderung nach.

## Der Reiter „Home Assistant“

![Auswahl und Werte in einer Tabelle](https://raw.githubusercontent.com/Melle79/HA-heizungsanlagenmanager/main/heizungsanlage/doku/bilder/mqtt.png)


Alles, was mit dem Weg nach Home Assistant zu tun hat, steht auf einer Seite:
wer meldet, welche Parameter, und was davon zuletzt ankam.

Die Tabelle führt beides nebeneinander: links das Häkchen und der Name, rechts
der zuletzt gelesene Wert. Die Spaltenköpfe sortieren – nach Nummer, Name,
Einheit oder Wert –, und der Filter kennt neben „nur stellbare“ und
„nur ausgewählte“ auch **„ausgewählt, aber ohne Wert“**: Damit findest du in
einem Griff, was in Home Assistant als leere Entität landen würde.

**Sortiert ist sie nach den Kategorien der Regelung** – in deren eigener
Reihenfolge, nicht in einer erfundenen. Jede Kategorie ist zugeklappt und
zeigt, wie viele Parameter sie führt und wie viele davon angehakt sind; ein
Klick auf die Zeile öffnet sie. Wer sucht oder filtert, bekommt die Treffer
offen hingelegt und muss nicht erst klicken.

### Wenn die Beschriftung nicht stimmt

Die Namen kommen aus der Parameterliste der Firmware, und die trifft es nicht
immer: Parameter 70 heißt dort *Brauchwassertemperatur-Reduziertsollwert* und
ist an dieser Anlage die **Betriebsart**. Solche Fehlgriffe stammen aus den
Siemens-Unterlagen und lassen sich nicht von außen richtigstellen.

Deshalb kann jeder Parameter einen **eigenen Namen** bekommen: in der Auswahl
über den Stift ✎ neben dem Namen. Er gilt überall in dieser Oberfläche, und
der ursprüngliche Name bleibt als Fußnote *laut Liste: …* darunter stehen –
damit nachvollziehbar bleibt, worüber man eigentlich spricht.

**Home Assistant übernimmt den Namen ebenfalls.** Meldet der Manager selbst,
steht er einfach in der Anmeldung. Meldet BSB-LAN, schreibt der Manager dessen
Anmeldung zurück – dieselbe `unique_id`, dieselben Themen, nur der Name
korrigiert. Home Assistant erkennt die Entität wieder und benennt sie um.

Kündigt BSB-LAN seine Entitäten neu an, etwa nach einem Neustart, steht dort
zunächst wieder der Name aus der Liste; der Manager setzt den eigenen im
nächsten Takt erneut durch. Und weil er sich den ursprünglichen Namen merkt,
führt das Löschen des eigenen Namens zurück zum alten – nicht in ein Nichts.

## Auswahl: was nach Home Assistant geht

Jeder angehakte Parameter wird ein Sensor. Einheit und Geräteklasse schlägt
der Manager aus dem Datentyp vor:

| erkannt an | Geräteklasse | Verlauf |
|---|---|---|
| °C, °F, K | `temperature` | `measurement` |
| bar | `pressure` | `measurement` |
| kW / kWh | `power` / `energy` | `measurement` / `total_increasing` |
| h, min, s | `duration` | `measurement` |
| „Betriebsstunden“, „Starts“, „Verbrauch“ im Namen | – | **`total_increasing`** |
| Aufzählungen, Datum, Uhrzeit | keine | keine |

Die letzte Zeile mit den Zählerständen ist die wichtigste: Aus einem Wert, der
nur wächst, baut Home Assistant von selbst eine **Langzeitstatistik** mit
Tages-, Monats- und Jahreswerten. Wer eine Zeitreihendatenbank an Home
Assistant hängt, bekommt den Verlauf dort ohne weiteres Zutun.

Die Entität hängt an der **Parameternummer**, nicht am Namen. Wer die Anzeige
umbenennt, behält also seine Historie.

## Die Fassung von BSB-LAN

Oben rechts, neben den Anzeigen für BSB-LAN und MQTT, steht die geflashte
Fassung des Adapters – etwa **BSB-LAN 5.1.18**. Gibt es eine neuere,
erscheint daneben ein Hinweis, der auf die Veröffentlichungen verlinkt.
Verglichen wird mit `bsb-lan.de/bsb-version.h`, derselben Quelle, die auch
BSB-LAN selbst befragt; abgefragt wird das höchstens einmal am Tag.

## Wer meldet nach Home Assistant?

Zwei Programme können dieselbe Anlage melden, und beide können es gut – nur
nicht gleichzeitig. Unter *Home Assistant* steht die Wahl – und darunter
gleich die Felder, die zum gewählten Weg gehören:

**Der Manager meldet** (ab Werk). Er liest die Auswahl in seinem Takt und legt
die Entitäten selbst an, mit kuratierten Geräteklassen. Steht das Add-on,
kommt nichts an.

**BSB-LAN meldet.** Der Adapter bringt eigenes MQTT samt automatischer
Anmeldung mit. Er fragt den Bus ohnehin ab, meldet häufiger und legt auch
Bedienelemente an (`select.…` für stellbare Parameter). Der Manager gibt ihm
dann nur noch die Liste und hält sich mit eigenen Entitäten zurück – die
angemeldeten räumt er beim Umschalten ab, damit nicht zwei Absender dasselbe
Diagramm füllen.

In dieser Betriebsart übernimmt der Manager die Einrichtung:

* **Broker, Benutzer und Passwort** kommen von Home Assistant selbst. Der
  Supervisor reicht sie dem Add-on durch; sie werden an BSB-LAN
  weitergegeben, aber weder angezeigt noch hier gespeichert. Abtippen musst du
  nichts.
* **Die Broker-Adresse wird übersetzt.** Der Supervisor nennt dem Add-on
  `core-mosquitto` – einen Namen aus dem Docker-Netz von Home Assistant. Für
  das Add-on stimmt er, für einen ESP32 im Hausnetz ist er nicht auflösbar.
  Deshalb fragt der Manager nach der IP-Adresse des Rechners, auf dem Home
  Assistant läuft, und gibt diese weiter. Findet er keine, schreibt er weder
  Adresse noch Zugangsdaten: Was in BSB-LAN steht, funktioniert wenigstens.
* **Präfix, Geräte-ID, Intervall, Einheiten und MQTT-Art** stellst du hier ein.
  Meldet dagegen der Manager, steht an derselben Stelle nur *sein* Präfix – es
  ist immer das eine Feld sichtbar, das gerade gilt.
* **Speichern trägt die Werte gleich ins Gerät ein.** Ein eigener Knopf dafür
  wäre eine Falle: Man hätte das neue Präfix im Add-on stehen, während BSB-LAN
  weiter unter dem alten meldet. Was dabei im Gerät geändert wurde, sagt die
  Meldung danach – und geschrieben wird nur, was sich unterscheidet.
* **Auto-Discovery** wird eingeschaltet, damit die Entitäten von selbst in Home
  Assistant erscheinen.
* Was BSB-LAN sonst tut – etwa auf SD-Karte protokollieren –, bleibt
  unangetastet: Geschrieben wird nur, was sich unterscheidet.

### Legionellenaufheizung

Die Regelung kann eine Legionellenschaltung selbst – aber auf älteren Reglern
nur als *alle n Tage*, ohne Wochentag und ohne Uhrzeit. Bei einem Speicher
**ohne thermostatische Mischeinrichtung** ist der Zeitpunkt aber die halbe
Sache: 60 °C im Speicher heißen 60 °C am Wasserhahn.

Deshalb kann der Manager die Aufheizung selbst fahren, unter *Einstellungen →
Legionellenaufheizung*: Rhythmus in Tagen, Wochentag, Uhrzeit, Zieltemperatur
und eine Höchstdauer. Er hebt dann Sollwert **und** Obergrenze des
Trinkwassers an und stellt beide danach auf die vorherigen Werte zurück.

Drei Dinge sind dabei bewusst so gebaut:

* **Der Rückweg steht fest, bevor der Hinweg beginnt.** Die aktuellen Werte
  werden frisch gelesen und im Zustand hinterlegt. Stirbt das Add-on mitten
  im Lauf, stellt es beim nächsten Start zurück – nicht der Speicher bleibt
  heiß, sondern das Programm merkt sich, was es schuldet.
* **Ohne Freigabe zum Stellen passiert nichts.** Diese Funktion schreibt von
  sich aus; sie ist ab Werk aus und braucht denselben Schalter wie jedes
  andere Schreiben.
* **Es gibt eine Zeitgrenze.** Wird die Zieltemperatur nicht erreicht – etwa
  weil der Kessel nicht mitspielt –, stellt der Manager nach der eingestellten
  Höchstdauer trotzdem zurück und schreibt „Zeit abgelaufen“ ins Protokoll.

Nach dem Erreichen hält er die Temperatur noch eine Viertelstunde, damit auch
der Teil des Speichers warm wird, an dem der Fühler nicht sitzt. Mit *Jetzt
aufheizen* lässt sich ein Lauf von Hand auslösen, mit *Abbrechen* jederzeit
beenden.

Welche Parameter dafür verwendet werden, leitet der Manager aus dem Katalog
ab – Sollwert, Obergrenze und Istwert des Trinkwassers. Führt eine Anlage
nicht alle drei, sagt er das und bietet die Funktion nicht an.

### Melden, wenn etwas ausfällt

Unter *Einstellungen → Melden* steht, wohin eine Störung geht: ein
**notify-Dienst von Home Assistant**, ausgewählt aus dem, was deine Installation
anbietet – das Handy, ein Lautsprecher, eine dauerhafte Benachrichtigung. Ohne
Meldeweg steht eine Störung nur in dieser Oberfläche.

Zwei Fälle werden gemeldet:

* **Der Adapter antwortet nicht.** Kein Netz, kein Strom, abgestürzt.
* **Er antwortet, meldet aber nichts.** Der Zustand nach einem Funkabriss, in
  dem BSB-LAN erreichbar bleibt und MQTT trotzdem ausgelassen hat.

Beides erst, wenn es die eingestellte **Wartezeit** übersteht – ab Werk zehn
Minuten. Kurze Funklöcher sind bei WLAN normal, und wer bei jedem Ruckler eine
Nachricht bekommt, liest ab der dritten keine mehr. Ist die Störung vorbei,
kommt eine Entwarnung; beides genau einmal.

Mit *Probemeldung schicken* prüfst du den Weg, bevor du ihn brauchst.

### Die Entität „BSB-LAN erreichbar“

BSB-LANs eigene Anmeldung in Home Assistant kennt **kein Verfügbarkeitsthema**.
Fällt der Adapter aus – ein Funkabriss reicht –, bleiben seine Entitäten
„verfügbar“ und zeigen ihren letzten Wert weiter. Auf dem Dashboard sieht das
aus wie eine Anlage, die 74,6 °C hält.

Deshalb meldet der Manager eine eigene Entität:
`binary_sensor.heizungsanlage_bsblan_erreichbar`, Geräteklasse *connectivity*,
als Diagnose eingestuft. Sie wird **in jeder Betriebsart** gemeldet, auch wenn
BSB-LAN sonst alles selbst meldet – sie sagt nichts über die Heizung, sondern
über die Verbindung zu ihr. Geprüft wird einmal je Minute über `/JI`, was nur
das Gerät fragt und den Bus nicht belastet.

Damit lässt sich eine Automation bauen, die sich meldet, wenn der Adapter
länger als ein paar Minuten weg ist.

### Wenn BSB-LAN antwortet, aber nichts meldet

Es gibt einen Zustand, der von außen wie „läuft“ aussieht und keiner ist:
BSB-LAN beantwortet jede HTTP-Abfrage, hat den MQTT-Teil aber nicht gestartet.
Das passiert nach einem WLAN-Abriss – der Adapter macht dann einen eigenen
Zugangspunkt auf und überspringt MQTT, während sich das WLAN im Hintergrund
wieder einbucht. In Home Assistant fällt das lange nicht auf: Die Entitäten
behalten einfach ihren letzten Wert.

Der Manager hört deshalb auf `<Präfix>/status`, wo BSB-LAN sein „online“
hinterlegt. Bleibt dort „offline“ stehen, während das Gerät erreichbar ist,
erscheint ein Hinweis mit dem Knopf **Adapter neu starten**. Der Neustart geht
über `/N` und lässt alle Einstellungen im Gerät unangetastet.

### Zweimal fragen ist einmal zu viel

Meldet BSB-LAN, sind die Werte längst über den Bus gekommen – und liegen als
`retained`-Nachrichten beim Broker, also sofort abrufbar. Der Manager **hört
sie deshalb mit**, statt dieselbe Anlage ein zweites Mal zu fragen. Über den
Bus geht er nur noch dort, wo etwas fehlt: für Kategorien, die man im Reiter
*Regelung* öffnet, für Zeitprogramme – und wenn ein gemeldeter Wert länger als
das Dreifache des Abfragetakts nicht mehr aufgefrischt wurde.

**Was die Übersicht braucht, gehört dazu.** Kesseltemperatur, Außentemperatur,
Betriebsstunden und die übrigen Kachelwerte trägt der Manager selbst in die
Auswahl ein; abwählen lässt sich das nicht, denn ohne sie bliebe seine eigene
Startseite leer. In der Liste stehen sie mit dem Vermerk *für die Übersicht*.
Für Messwerte gilt zusätzlich ein **Mindesttakt von fünf Minuten** – ein Grundtakt
von einer Stunde würde die Übersicht sonst zu einer Erinnerung machen.

Eine Kachel, die eine **Einstellung** zeigt statt eines Messwerts – die
Legionellenschaltung etwa –, wird nur stündlich erfragt: Sie ändert sich nur,
wenn jemand sie ändert.

Was die Anlage nicht beantwortet, wird dabei **nicht** erzwungen: Für eine
Vorlauftemperatur ohne Fühler entstünde nur eine ewig leere Entität.

### Jeder Parameter im eigenen Takt

Der **Grundtakt** von BSB-LAN gilt für alle Parameter gleich, und das
ist der Grund für die Grenze von 40: Eine Busabfrage dauert ein bis zwei
Sekunden, vierzig Parameter jede Minute belegen den Bus vollständig. Frederik
Holst, der BSB-LAN gebaut hat, rät deshalb dazu, jeden Parameter so oft zu
holen, wie er es verdient – die Kesseltemperatur oft, die Betriebsstunden
einmal in der Stunde.

Dafür steht in der Auswahl je Parameter eine Spalte **Takt**. Bleibt sie auf
*Grundtakt*, gilt der Grundtakt von BSB-LAN. Steht dort ein Wert, fordert
der Manager diesen Parameter über MQTT (`<Präfix>/poll`) selbst an – dieselbe
Schnittstelle, die man sonst mit Automationen in Home Assistant bedient, nur
dass sich hier niemand welche bauen muss.

Neben der Auswahl steht, was das kostet: **Abfragen je Minute** und der
geschätzte Anteil an der Buszeit. Über 60 % wird die Zahl orange – dann fragt
die Anlage öfter, als sie antworten kann.

Die **Auswahl** wandert beim Speichern gleich mit in BSB-LANs Log-Parameter-
liste. Umgekehrt geht es auch: *Liste aus BSB-LAN übernehmen* holt, was dort
über die Jahre zusammengekommen ist, in die Auswahl. Beide Knöpfe stehen bei
der Auswahl selbst, nicht oben bei der Melderwahl – und nur dann, wenn BSB-LAN
auch meldet. *Auswahl an BSB-LAN geben* ist der Nachschlag für den Fall, dass
das Gerät zwischendurch zurückgesetzt wurde.

Nach jedem Schreiben liest der Manager zurück und zeigt, was wirklich
angekommen ist. Das ist keine Vorsicht, sondern Erfahrung:

* **BSB-LAN nimmt höchstens 40 Log-Parameter.** Was darüber hinausgeht, fällt
  stillschweigend weg – ohne Fehler, ohne Meldung. Der Manager sagt dir dann,
  welche Nummern nicht angekommen sind.
* **`/JW` verwirft Einträge, die zu viel mitbringen.** Gibt man den
  vollständigen Eintrag aus `/JL` zurück – mit `type`, `format`, `category`
  und `name` –, antwortet das Gerät mit einer leeren Struktur und ändert
  nichts. Nur `parameter` und `value` werden angenommen.
* **`/JL` liefert in 5.1.18 kaputtes JSON**, wenn keine One-Wire- oder
  DHT-Pins gesetzt sind.
* **BSB-LAN widerruft nur, was es gerade führt.** Ändert man erst die Liste
  und meldet dann ab, bleibt für jeden entfernten Parameter eine Entität
  zurück – „retained“ im Broker und damit für immer in Home Assistant. Der
  Manager hält deshalb die Reihenfolge ein: abmelden, Liste ändern, anmelden.

## Gemerkte Werte

Eine Kategorie über den Bus zu lesen dauert ein paar Sekunden – 4800 Baud, und
die Regelung antwortet in ihrem Takt. Wer nur nachsehen will, wie der
Komfortsollwert steht, wartet jedes Mal aufs Neue.

Der Manager merkt sich deshalb, was er zuletzt gelesen hat. Steht unter
*Einstellungen → Anzeige* der Haken **„Zuletzt gelesene Werte beim Öffnen
sofort zeigen“**, erscheint die Tabelle ohne Wartezeit, mit dem Alter daneben –
„vor 7 Minuten gelesen · wird aufgefrischt …“ –, und der frische Stand kommt im
Hintergrund nach.

Ab Werk ist der Haken **aus**, und das hat einen Grund: Wer seine Anlage auch
am Gerät auf dem Kessel verstellt, sähe für diese paar Sekunden den alten Wert.
Läuft alles über Home Assistant, kann das nicht passieren.

Zwei Dinge gelten auch mit Haken:

* Eine Zahl, die gerade getippt wird, überlebt das Auffrischen – samt Cursor.
* In den Zeitprogrammen werden nur die Tage aufgefrischt, die niemand
  angefasst hat. Geänderte Zeiten gehen nicht verloren.

## Gelesen wird auf Zuruf

Eine Regelung kennt schnell zweihundert Parameter, und über 160 davon sind bei
einer Weishaupt-Anlage stellbar. Die alle im Takt abzufragen würde den Bus
dauerhaft belegen – und die wenigsten davon will jemand dauerhaft sehen.

Deshalb liest der Manager im Reiter *Regelung* nur, was gerade offen ist: die
Kategorie, die du angeklickt hast, höchstens 40 Parameter auf einmal. Nach
einer Änderung liest er **nur den geänderten Parameter** nach – der ist der
Beweis, dass die Regelung den Wert übernommen hat.

Was du dauerhaft sehen willst, gehört unter *Home Assistant* in die Auswahl:
Nur diese Parameter laufen im Takt und werden zu Entitäten.

## Der Bus ist langsam

Jede Abfrage ist ein Telegramm auf einem Zweidrahtbus, und die Regelung
antwortet in ihrem eigenen Takt. Der Manager fragt deshalb in Bündeln zu zwölf
Parametern mit kurzen Pausen dazwischen. Ein Aussetzer in einem Bündel kostet
nur dieses Bündel, nicht die ganze Runde.

Fünf Minuten **Abfragetakt des Managers** sind für eine Heizung reichlich –
ihre Trägheit misst sich in Stunden. Dieser Takt ist der des Add-ons selbst:
Es liest die ausgewählten Parameter für seine eigene Anzeige, und wenn es
meldet, auch für Home Assistant. Er läuft **auch dann, wenn BSB-LAN meldet** –
beide Takte belegen denselben Bus, und die Schätzung neben der Auswahl zählt
deshalb beide.

## Übernahme durch andere Add-ons

Der Heizungsplaner soll Sollwerte und Schaltzeiten übernehmen können, ohne
dass hier jemand dagegenarbeitet. Dafür gibt es eine kleine Schnittstelle –
und drei Regeln, die sie erträglich machen:

* **Ohne Anmeldung ändert sich nichts.** Ab Werk führt niemand etwas; das
  Add-on bleibt vollständig eigenständig und braucht den Planer nicht.
* **Übernommen heißt stillgelegt, nicht versteckt.** Die Werte sind weiter
  ablesbar. Nur die Eingabefelder liegen still, mit dem Namen dessen, der sie
  führt, direkt daneben.
* **Der Mensch davor behält das letzte Wort.** Über der Tafel steht ein Knopf
  *Übernahme aufheben*. Eine Sperre, die man nicht lösen kann, wäre keine
  Zusammenarbeit.

Erreichbar ist das Add-on für andere Add-ons unter
`http://local-heizungsanlage:8099` (mit Bindestrich – der Unterstrich des
slugs wird im Rechnernamen zum Strich).

### Anmelden

```
PUT http://local-heizungsanlage:8099/api/uebernahme
{
  "quelle": "heizungsplaner",
  "name": "Heizungsplaner",
  "hinweis": "Sollwerte kommen aus dem Wochenplan",
  "parameter": ["710", "712", "11", "11.1"]
}
```

Der Aufruf ersetzt jedes Mal die ganze Liste dieser Quelle – wer etwas
freigeben will, schickt sie einfach ohne diesen Parameter erneut. Eine **leere
Liste ist die Abmeldung**, damit beim Aufräumen ein Aufruf genügt.

### Stellen

Der Planer stellt seine Parameter über denselben Weg wie die Oberfläche, nennt
dabei aber seine Kennung:

```
POST http://local-heizungsanlage:8099/api/setzen
{"nr": "710", "wert": "21.5", "quelle": "heizungsplaner"}
```

Ohne `quelle` antwortet das Add-on auf einen übernommenen Parameter mit
**409** und einem Satz, der den Verantwortlichen nennt. Das ist Absicht: Ein
von Hand gestellter Wert, den der Planer beim nächsten Takt zurückdreht, wäre
schlimmer als eine klare Absage.

### Nachsehen und aufheben

```
GET    /api/uebernahme                → {quellen: {...}, parameter: {nr: {...}}}
DELETE /api/uebernahme/heizungsplaner → hebt die Übernahme auf
```

Hebt jemand die Übernahme in der Oberfläche auf, erfährt der Planer das beim
nächsten `GET`. Er sollte sie dann **nicht** stillschweigend neu anmelden –
sonst ist der Knopf eine Attrappe.

## Zusammenspiel mit dem Heizungsplaner

Die Entitäten sind gewöhnliche Sensoren und lassen sich überall verwenden. Im
[Heizungsplaner](https://github.com/Melle79/HA-heizungsplaner-heating-planner)
gehört vor allem einer hinein: der **Betriebsstundenzähler**. Trägst du ihn
dort unter *Öltank → Laufzeitzähler* ein, rechnet der Planer daraus Verbrauch,
Reichweite und Kosten.
