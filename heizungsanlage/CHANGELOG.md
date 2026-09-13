# Änderungen

## 1.26.4

- Prüfung nachgezogen, die zur Regel aus 1.26.3 nicht mehr passte. Die
  Fassung 1.26.3 ging mit einer roten Prüfung hinaus – meine Befehlskette hat
  den Fehlschlag verschluckt.

## 1.26.3

- **Erst lesen, dann erzwingen.** Ein Kachelwert, von dem der Manager noch
  nichts weiß, wird nicht mehr in die Auswahl gezogen. Sonst landete er dort,
  bevor sich zeigte, dass die Anlage ihn gar nicht beantwortet – und stünde in
  Home Assistant als leere Entität. Genau das ist der Vorlauftemperatur
  passiert, für die es hier keinen Fühler gibt.

## 1.26.2

- **Pflichtparameter werden im Betrieb nachgetragen.** Bisher geschah das nur
  beim Speichern der Auswahl – eine Kachel, die mit einer neuen Fassung
  dazukam, stand deshalb als „nicht ausgewählt“ da, bis jemand zufällig
  speicherte. Genau so ging es der Legionellenkachel.
- **„Noch nicht gelesen“ war eine Ausrede.** Seit der Manager mithört, statt
  selbst zu lesen, erfuhr er nie mehr, dass ein Kachelwert von der Anlage gar
  nicht beantwortet wird – die Vorlauftemperatur etwa. Kacheln außerhalb der
  Auswahl werden jetzt einmal am Tag selbst gelesen; damit steht dort wieder
  der Grund und nicht eine Vertröstung.

## 1.26.1

- **„Schreibzugriff in BSB-LAN gesperrt“ stimmte nicht.** Die Auskunft kam aus
  dem Feld `buswritable` von `/JI`, und das hängt an einem Übersetzungsschalter
  der Firmware: Es meldet 0, obwohl Schreiben erlaubt ist und funktioniert.
  Gelesen wird jetzt die Einstellung selbst – „Schreibzugriff (Ebene)“ –, und
  wenn sie sich nicht lesen lässt, steht dort *unbekannt* statt einer
  Behauptung.

## 1.26.0

- **Neue Kachel „Legionellen“** auf der Übersicht. Eine Legionellenschaltung,
  die stillschweigend auf „aus“ steht, merkt man sonst erst, wenn jemand
  danach sucht. Angezeigt wird der Rhythmus – „alle 7 Tage“ oder „aus“ –,
  nicht eine nackte Zahl in Tagen.
- Kacheln, die eine **Einstellung** zeigen statt eines Messwerts, werden nur
  stündlich erfragt statt alle fünf Minuten. Sie ändern sich nur, wenn jemand
  sie ändert.

## 1.25.2

- **Aufräumen nach 1.25.0:** Werte, die einmal mitgehört wurden und inzwischen
  nicht mehr gemeldet werden, verschwinden aus dem Zwischenspeicher. Sonst
  bliebe ein Wert von vorgestern mit dem Zeitstempel des Tages stehen, an dem
  er zufällig hereinkam.

## 1.25.1

- **Karteileichen unter demselben Präfix werden nicht mehr übernommen.** Beim
  Abonnieren liefert der Broker alle „retained“-Nachrichten auf einmal – auch
  die aus früheren Parameterlisten. Sie kamen in diesem Moment an und sahen
  damit taufrisch aus, obwohl BSB-LAN sie nie wieder auffrischt. Übernommen
  wird jetzt nur, was auch wirklich gemeldet wird.

## 1.25.0

- **Der Manager fragt nicht mehr doppelt.** Meldet BSB-LAN, hört er dessen
  Werte über MQTT mit, statt dieselben Parameter ein zweites Mal über den Bus
  zu holen. Möglich ist das, weil BSB-LAN „retained“ sendet: Ein frisches
  Abonnement bekommt sofort den letzten Stand jedes Werts. Auf dieser Anlage
  fällt damit etwa die Hälfte der Buslast weg.
- Über den Bus geht er nur noch für das, was dort nicht ankommt – und wenn ein
  Wert länger als das Dreifache des Abfragetakts nicht aufgefrischt wurde.
  Dann liest er ihn selbst, statt ihn stehen zu lassen.
