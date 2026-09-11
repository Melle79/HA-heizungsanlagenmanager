# Änderungen

## 1.6.1

- **Behoben: Das Add-on räumte bei jedem Start die alten Entitäten erneut ab.**
  Der Merker, unter welcher Kennung zuletzt veröffentlicht wurde, kam nie auf
  die Platte: Der Lesetakt lädt den Zustand, braucht ein paar Sekunden für
  seine Runde über den Bus und schrieb danach seine inzwischen veraltete
  Kopie zurück – samt allem, was in der Zwischenzeit jemand anderes
  eingetragen hatte. Jetzt schreibt jeder Weg nur die Felder fort, für die er
  zuständig ist.

## 1.6.0

- **Andere Add-ons können Parameter übernehmen.** Gedacht für den
  Heizungsplaner: Er meldet an, welche Sollwerte und Schaltzeiten er führt,
  und die liegen hier dann still – ablesbar wie zuvor, aber mit seinem Namen
  daneben statt einem Eingabefeld. Die Schnittstelle steht in der
  Dokumentation.
- **Eigenständig bleibt es trotzdem.** Ohne Anmeldung ändert sich gar nichts,
  und über jeder betroffenen Tafel steht ein Knopf *Übernahme aufheben*. Eine
  Sperre, die man nicht lösen kann, wäre keine Zusammenarbeit.
- Ein übernommener Parameter lässt sich auch über die Schnittstelle nicht
  versehentlich von Hand stellen: Das Add-on antwortet mit 409 und nennt den
  Verantwortlichen, statt einen Wert anzunehmen, den der Planer beim nächsten
  Takt zurückdreht.
- **Behoben: Die Oberfläche zeigte die falsche Fassung.** Die Nummer stand an
  zwei Stellen und lief auseinander – im Kopf stand „v1.3.1“, während das
  Add-on längst 1.5.0 war. Sie kommt jetzt aus der `config.yaml`, und eine
  Prüfung wacht darüber.
- **Behoben: Das Protokoll meldete „126 Werte gelesen“**, wo dreizehn abgefragt
  wurden – gezählt wurde der ganze Zwischenspeicher statt der Runde.

## 1.5.0

- **Die Entitäten heißen jetzt `sensor.heizungsanlage_p…`** statt
  `sensor.kesselmanager_p…`. Der alte Name passte nicht mehr zu dem, was das
  Add-on tut, und je länger er stehenbleibt, desto teurer wird die Umstellung.
- Beim ersten Start danach **räumt das Add-on hinter sich auf**: Die
  Anmeldungen der alten Kennung werden zurückgenommen. Ohne das stünde in
  Home Assistant für immer ein zweites, totes Gerät – Discovery-Nachrichten
  überleben das Add-on, sie liegen im Broker.
- Ein gespeichertes MQTT-Präfix `kesselmanager` wandert mit. Ein selbst
  gewähltes bleibt unangetastet.
- Der slug ist `heizungsanlage`; für den Supervisor ist das ein neues Add-on.
  Einstellungen, Auswahl und Katalog müssen beim Umzug mitgenommen werden –
  ein neues Einlesen des Katalogs über den Bus ist dafür nicht nötig.

## 1.4.1

- **Neuer Name: „Heizungsanlagenmanager via BSB-LAN“.** „Kesselmanager“ war zu
  eng – gestellt wird die ganze Anlage: Heizkreise, Trinkwasser,
  Zeitprogramme. Im Seitenmenü steht das Add-on jetzt als *Heizkessel*, damit
  es sich vom *Heizungsplaner* unterscheidet.
- Die Entitäten heißen **unverändert** `sensor.kesselmanager_p…`. Der interne
  Kurzname bleibt, denn er steckt in den IDs und in der aufgezeichneten
  Historie; ein neuer wäre für den Supervisor ein anderes Add-on, mit
  Neuinstallation und leeren Diagrammen.

## 1.4.0

- **Der Manager passt jetzt auf jede BSB-LAN-Anlage, nicht nur auf eine.**
  Drei Stellen waren auf die Parameterliste eines einzigen Kessels getippt:
  die sechs Kacheln der Übersicht (115, 116, 110, 111, 72, 73), die
  Kategorien der Zeitprogramme (1 bis 4) und die Annahme, die ersten sieben
  Parameter einer solchen Kategorie seien die Wochentage. Auf einer
  Standard-BSB-Regelung heißt die Kesseltemperatur 8310, und die Programme
  sitzen ganz woanders.
