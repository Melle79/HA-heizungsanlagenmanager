# Kesselmanager

Der Kesselmanager bringt die Heizungsregelung nach Home Assistant – über
[BSB-LAN](https://github.com/fredlcore/BSB-LAN), einen kleinen ESP32 am Bus
des Reglers.

Er tut drei Dinge:

* **Auswählen.** Aus allen Parametern, die deine Regelung kennt, hakst du die
  an, die dich interessieren. Nur diese werden gelesen und als Entitäten
  gemeldet.
* **Lesen.** In einem einstellbaren Takt, schonend für den Bus, und mit
  passender Geräteklasse für Home Assistant.
* **Stellen.** Sollwerte und Betriebsarten ändern – hinter zwei Schaltern, die
  beide ab Werk aus sind.

## Voraussetzungen

Ein laufendes BSB-LAN im selben Netz und ein MQTT-Broker in Home Assistant.
Beides wird beim Start geprüft; fehlt der Broker, läuft die Oberfläche
trotzdem, es entstehen nur keine Entitäten.

## Der Parameterkatalog

Welche Parameter eine Regelung kennt, hängt am Gerät. Bei Siemens-Reglern –
und damit bei Weishaupt, Brötje, Elco und vielen anderen – unterscheidet sich
das sogar zwischen Gerätefamilien. Deshalb gibt es die **angepasste
Parameterliste**, die der BSB-LAN-Entwickler aus den Rohdaten einer Anlage
baut und die als `BSB_LAN_custom_defs.h` in die Firmware kommt.

Der Kesselmanager liest diese Liste nicht aus der Datei, sondern **aus BSB-LAN
selbst**. Das ist robuster: Was BSB-LAN ausliefert, ist per Definition das, was
auch tatsächlich geflasht ist. Aus „Parameter 72“ wird so
„Gerätebetriebsstunden“.

Einlesen musst du den Katalog einmal – und danach nur noch, wenn du die
Firmware mit einer neuen Liste geflasht hast. Es dauert ein bis zwei Minuten,
weil jede Kategorie einzeln über den Bus geht.

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

## Der Reiter „Regler“

Hier bedienst du die Anlage so, wie du es am Gerät auf dem Kessel tätest –
**mit derselben Gliederung**. Die 27 Kategorien kommen nicht von mir, sondern
aus der Regelung selbst: *Uhrzeit*, *Einstellwerte*, *Urlaub*, *Betriebsart*,
*Heizkreis*, *Warmwasser*, *Kessel* und so weiter. Niemand muss etwas
sortieren; die Anlage weiß am besten, was zusammengehört.

Wählst du eine Kategorie, liest der Manager ihre Werte und zeigt sie an.
Kategorien sind klein – meist zwischen zwei und dreißig Parametern –, das geht
in wenigen Sekunden. Stellbare Parameter bekommen gleich das passende
Bedienelement: ein Zahlenfeld bei Temperaturen, eine Auswahlliste bei
Betriebsarten, ein Textfeld sonst.

Die vier Zeitschaltprogramme haben einen **eigenen Reiter** – eine Zeile Text
wäre dort keine brauchbare Bedienung.

## Werte in der Steuerung: auf Zuruf

Der Reiter *Steuerung* zeigt jeden Parameter, den die Regelung als
beschreibbar meldet – bei einer Weishaupt-Anlage sind das über 160. Die alle
im Takt abzufragen würde den Bus dauerhaft belegen, und die wenigsten davon
will jemand dauerhaft sehen.

Deshalb liest die Steuerung **auf Zuruf**:

* Bis 25 angezeigte Parameter liest sie von selbst. Das trifft zu, sobald man
  nach etwas Bestimmtem sucht – und genau dann will man auch Zahlen sehen.
* Darüber wartet sie auf den Knopf *Werte der angezeigten Parameter lesen* und
  liest höchstens 40 auf einmal.
* Nach einer Änderung liest sie **nur den geänderten Parameter** nach. Der ist
  der Beweis, dass die Regelung den Wert übernommen hat.

Was du dauerhaft sehen willst, gehört unter *Auswahl* – nur diese Parameter
laufen im Takt und werden zu Entitäten.

## Zeitschaltprogramme

Vier Programme – Heizkreis 1, 2, 3 und Trinkwasser –, jedes mit sieben Tagen
und **drei Schaltfenstern je Tag**. Der Reiter zeigt sie als Tabelle mit
Uhrzeitfeldern: eine Zeile je Tag, drei Von-Bis-Paare nebeneinander.

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

Beide sind ab Werk aus. Der Reiter *Steuerung* zeigt jederzeit, welcher von
beiden noch fehlt. Zusätzlich nimmt der Manager nur Parameter an, die die
Regelung selbst als beschreibbar meldet, und fragt vor jeder Änderung nach.

## Der Bus ist langsam

Jede Abfrage ist ein Telegramm auf einem Zweidrahtbus, und die Regelung
antwortet in ihrem eigenen Takt. Der Manager fragt deshalb in Bündeln zu zwölf
Parametern mit kurzen Pausen dazwischen. Ein Aussetzer in einem Bündel kostet
nur dieses Bündel, nicht die ganze Runde.

Fünf Minuten Abfrageintervall sind für eine Heizung reichlich – ihre Trägheit
misst sich in Stunden.

## Zusammenspiel mit dem Heizungsplaner

Die Entitäten sind gewöhnliche Sensoren und lassen sich überall verwenden. Im
[Heizungsplaner](https://github.com/Melle79/HA-heizungsplaner-heating-planner)
gehört vor allem einer hinein: der **Betriebsstundenzähler**. Trägst du ihn
dort unter *Öltank → Laufzeitzähler* ein, rechnet der Planer daraus Verbrauch,
Reichweite und Kosten.