- **Was die Übersicht braucht, ist jetzt Voraussetzung**: Die Kachelwerte
  trägt der Manager selbst in die Auswahl ein und lässt sie nicht abwählen –
  sie stehen mit dem Vermerk *für die Übersicht* in der Liste. Dazu ein
  **Mindesttakt von fünf Minuten** für genau diese Werte.
- Was die Anlage nicht beantwortet, wird nicht erzwungen. Eine
  Vorlauftemperatur ohne Fühler bliebe eine leere Entität.

## 1.24.1

- **Das Feld „Abfrageintervall“ heißt jetzt „Abfragetakt des Managers“** – und
  sagt dazu, wessen Abfrage gemeint ist: die des Add-ons für seine eigene
  Anzeige. Sie läuft auch dann, wenn BSB-LAN meldet.
- **Die Buslast-Schätzung zählt diesen Takt jetzt mit.** Sie war zu niedrig:
  Der Manager liest weiter, während BSB-LAN meldet – beide auf demselben Bus.
- Der Bereich *Melden* ist aufgeräumt: Erklärung nach oben, zwei Spalten statt
  drei mit Leerstelle, und der Meldeweg endlich breit genug für seinen Namen.

## 1.24.0

- **Der Meldeweg steht jetzt in den Einstellungen**, wie in den übrigen
  Add-ons: ein notify-Dienst von Home Assistant, dazu eine Wartezeit. Dafür
  braucht es keine Automation mehr, die man ein Jahr später niemandem mehr
  erklären kann.
- Gemeldet wird zweierlei: **der Adapter antwortet nicht** – und **er
  antwortet, meldet aber nichts**. Beides erst, wenn es die Wartezeit
  übersteht (ab Werk zehn Minuten), und mit Entwarnung, wenn es vorbei ist.
  Jede Störung genau einmal, auch über einen Neustart des Add-ons hinweg.
- **Probemeldung schicken** prüft den Weg, bevor man ihn braucht.
- Zweite neue Entität: **„BSB-LAN meldet“** – sie sagt, ob der Adapter beim
  Broker angemeldet ist. Meldet der Manager selbst, verschwindet sie wieder,
  statt eine Auskunft über einen Zustand zu geben, den es dann nicht gibt.

## 1.23.0

- **Neue Entität „BSB-LAN erreichbar“** (`binary_sensor`, Geräteklasse
  *connectivity*). BSB-LANs eigene Anmeldung kennt kein Verfügbarkeitsthema –
  fällt der Adapter aus, behalten seine Entitäten stundenlang ihren letzten
  Wert, ohne auszugrauen. Diese hier wird in jeder Betriebsart gemeldet und
  sagt, ob die Verbindung steht; damit lässt sich eine Automation daran hängen.
- Geprüft wird jede Minute über `/JI`. Das fragt nur das Gerät und belastet
  den Bus nicht.
- Kleinigkeit mit Folgen fürs Verständnis: Bei „BSB-LAN meldet“ steht jetzt,
  dass der Manager ihm sagt, **was und wie oft** – seit es die Takte gibt,
  stimmte das „was“ allein nicht mehr.

## 1.22.1

- **Das Feld heißt jetzt „Grundtakt“.** In der Auswahl steht bei jedem
  Parameter *Grundtakt*, gemeint war immer dieses Feld – es hieß aber
  „Sendeintervall“, und damit war der Zusammenhang nur zu erraten.
- Der Hinweis darunter sagt jetzt, was der Wert tut, statt eine Zahl zu
  empfehlen, die mit eigenen Takten ohnehin nicht mehr stimmt.

## 1.22.0

- **Erkennt den Zustand, der wie „läuft“ aussieht.** BSB-LAN kann auf jede
  HTTP-Abfrage antworten und trotzdem nichts melden – nach einem WLAN-Abriss
  macht es einen eigenen Zugangspunkt auf und überspringt MQTT, während sich
  das WLAN im Hintergrund wieder einbucht. In Home Assistant behalten die
  Entitäten dann stundenlang ihren letzten Wert, ohne dass etwas rot wird.