- Die Übersicht sucht ihre Kacheln nun über die **Namen** im Katalog und
  unterscheidet dabei Ist- von Sollwerten. Die Zeitprogramme erkennt der
  Manager am **Datentyp TIMEPROG**, den BSB-LAN vergibt – damit findet er in
  einer Kategorie auch nur die Tage und nicht die „Standardwerte“ daneben.
  Was BSB-LAN selbst mitbringt (PPS-Emulation, One-Wire-Fühler), bleibt
  draußen: Das sind keine Programme der Heizung.
- Beides wird beim Ausliefern aus dem gespeicherten Katalog abgeleitet. Ein
  Katalog aus einer älteren Fassung muss dafür **nicht** neu über den Bus
  eingelesen werden.
- **Behoben: Breite Tabellen schoben die ganze Seite zur Seite.** Die
  Wochentabelle der Zeitprogramme passt auf einem Tablet nicht nebeneinander;
  bisher wanderte deshalb auch die Kopfzeile aus dem Bild. Jetzt rollt jede
  Tabelle in ihrem eigenen Kasten.
- Ab Werk steht **keine** Adresse mehr drin. Eine fremde IP als Vorgabe führt
  nur dazu, dass jemand sucht, warum nichts ankommt; ohne Adresse sagt der
  Manager offen, dass sie fehlt, und zeigt auf die Einstellungen.

## 1.3.2

- **Meldungen bleiben stehen, bis man sie wegklickt.** Vorher verschwanden sie
  nach sechs Sekunden von selbst. Wer nach dem Stellen eines Wertes zur Heizung
  schaut statt auf den Bildschirm, verpasst genau die Auskunft, für die er den
  Knopf gedrückt hat – eine Fehlermeldung, die man nicht liest, ist keine.
  Jede Meldung hat jetzt ein ✕ und steht als abgesetzter Kasten da, rot beim
  Fehler, grün beim Erfolg.
- Steht die Meldung außerhalb des Bildes – etwa unter einer langen
  Parametertabelle –, rückt die Ansicht sie ins Blickfeld.
- Der Reiter „Werte“ hat ein eigenes Meldungsfeld. Bisher wurde dafür die
  Zeile „Zuletzt gelesen …“ missbraucht, die danach rot eingefärbt blieb.
- Bei den Zeitprogrammen überschreibt der Erfolg keinen Fehler mehr: Bricht das
  Speichern beim dritten Tag ab, steht jetzt beides da statt nur der grünen
  Hälfte. Der Hinweis auf die fehlende Freigabe ist ein Dauerhinweis geworden –
  als Meldung kam er nach jedem Wegklicken sofort zurück.

## 1.3.1

- **Behoben: Eine gelungene Änderung wurde als Fehler gemeldet.** BSB-LAN
  quittiert ein Schreiben mit dem Rückgabewert von `set()`, und der ist nicht
  selbsterklärend: **1 heißt gesetzt**, 2 „der Parameter ist nur lesbar“,
  0 „fehlgeschlagen“. Ich hatte aus Gewohnheit die Null für den Erfolg
  gehalten – damit wurde jede angenommene Änderung rot angestrichen.
- Die drei Fälle bekommen jetzt je eine eigene, zutreffende Meldung. Der
  Hinweis auf den BSB-LAN-Schalter erscheint nur noch dort, wo er passt: beim
  echten Fehlschlag.

## 1.3.0

- **Neu: der Reiter „Regler“.** Die Anlage bedienen wie am Gerät auf dem
  Kessel – mit derselben Gliederung. Die 27 Kategorien kommen aus der Regelung
  selbst; niemand muss etwas sortieren. Eine Kategorie anklicken genügt, der
  Manager liest ihre Werte und zeigt stellbare gleich mit passendem
  Bedienelement: Zahlenfeld bei Temperaturen, Auswahlliste bei Betriebsarten.
- **Neu: der Reiter „Zeitprogramme“.** Vier Programme mit je sieben Tagen und
  drei Schaltfenstern, als Tabelle aus Uhrzeitfeldern statt als Zeile
  Rautentext. Dazu *Montag auf Mo–Fr übertragen* und *auf alle Tage
  übertragen*, ein ✕ zum Leeren eines Tages und eine Rückfrage im Klartext.
- Gespeichert werden **nur geänderte Tage**; sie sind während der Bearbeitung
  markiert. Lehnt die Regelung einen Tag ab, hört der Manager auf, statt blind
  weiterzuschreiben.
- Der frühere Reiter „Steuerung“ geht darin auf. Wer einen bestimmten Parameter
  sucht statt in Kategorien zu blättern, findet ihn weiterhin unter *Auswahl*.

## 1.2.0