- Der Manager hört jetzt auf `<Präfix>/status` und sagt es, wenn dort
  „offline“ steht, obwohl das Gerät antwortet – mit dem Knopf **Adapter neu
  starten** daneben. Der Neustart geht über `/N` und lässt die Einstellungen
  im Gerät unangetastet.
- **Die Buslast wurde zu niedrig geschätzt.** BSB-LAN holt im Grundtakt alles,
  was in seiner Liste steht; ein eigener Takt kommt oben drauf, statt ihn zu
  ersetzen. Jetzt wird beides gezählt.

## 1.21.0

- **Jeder Parameter im eigenen Takt.** In der Auswahl steht je Parameter eine
  Spalte *Takt*. Wer dort etwas einträgt, bekommt diesen Wert vom Manager über
  `<Präfix>/poll` angefordert – dieselbe Schnittstelle, die man sonst mit
  Automationen in Home Assistant bedient. Der Rest läuft weiter im Grundtakt
  von BSB-LAN.
- **Und daneben steht, was es kostet:** Abfragen je Minute und der geschätzte
  Anteil an der Buszeit, gerechnet mit anderthalb Sekunden je Abfrage. Über
  60 % wird die Zahl orange.
- Der Grund für beides kommt von Frederik Holst: Eine Busabfrage dauert ein bis
  zwei Sekunden, vierzig Parameter im Minutentakt belegen den Bus vollständig –
  daher auch die Grenze von 40 Log-Parametern in BSB-LAN.

## 1.20.0

- **Die Broker-Adresse trägt jetzt auch bis zum Adapter.** Der Supervisor nennt
  dem Add-on `core-mosquitto` – ein Name aus dem Docker-Netz. Er wurde bisher
  unverändert an BSB-LAN weitergereicht, und ein ESP32 im Hausnetz kann ihn
  nicht auflösen: Der Adapter verbindet sich dann alle zehn Sekunden ins Leere
  und meldet nichts mehr. Jetzt ermittelt der Manager die IP-Adresse des
  Rechners, auf dem Home Assistant läuft, und gibt diese weiter.
- **Und wenn er keine findet, schreibt er nichts.** Weder Adresse noch
  Zugangsdaten. Eine laufende Verbindung gegen eine unmögliche zu tauschen ist
  schlimmer, als die Finger stillzuhalten – die Rückmeldung sagt es dann.
- **Die Fassung von BSB-LAN steht oben rechts**, neben den Anzeigen für
  Verbindung und MQTT. Gibt es eine neuere, erscheint daneben ein Hinweis mit
  Verweis auf die Veröffentlichungen. Verglichen wird mit derselben Quelle, die
  BSB-LAN selbst befragt, höchstens einmal am Tag.

## 1.19.1

- **Antwortet das Add-on nicht, steht das jetzt da.** Wer eine Antwort bekommt,
  die kein JSON ist – „502: Bad Gateway“ vom Vermittler etwa, während das
  Add-on neu startet –, las bisher „Unexpected non-whitespace character after
  JSON at position 3“. Jetzt steht dort, was los ist.
- **Der Bericht über das Speichern bleibt stehen.** Schlug danach das Nachlesen
  fehl, überschrieb dessen Meldung die wichtigere: welche Tage angekommen sind
  und welcher nicht. Beides steht jetzt nebeneinander – und dazu der Satz, dass
  die Tabelle in diesem Fall Eingaben zeigt und nicht den Stand der Anlage.
- Das Nachlesen versucht es nach zweieinhalb Sekunden ein zweites Mal: Direkt
  nach dem Schreiben ist der Bus belegt, und ein neu startendes Add-on ist
  Sekunden später wieder da.

## 1.19.0

- **Die Parameterliste ist nach Kategorien gegliedert und klappt auf.** In der
  Reihenfolge, in der die Regelung ihre Kategorien selbst führt. Jede Zeile
  sagt, wie viele Parameter dahinterstecken und wie viele davon angehakt sind.
  Zugeklappt sind 27 Überschriften eine Übersicht – 242 Zeilen am Stück waren
  eine Wand. Wer sucht oder filtert, bekommt die Treffer offen hingelegt.
- Die Spalte *Kategorie* entfällt: Sie steht jetzt als Überschrift darüber.
- **Aufgeräumt.** Die fünf Felder von BSB-LAN stehen in drei Spalten statt
  vier plus einem Nachzügler, und die Knöpfe für die Liste in BSB-LAN haben
  eine eigene Zeile bekommen, statt sich zu viert nebeneinander zu drängen.

## 1.18.0

- **Speichern speichert dort, wo es wirkt.** Meldet BSB-LAN, gehen Präfix,
  Geräte-ID, Intervall, Einheiten und MQTT-Art beim Speichern gleich ins Gerät.
  Vorher stand das neue Präfix im Add-on, während BSB-LAN weiter unter dem
  alten meldete – dafür gab es einen zweiten Knopf, den man kennen musste. Die
  Meldung sagt hinterher, was im Gerät geändert wurde.
- Der Knopf *BSB-LAN einrichten* entfällt damit. Wer das Gerät zurückgesetzt
  hat, drückt einfach wieder Speichern: Geschrieben wird ohnehin nur, was sich
  unterscheidet.
- **Die Listenknöpfe stehen jetzt bei der Liste.** *Auswahl an BSB-LAN geben*
  und *Liste aus BSB-LAN übernehmen* gehören zu den Parametern, nicht zur
  Melderwahl – und erscheinen nur, wenn BSB-LAN auch meldet.

## 1.17.1

- **Beide MQTT-Präfixe stehen jetzt an einer Stelle.** Das des Managers lag
  unter *Einstellungen*, das von BSB-LAN unter *Home Assistant* – zwei Felder
  mit derselben Aufgabe, einen Reiter auseinander. Sie stehen nun beide unter
  der Frage, wer meldet, und sichtbar ist immer nur das Feld, das gerade gilt.
- Die Knöpfe *BSB-LAN einrichten*, *Auswahl an BSB-LAN geben* und *Liste aus
  BSB-LAN übernehmen* stehen jetzt unter dem Speichern, nicht darüber – erst
  einstellen, dann sichern, dann übergeben.

## 1.17.0

- **Die Oberfläche spricht jetzt auch Englisch.** Welche Sprache erscheint,
  entscheidet Home Assistant; das Add-on fragt beim Laden nach. Umschalten muss
  niemand etwas.
- Deutsch bleibt die Quelle: Der deutsche Satz ist zugleich der Schlüssel. Ein
  vergessener Eintrag fällt damit nicht aus – er bleibt deutsch stehen, statt
  als Platzhalter zu erscheinen. Eine weitere Sprache ist eine Datei unter
  `frontend/sprachen/`, am Code ändert sich nichts.
- **Was die Regelung sagt, bleibt unübersetzt.** Kategorien, Parameternamen und
  Auswahlwerte kommen aus dem Gerät und stehen da wie am Kessel. Vier von 27
  Kategorien zu übersetzen ergäbe eine Scheinordnung.
- Dafür mussten drei Sätze umgebaut werden, die sich Fettdruck und Text teilten:
  Zerschnitten ergibt ein Satz keine übersetzbare Einheit, und im Englischen
  steht die Zahl an anderer Stelle als im Deutschen.
- Auch die **Rückfragen vor dem Schreiben** sind übersetzt. Die zeigt der
  Browser selbst an, nicht die Seite – sie gehen an der Mechanik vorbei und
  brauchten einen eigenen Weg. Ausgerechnet die Sicherheitsabfragen deutsch zu
  lassen wäre die falsche Stelle zum Sparen.

## 1.16.1

- **Behoben: Das Logo trug noch den alten Namen.** Im Add-on-Store stand
  „Kesselmanager“ – seit der Umbenennung falsch, und niemandem aufgefallen,
  weil das Bild niemand liest, sondern nur sieht.
- Icon und Logo haben jetzt **Quellen** (`doku/icon.svg`, `doku/logo.svg`) samt
  Anleitung, wie man sie neu erzeugt. Vorher gab es nur die fertigen PNG.