- **Behoben: In der Steuerung stand fast überall „–“.** Angezeigt wurden dort
  alle 161 stellbaren Parameter, gelesen aber nur die, die unter *Auswahl*
  stehen. Alles andere – und damit auch sämtliche Zeitschaltprogramme – blieb
  ohne Wert.
- Die Steuerung liest jetzt **auf Zuruf**: bis 25 angezeigte Parameter von
  selbst, darüber auf Knopfdruck und höchstens 40 auf einmal. Nach einer
  Änderung wird nur der geänderte Parameter nachgelesen.
- Auf Zuruf gelesene Werte gehen **nicht** nach MQTT. Entitäten entstehen
  weiterhin nur aus der Auswahl – ein einmal abgefragter Parameter soll keine
  Entität hinterlassen, die danach veraltet.
- **Zeitschaltprogramme lesbar gemacht.** Statt
  `06:00-22:00 ##:##-##:## ##:##-##:##` steht in der Tabelle nur noch
  `06:00-22:00`; das Eingabefeld enthält weiterhin die vollständige
  Zeichenkette, weil sie beim Schreiben genau so erwartet wird.
- Das Nachlesen merkt sich, was es schon versucht hat. Ohne dieses Gedächtnis
  hätte ein Parameter, der nie antwortet, eine Endlosschleife ausgelöst.

## 1.1.0

- **Behoben: Das Stellen blieb gesperrt, obwohl es freigegeben war.** Ich habe
  vor jedem Schreiben `buswritable` aus `/JI` abgefragt und daraus ein Verbot
  gemacht. Das war die falsche Zahl: In BSB-LAN entstehen diese Meldung und die
  Sperre, die beim Schreiben wirklich greift, aus **zwei verschiedenen
  Rechnungen**. Steht `DEFAULT_FLAG` auf `FL_RONLY`, meldet `/JI` eine Null,
  während die eigentliche Prüfung jeden Parameter durchlässt, der nicht selbst
  als nur-lesbar markiert ist.
- Gesperrt wird jetzt **allein über den Schalter dieses Add-ons**. Der Versuch
  geht an die Regelung, und deren Antwort zählt – lehnt sie ab, steht der
  Status in der Meldung, und falls BSB-LAN zusätzlich „nur lesen“ meldet, wird
  das als mögliche Ursache genannt. Hinterher als Erklärung, nicht vorher als
  Verbot.
- Der Reiter *Steuerung* sagt entsprechend, was Sache ist, statt auf einen
  Schalter zu zeigen, der längst steht.

## 1.0.1

- **Behoben: „JSON Parse error" beim Speichern.** Die Oberfläche rief ihre
  eigene Schnittstelle mit führendem Schrägstrich auf. Unter Ingress läuft die
  Seite aber nicht unter `/`, sondern unter
  `/api/hassio_ingress/<token>/` – die Aufrufe landeten damit bei Home
  Assistant selbst, das mit HTML antwortet. Alle Aufrufe gehen jetzt relativ
  und treffen das Add-on, egal unter welcher Adresse es läuft.

## 1.0.0

- **Erste Fassung.** Der Kesselmanager liest eine Heizungsregelung über
  BSB-LAN und bringt ausgewählte Parameter als Entitäten nach Home Assistant.
- **Parameterkatalog aus BSB-LAN**, nicht aus einer Datei: Was das Gerät
  ausliefert, ist per Definition das, was auch geflasht ist. Damit erscheinen
  die Namen der angepassten Parameterliste – aus „Parameter 72“ wird
  „Gerätebetriebsstunden“.
- **Auswahl per Häkchen** mit Suche, Kategoriefilter und einem Vorschlag für
  den Anfang.
- **Geräteklassen werden vorgeschlagen.** Temperaturen, Drücke und Leistungen
  bekommen die passende Klasse; Betriebsstunden, Starts und Verbräuche
  zusätzlich `total_increasing` – daraus baut Home Assistant von selbst eine
  Langzeitstatistik.
- **Stellen von Sollwerten** hinter zwei Schaltern, die beide ab Werk aus sind:
  dem in BSB-LAN und einem eigenen. Der Manager nimmt nur Parameter an, die die
  Regelung selbst als beschreibbar meldet, und fragt vor jeder Änderung nach.
- **Schonend zum Bus**: Abfragen in Bündeln zu zwölf Parametern mit Pausen
  dazwischen; ein Aussetzer kostet nur sein Bündel, nicht die ganze Runde.
- Entitäten hängen an der **Parameternummer**, nicht am Namen – eine
  Umbenennung kostet keine Historie.