- Das Repository ist nach dem Muster der übrigen Add-ons vervollständigt:
  README auf Deutsch und Englisch mit dem Knopf zum Hinzufügen des
  Repositories, ein kurzes README im Add-on-Verzeichnis, und die Bilder unter
  `doku/bilder/`.
- Der Kaffee-Knopf steht jetzt auch hier, wie in den übrigen Add-ons.
- **Wiederhergestellt: der Haftungsausschluss im README.** Beim Aufteilen in
  zwei Sprachen ist er verlorengegangen – er steht jetzt in beiden Fassungen.

## 1.16.0

- **Das Add-on sagt jetzt an, wo es zu erreichen ist.** Beim Verbinden mit
  MQTT geht eine bleibende Nachricht auf `heizungsanlage/anschrift` mit der
  eigenen Anschrift im Docker-Netz.
- Hintergrund: Der Hostname lautet `<repo-hash>-heizungsanlage`, und der Hash
  hängt am Repository, aus dem das Add-on stammt. Ein anderes Add-on kann ihn
  nicht raten, und die Add-on-Liste gibt der Supervisor nur mit
  Verwalterrechten heraus. Damit der Heizungsplaner die Übernahme-Schnittstelle
  findet, ohne solche Rechte zu verlangen, nennt sie das Add-on selbst.
- Für alle, die den Heizungsplaner nicht einsetzen, ändert sich nichts.

## 1.15.1

- **Behoben: Die Rückfrage beim Umschalten nannte einen falschen Namen.** Sie
  fragte „Brauchwassertemperatur-Reduziertsollwert auf ‚Programm 2‘ stellen?“ –
  so heißt Parameter 70 in Weishaupts Parameterliste, und das ist schlicht
  falsch. Jetzt steht dort **Betriebsart**, und der Listenname erscheint nur
  noch als Fußnote im Hinweis.
- **Die Rückfrage nennt jetzt die Folge, nicht nur den Wert.** „Programm 2“
  sagt niemandem, was danach anders ist – also steht daneben: *Danach gilt
  „Zeitschaltprogramm 2“ für die Heizung.* Bei Standby, Sommer oder
  Dauerbetrieb: *Danach gilt kein Zeitprogramm.*

## 1.15.0

- **Eine Tabelle statt zweier.** Links die Auswahl, rechts der zuletzt
  gelesene Wert – vorher standen beide Listen untereinander, und man musste
  zwischen ihnen hin- und herspringen, um zu sehen, ob ein Häkchen auch einen
  Wert trägt.
- **Sortieren durch Klick auf die Spaltenköpfe**, in beide Richtungen: nach
  Nummer, Name, Kategorie, Einheit oder Wert. Nach Wert wird der Größe nach
  sortiert; was keinen hat, steht hinten.
- **Mehr Filter:** nur stellbare, nur lesbare, nur ausgewählte, nur nicht
  ausgewählte, nur mit Wert – und „ausgewählt, aber ohne Wert“. Der letzte
  findet in einem Griff, was in Home Assistant als leere Entität landet.

## 1.14.1

- **Behoben: Die Einheiten-Einstellung wurde nie an BSB-LAN geschrieben** und
  in der Lagemeldung stand immer „nicht für Home Assistant“. Der Optionsnummer
  58 fehlte der Eintrag in der Zuordnung – derselbe Fehler wie zuvor bei
  Benutzer und Passwort: Was dort nicht steht, wird stillschweigend
  übersprungen. Jetzt prüft ein Test, dass jede Einstellung, die das
  Einrichten setzen will, auch eine Optionsnummer hat.

## 1.14.0

- **Aus drei Reitern wird einer: „Home Assistant“.** *Werte*, *Auswahl* und
  die Melde-Einstellungen drehten sich um dieselbe Frage – was geht nach Home
  Assistant, wer schickt es, und was steht gerade drin. Jetzt eine Seite, von
  oben nach unten in der Reihenfolge, in der man sie braucht. Unter
  *Einstellungen* bleibt, was die Anlage selbst betrifft: Verbindung,
  Schreibzugriff, Anzeige, Katalog.
- Gespeichert wird dort, wo die Felder stehen – ein Knopf, nicht zwei.
- **Behoben: Die Lagemeldung warnte vor einer Doppelung, die abgestellt war.**
  Sie sah nur, dass BSB-LAN sendet, nicht, dass der Manager sich deshalb
  zurückhält. Jetzt steht dort eine Bilanz statt einer Warnung – und
  umgekehrt fällt auf, wenn BSB-LAN melden soll, es aber nicht tut.
- Der Eintrag „MQTT-Präfix“ unter *Einstellungen* heißt jetzt „MQTT-Präfix des
  Managers“: Er gilt nur, solange der Manager selbst meldet.

## 1.13.0

- **Beim Ändern der Liste räumt der Manager jetzt hinter sich auf.** Fällt ein
  Parameter weg, meldet er ihn in Home Assistant ab, bevor er die neue Liste
  schreibt, und meldet danach die neue an. Die Reihenfolge ist kein
  Feinschliff: BSB-LAN widerruft nur, was es *gerade* führt. Wer erst die
  Liste ändert, widerruft die neuen Einträge und lässt für jeden entfernten
  eine Entität zurück – „retained“ im Broker und damit dauerhaft in Home
  Assistant, ohne dass sie je wieder jemand abmeldet.

## 1.12.3

- Dokumentiert, was an der lebenden Anlage herauskam: **BSB-LAN nimmt
  höchstens 40 Log-Parameter** und lässt alles Weitere stillschweigend fallen.
  Der Manager meldet nach dem Zurücklesen, welche Nummern nicht angekommen
  sind.

## 1.12.2

- **Behoben: Das Schreiben nach BSB-LAN tat gar nichts.** Zurückgegeben wurde
  der vollständige Eintrag, wie `/JL` ihn liefert – mit `type`, `format`,
  `category` und `name`. Darauf antwortet BSB-LAN mit einer leeren Struktur
  und ändert nichts: kein Fehler, keine Meldung, ein stilles Nein. Jetzt gehen
  nur `parameter` und `value` hinaus, und das wird angenommen.
- Aufgefallen ist es nur, weil nach jedem Schreiben zurückgelesen wird. Ohne
  das hätte die Oberfläche „geschrieben“ gemeldet und nichts wäre geschehen.

## 1.12.1

- **Behoben: Das Umschalten wirkte erst beim nächsten Verbindungsaufbau.** Wer
  auf „BSB-LAN meldet“ stellte, sah seine alten Entitäten noch stehen – und
  damit genau die Doppelung, die er gerade abstellen wollte. Jetzt wird beim
  Speichern der Einstellungen sofort abgeräumt beziehungsweise angemeldet.

## 1.12.0

- **Neu: BSB-LAN kann das Melden übernehmen, der Manager richtet es ein.**
  Unter *Einstellungen → Wer meldet nach Home Assistant?* wählst du zwischen
  beiden. Entscheidest du dich für BSB-LAN, schreibt der Manager dessen
  MQTT-Einstellungen (Broker, Zugangsdaten, Präfix, Geräte-ID, Intervall,
  Einheiten, Auto-Discovery) und gibt die Auswahl als Log-Parameterliste
  weiter – und meldet seine eigenen Entitäten ab, damit nicht zwei Absender
  dieselbe Anlage doppeln.
- **Broker, Benutzer und Passwort kommen von Home Assistant selbst.** Der
  Supervisor reicht sie dem Add-on durch; sie gehen an BSB-LAN, werden aber
  nirgends angezeigt oder hier gespeichert. In der Rückmeldung heißen sie nur
  „Zugangsdaten“.
- *Liste aus BSB-LAN übernehmen* holt umgekehrt, was dort schon eingetragen
  ist, in die Auswahl – mit den Namen aus dem Katalog.
- Nach jedem Schreiben wird zurückgelesen. BSB-LAN kürzt lange Listen
  stillschweigend; was das Gerät danach führt, zählt, nicht was wir ihm
  geschickt haben.

## 1.11.1

- **Behoben: „BSB-LAN meldet nichts von sich aus“ – obwohl es meldete.** Ich
  hatte die Optionsnummer der Weboberfläche mit der aus `/JL` verwechselt: Der
  Log-Modus ist dort Option 53, die 11 sind die Bustelegramme. Eine Zahl
  daneben, und die Auskunft war das Gegenteil der Wahrheit.

## 1.11.0

- **Auch beim Trinkwasserprogramm steht jetzt, ob es gilt.** Es hängt nicht an
  der Programmwahl, sondern an einem eigenen Schalter („Warmwasser-Mode“:
  *24h/Tag*, *Heizprogramme mit Vorverlegung*, *Warmwasserprogramm*). Nur beim
  letzten gilt die Wochentabelle – und umstellen kannst du ihn gleich dort.
  Die Falle dabei: Auch „Funktion Zirkulationspumpe“ kennt den Wert
  *Warmwasserprogramm*, schaltet aber die Pumpe. Unterschieden wird am Namen
  des Parameters, nicht an seinen Werten.
- **Neu unter Einstellungen: „Wer meldet nach Home Assistant?“** BSB-LAN
  bringt eigenes MQTT mit, samt automatischer Anmeldung. Ist beides an, melden
  zwei Programme dieselbe Anlage – doppelte Entitäten, doppelte Buslast. Der
  Manager liest jetzt BSB-LANs eigene Einstellungen und schreibt hin, was dort
  läuft: wie viele Parameter, wie oft, an welchen Broker.
- Dabei gefunden: **BSB-LAN 5.1.18 liefert unter `/JL` kaputtes JSON**, wenn
  keine One-Wire- oder DHT-Pins gesetzt sind – ein Wert bleibt unbeendet. Das
  wird beim Lesen geflickt, sonst ginge die ganze Auskunft verloren.

## 1.10.1

- **Behoben: „kein Fühler angeschlossen“ stand auch dort, wo es keinen Fühler
  geben kann.** Bei den Ferienperioden zum Beispiel – da steht ein Datum, kein
  Messwert. BSB-LAN meldet für beides dasselbe `---`; was es bedeutet, hängt
  daran, wer den Wert füllt. Jetzt heißt es bei einer Ferienperiode *keine
  Ferien eingetragen*, bei einem stellbaren Parameter *nicht eingestellt* und
  nur bei einem gelesenen Messwert *kein Fühler angeschlossen*.
- Weiß der Manager nicht, was für ein Parameter vorliegt, sagt er schlicht
  *kein Wert hinterlegt* – lieber wenig als etwas Falsches.

## 1.10.0

- **Ein Reiter statt zwei.** Aus „Regler“ wird *Regelung*, und die
  Zeitschaltprogramme stehen jetzt darin – im Bereich *Zeitprogramme*, wie
  jede andere Kategorie auch. Sie zweimal im Menü zu führen war einmal
  praktisch und dann nur noch doppelt.
- **Die Zahlen sind aus den Knöpfen verschwunden.** Neben „Zeitschaltprogramm
  1“ noch eine 7 zu setzen half niemandem – es sah aus wie ein zweiter Name.
- **Man sieht, welches Programm gerade läuft.** Über der Wochentabelle steht
  *läuft gerade* oder *läuft gerade nicht*, und daneben die Auswahl, um
  umzuschalten – auch auf Standby, Sommer oder Dauerbetrieb.
- Den Parameter dafür findet der Manager an seinen **Auswahlwerten**, nicht am
  Namen: Wo mehrfach „Programm <Zahl>“ zur Wahl steht, ist die Programmwahl.
  In Weishaupts angepasster Liste heißt dieser Parameter
  „Brauchwassertemperatur-Reduziertsollwert“ – schlicht falsch, und ein guter
  Grund, Namen nicht zu glauben. Findet sich nichts Passendes, behauptet die
  Oberfläche auch nichts.

## 1.9.0

- **Das Menü im Reiter „Regler“ hat jetzt zwei Stufen.** Oben die Bereiche –
  *Heizen*, *Trinkwasser*, *Wärmeerzeuger* und so fort –, darunter die
  Kategorien des gewählten Bereichs, darunter das Formular. Vorher standen
  alle 27 Kategorien gleichzeitig da: vollständig, aber zum Suchen.
- Ein Bereich mit genau einer Kategorie öffnet sie direkt – *Trinkwasser* führt
  ohne zweiten Klick zum Warmwasser.
- Der Wechsel des Bereichs schließt das Formular: Es gehörte zu einer
  Kategorie, die im neuen Bereich gar nicht steht.
- *Anpassen* zeigt weiterhin alles auf einmal mit Häkchen – dort soll man ja
  gerade das sehen, was man ausgeblendet hat.

## 1.8.0

- **Der Regler zeigt sofort etwas an.** Bisher stand beim Öffnen einer
  Kategorie „wird gelesen …“, bis der Bus geantwortet hatte – mehrere Sekunden,
  jedes Mal. Mit dem neuen Haken unter *Einstellungen → Anzeige* steht gleich
  da, was zuletzt gelesen wurde, mit Altersangabe („vor 7 Minuten gelesen ·
  wird aufgefrischt …“), und der frische Stand kommt im Hintergrund nach.
  Dasselbe in den Zeitprogrammen.
- **Ab Werk aus.** Wer seine Anlage auch am Gerät auf dem Kessel verstellt,
  sähe für diese Sekunden den alten Wert. Wessen Heizung nur über Home
  Assistant läuft, schaltet es ein und merkt nie einen Nachteil.
- Eine Zahl, die gerade getippt wird, überlebt das Auffrischen – samt Cursor.
  In den Zeitprogrammen werden nur unangetastete Tage aufgefrischt; geänderte
  Zeiten gehen nicht verloren.
- Wechselt man die Kategorie, während eine Abfrage noch läuft, landet deren
  Antwort nicht mehr auf dem neuen Bildschirm.
- Die Dokumentation hatte zweimal dieselbe Überschrift „Zusammenspiel mit dem
  Heizungsplaner“ – die Schnittstelle heißt jetzt „Übernahme durch andere
  Add-ons“.

## 1.7.0

- **Das Kategorienmenü ist gruppiert.** 27 Knöpfe nebeneinander waren eine
  Wand, keine Übersicht. Sie stehen jetzt unter *Zeitprogramme*, *Heizen*,
  *Trinkwasser*, *Wärmeerzeuger*, *Speicher*, *Wartung & Diagnose*, *Anlage &
  Konfiguration* – und alles, was BSB-LAN selbst mitbringt (eigene Parameter,
  PPS-Emulation, One-Wire-Fühler) unter *BSB-LAN selbst*. Die Zuordnung kommt
  aus den Namen, die die eigene Anlage liefert; was in keine Gruppe passt,
  landet unter *Weitere* statt unter den Tisch.
- **Kategorien lassen sich ausblenden.** Über *Anpassen* im Reiter „Regler“.
  Jede Anlage schleppt Ecken mit, die ihr Besitzer nie braucht – bei der einen
  die Kaskade, bei der anderen die PPS-Emulation. Ausgeblendet heißt nicht
  gelöscht: Der Hinweis oben nennt die Zahl, und ein Klick holt alles zurück.
- **Ausgewählte Parameter, die es nicht gibt, fallen jetzt auf.** Steht in der
  Auswahl eine Nummer, die der Katalog nicht kennt, sagt der Reiter das – samt
  Knopf zum Entfernen. Solche Einträge liefern nie einen Wert, und eine
  Entität auf „unbekannt“ sieht aus wie ein kalter Fühler.

## 1.6.2

- **„Kein Wert“ heißt jetzt, warum.** Eine Regelung antwortet auf drei Arten
  mit nichts, und das bedeutet Verschiedenes: `error 7` heißt „diesen
  Parameter kennt die Anlage nicht“ – der Vorlauffühler einer Anlage, die
  keinen hat. `---` heißt „Parameter vorhanden, Klemme leer“. Beides stand
  vorher als blasser Strich da, nicht von „noch nicht gelesen“ zu
  unterscheiden. Übersicht, Werte und Regler schreiben den Grund jetzt
  daneben.
- **Behoben: `---` wäre als Text nach Home Assistant gegangen.** Ein Sensor
  mit Geräteklasse `temperature` kann damit nichts anfangen und fällt auf
  „nicht verfügbar“. Jetzt wird daraus, wie bei jedem fehlenden Wert, ein
  sauberes „unbekannt“.

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
