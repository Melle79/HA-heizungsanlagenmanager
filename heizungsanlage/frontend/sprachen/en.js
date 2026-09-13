// Englisch. Eine Sprachdatei besteht aus zwei Teilen und sonst nichts:
//
//   woerter  – feste Texte, Schlüssel ist der deutsche Originaltext
//   muster   – Texte mit Zahlen oder Namen darin, als reguläre Ausdrücke
//
// Wer eine Sprache ergänzen will, kopiert diese Datei nach `<code>.js`,
// übersetzt die rechte Seite und ist fertig – am Code ändert sich nichts.
// Ein fehlender Eintrag fällt nicht aus: Er bleibt deutsch stehen.
//
// Auch die Meldungen des Backends stehen hier. Sie kommen als fertiger Satz
// aus Python und landen als Text in der Seite – für die Übersetzung ist das
// dasselbe wie eine Überschrift.

window.SPRACHEN = window.SPRACHEN || {};
window.SPRACHEN.en = {
  // Zahlen und Uhrzeiten: „52.7“ und „14:00“ statt „52,7“ und „2:00 pm“.
  locale: 'en-GB',

  woerter: {
  // ── Kopf und Reiter ──
  "Heizungsanlagenmanager": "Heating System Manager",
  "Übersicht": "Overview",
  "Regelung": "Controller",
  "Home Assistant": "Home Assistant",
  "Einstellungen": "Settings",
  "BSB-LAN verbunden": "BSB-LAN connected",
  "BSB-LAN fehlt": "BSB-LAN missing",
  "MQTT verbunden": "MQTT connected",
  "kein MQTT": "no MQTT",

  // ── Übersicht ──
  "Die Anlage": "The system",
  "Am Bus": "On the bus",
  "Noch nichts gefunden": "Nothing found yet",
  "Kessel": "Boiler",
  "Vorlauf": "Flow",
  "Außen": "Outside",
  "Außen gedämpft": "Outside, damped",
  "Betriebsstunden": "Operating hours",
  "Brennerstarts": "Burner starts",
  "liefert diese Anlage nicht": "this system does not provide it",
  "kein Fühler angeschlossen": "no sensor connected",
  "keine Ferien eingetragen": "no holiday entered",
  "kein Datum eingetragen": "no date entered",
  "nicht eingestellt": "not set",
  "kein Wert vorhanden": "no value available",
  "kein Wert hinterlegt": "no value stored",
  "noch nicht gelesen": "not read yet",
  "nur lesen": "read only",

  // ── Regelung ──
  "Die Regelung, Kategorie für Kategorie": "The controller, category by category",
  "Dieselbe Gliederung, die auch am Gerät auf dem Kessel steht. Wähle einen Bereich, darunter die Kategorie – die Werte stehen dann unten, stellbare gleich zum Ändern.":
    "The same structure you find on the boiler's own panel. Pick an area, then the category – the values appear below, writable ones ready to change.",
  "Anpassen": "Customise",
  "Fertig": "Done",
  "Wähle oben einen Bereich.": "Pick an area above.",
  "Neu lesen": "Read again",
  "wird gelesen …": "reading …",
  "läuft …": "running …",
  "Erst einen Wert eingeben": "Enter a value first",
  "stellen": "set",
  "unter Einstellungen freigeben": "release under Settings",

  // Bereiche des Menüs
  "Zeitprogramme": "Time programmes",
  "Heizen": "Heating",
  "Trinkwasser": "Domestic hot water",
  "Wärmeerzeuger": "Heat generator",
  "Speicher": "Storage",
  "Wartung & Diagnose": "Maintenance & diagnostics",
  "Anlage & Konfiguration": "System & configuration",
  "BSB-LAN selbst": "BSB-LAN itself",
  "Weitere": "Other",

  // ── Zeitprogramme ──
  "Je Tag drei Schaltfenster. Ein leeres Fenster heißt: wird nicht benutzt. Geändert wird erst beim Speichern, und auch dann nur die Tage, die du angefasst hast.":
    "Three switching windows per day. An empty window means: not in use. Nothing changes until you save, and even then only the days you touched.",
  "Tag": "Day",
  "Fenster 1": "Window 1",
  "Fenster 2": "Window 2",
  "Fenster 3": "Window 3",
  "Montag": "Monday", "Dienstag": "Tuesday", "Mittwoch": "Wednesday",
  "Donnerstag": "Thursday", "Freitag": "Friday", "Samstag": "Saturday",
  "Sonntag": "Sunday",
  "Keine Änderungen": "No changes",
  "Geänderte Tage speichern": "Save changed days",
  "Montag auf Mo–Fr übertragen": "Copy Monday to Mon–Fri",
  "Montag auf alle Tage übertragen": "Copy Monday to all days",
  "Verwerfen und neu lesen": "Discard and read again",
  "alle Fenster dieses Tages leeren": "clear all windows of this day",
  "läuft gerade": "currently running",
  "läuft gerade nicht": "not currently running",
  "Betriebsart": "Operating mode",
  "Warmwasser-Betrieb": "Hot water mode",
  "Das Stellen ist nicht freigegeben": "Writing is not released",
  "Danach gilt die Wochentabelle dieses Programms.":
    "The weekly table of this programme will then apply.",
  "Zum Speichern das Stellen unter „Einstellungen“ freigeben.":
    "To save, release writing under “Settings”.",

  // ── Home Assistant: wer meldet ──
  "Wer meldet nach Home Assistant?": "Who publishes to Home Assistant?",
  "BSB-LAN bringt eigenes MQTT mit, samt automatischer Anmeldung in Home Assistant. Ist das eingeschaltet, melden zwei Programme dieselbe Anlage – doppelte Entitäten, und beide fragen denselben Bus ab.":
    "BSB-LAN carries its own MQTT, including auto-discovery for Home Assistant. With that switched on, two programs publish the same system – duplicate entities, and both poll the same bus.",
  "Der Manager meldet.": "The manager publishes.",
  "Er liest die Auswahl im eigenen Takt und legt die Entitäten selbst an. Steht das Add-on, kommt nichts an.":
    " It reads the selection on its own clock and creates the entities itself. While the add-on is stopped, nothing arrives.",
  "BSB-LAN meldet.": "BSB-LAN publishes.",
  "Der Manager sagt ihm nur, was – und hält sich mit eigenen Entitäten zurück. BSB-LAN fragt den Bus ohnehin ab, meldet häufiger und legt auch Bedienelemente an.":
    " The manager only tells it what – and holds back its own entities. BSB-LAN polls the bus anyway, publishes more often and also creates controls.",
  "Speichern": "Save",
  "Topic-Präfix des Managers": "The manager's topic prefix",
  "Unter diesem Präfix legt der Manager seine MQTT-Themen ab.":
    "The manager files its MQTT topics under this prefix.",
  "Topic-Präfix in BSB-LAN": "Topic prefix in BSB-LAN",
  "Geräte-ID (optional)": "Device ID (optional)",
  "Sendeintervall (Sekunden)": "Publish interval (seconds)",
  "BSB-LAN fragt in diesem Takt ab. 60 Sekunden sind für eine Heizung reichlich.":
    "BSB-LAN polls at this rate. 60 seconds is plenty for a heating system.",
  "Einheiten": "Units",
  "für Home Assistant": "for Home Assistant",
  "landesspezifisch": "country-specific",
  "keine": "none",
  "MQTT-Art": "MQTT flavour",
  "Einfach": "Plain",
  "JSON": "JSON",
  "Rich JSON": "Rich JSON",
  "Broker, Benutzer und Passwort kommen von Home Assistant selbst – dieselben, mit denen dieses Add-on am Broker hängt. Sie werden beim Speichern durchgereicht und hier weder angezeigt noch gespeichert; abtippen musst du nichts.":
    "Broker, user and password come from Home Assistant itself – the same ones this add-on uses. They are passed through when you save and are neither shown nor stored here; you don't have to type anything.",
  "Auswahl an BSB-LAN geben": "Hand the selection to BSB-LAN",
  "Liste aus BSB-LAN übernehmen": "Take over the list from BSB-LAN",
  "Der Manager hält sich zurück und meldet nichts Eigenes.":
    "The manager holds back and publishes nothing of its own.",

  // ── Home Assistant: Auswahl und Werte ──
  "Parameter auswählen": "Choose parameters",
  "Angehakt heißt: Der Wert wird regelmäßig gelesen und als Entität nach Home Assistant gemeldet. Einheit und Geräteklasse schlägt der Manager aus dem Datentyp vor – Betriebsstunden und Zählerstände bekommen automatisch eine Langzeitstatistik.":
    "Ticked means: the value is read regularly and published to Home Assistant as an entity. Unit and device class are proposed from the data type – operating hours and counters automatically get long-term statistics.",
  "Suche": "Search",
  "Name oder Nummer …": "Name or number …",
  "Kategorie": "Category",
  "alle": "all",
  "Filter": "Filter",
  "alle Parameter": "all parameters",
  "nur stellbare": "writable only",
  "nur lesbare": "read-only only",
  "nur ausgewählte": "selected only",
  "nur nicht ausgewählte": "unselected only",
  "nur mit Wert": "with a value only",
  "ausgewählt, aber ohne Wert": "selected but without a value",
  "Auswahl speichern": "Save selection",
  "Sinnvolle Auswahl vorschlagen": "Propose a sensible selection",
  "Alle aufklappen": "Expand all",
  "Alle zuklappen": "Collapse all",
  "Liste in BSB-LAN:": "List in BSB-LAN:",
  "Vorschlag übernommen – noch nicht gespeichert": "Proposal applied – not saved yet",
  "Nr": "No",
  "Name": "Name",
  "Einheit": "Unit",
  "zuletzt gelesen": "last read",
  "Keine Treffer.": "No matches.",
  "Jetzt lesen": "Read now",
  "liest …": "reading …",
  "Noch nichts ausgewählt.": "Nothing selected yet.",
  "stellbar": "writable",
  "Eintrag entfernen": "Remove entry",
  "Einträge entfernen": "Remove entries",
  "Diese Kategorie ist leer.": "This category is empty.",

  // ── Einstellungen ──
  "Verbindung zu BSB-LAN": "Connection to BSB-LAN",
  "Adresse": "Address",
  "Die Adresse, unter der die Weboberfläche von BSB-LAN erreichbar ist – meist die IP, oft auch":
    "The address where the BSB-LAN web interface answers – usually the IP, often also",
  "Passkey (falls gesetzt)": "Passkey (if set)",
  "Abfrageintervall (Sekunden)": "Polling interval (seconds)",
  "Eine Heizung ist träge – fünf Minuten reichen. Jede Abfrage belegt den Bus.":
    "A heating system is slow – five minutes is enough. Every query occupies the bus.",
  "Schreibzugriff": "Write access",
  "Stellen von Parametern erlauben": "Allow setting parameters",
  "Zwei Schalter müssen dafür stehen: dieser und der in BSB-LAN selbst. Beide sind ab Werk aus, und das mit Absicht – ein falscher Sollwert lässt im Winter eine Wohnung auskühlen.":
    "Two switches have to be on: this one and the one in BSB-LAN itself. Both are off by default, and deliberately so – a wrong setpoint lets a flat go cold in winter.",
  "Einstellungen speichern": "Save settings",
  "Gespeichert": "Saved",
  "BSB-LAN antwortet, meldet aber nichts.": "BSB-LAN answers, but publishes nothing.",
  "Der Adapter ist erreichbar, hat sich beim Broker aber nicht angemeldet. Das kommt nach einem WLAN-Abriss vor: BSB-LAN macht dann einen eigenen Zugangspunkt auf und lässt MQTT bis zum Neustart aus.":
    "The adapter is reachable but has not signed in with the broker. This happens after a Wi-Fi dropout: BSB-LAN then opens an access point of its own and leaves MQTT off until it restarts.",
  "Adapter neu starten": "Restart adapter",
  "BSB-LAN neu starten?": "Restart BSB-LAN?",
  "Die Einstellungen im Gerät bleiben unangetastet. Für etwa eine Minute ist es nicht erreichbar.":
    "The settings in the device are left untouched. It will be unreachable for about a minute.",
  "Neustart ausgelöst – das dauert eine Minute": "Restart triggered – this takes a minute",
  "Takt": "Rate",
  "Grundtakt": "Base rate",
  "1 min": "1 min",
  "2 min": "2 min",
  "5 min": "5 min",
  "15 min": "15 min",
  "1 Stunde": "1 hour",
  "Für BSB-LAN gibt es eine neuere Fassung": "A newer version of BSB-LAN is available",
  "Nachlesen fehlgeschlagen.": "Reading back failed.",
  "Das Add-on hat nicht geantwortet – vermutlich startet es gerade neu. In einem Moment noch einmal versuchen.":
    "The add-on did not answer – it is probably restarting. Try again in a moment.",
  "Die Anmeldung ist abgelaufen – die Seite einmal neu laden.":
    "The session has expired – reload the page.",
  "Die Tabelle zeigt deine Eingaben, nicht den Stand der Anlage.":
    "The table shows your entries, not the state of the system.",
  "Gespeichert – BSB-LAN stand schon richtig":
    "Saved – BSB-LAN was already right",
  "Anzeige": "Display",
  "Zuletzt gelesene Werte beim Öffnen sofort zeigen":
    "Show the values read last as soon as a category opens",
  "Eine Kategorie über den Bus zu lesen dauert ein paar Sekunden. Mit diesem Haken steht sofort da, was zuletzt gelesen wurde – mit Altersangabe –, und der frische Stand kommt im Hintergrund nach.":
    "Reading a category over the bus takes a few seconds. With this ticked, what was read last appears at once – with its age – while fresh values are fetched in the background.",
  "Ab Werk aus, und zwar aus einem Grund: Wer die Anlage auch am Gerät auf dem Kessel verstellt, sieht für diese paar Sekunden den alten Wert. Läuft bei dir alles über Home Assistant, kann das nicht schiefgehen.":
    "Off by default, for a reason: if you also adjust the system at the boiler's own panel, you see the old value for those few seconds. If everything goes through Home Assistant, that cannot happen.",
  "Parameterkatalog": "Parameter catalogue",
  "Noch kein Katalog eingelesen.": "No catalogue read yet.",
  "Der Katalog kommt aus BSB-LAN und enthält genau die Parameter, die deine Regelung kennt – also das, was in der angepassten Parameterliste steckt. Neu einlesen musst du ihn nur, wenn du die Firmware mit einer neuen Liste geflasht hast. Es dauert ein bis zwei Minuten, weil jede Kategorie einzeln über den Bus geht.":
    "The catalogue comes from BSB-LAN and holds exactly the parameters your controller knows – that is, what sits in the adapted parameter list. You only need to read it again after flashing firmware with a new list. It takes a minute or two, because every category goes over the bus on its own.",
  "Katalog neu einlesen": "Read the catalogue again",
  "wird eingelesen …": "reading …",
  "Übernahme aufheben": "Release control",
  "Die Einstellung wieder selbst in die Hand nehmen": "Take the setting back into your own hands",

  // ── Meldungen des Backends ──
  "Noch nichts ausgewählt": "Nothing selected yet",
  "Noch keine Adresse für BSB-LAN eingetragen. Sie steht unter „Einstellungen“.":
    "No address for BSB-LAN entered yet. It lives under “Settings”.",
  "BSB-LAN antwortet nicht. Läuft das Gerät, und stimmt die Adresse?":
    "BSB-LAN is not answering. Is the device running, and is the address right?",
  "BSB-LAN antwortet, aber nicht mit JSON. Meist steckt ein falscher Passkey dahinter.":
    "BSB-LAN answers, but not with JSON. Usually a wrong passkey is behind that.",
  "BSB-LAN antwortet beim Schreiben nicht mit JSON":
    "BSB-LAN does not answer with JSON when writing",
  "Das Stellen ist in den Einstellungen des Heizungsanlagenmanagers noch nicht freigegeben":
    "Writing has not been released in the Heating System Manager's settings yet",
  "Parameter und Wert werden beide gebraucht": "Both parameter and value are needed",
  "Dieses BSB-LAN kennt keine Log-Parameterliste":
    "This BSB-LAN has no log parameter list",
  "Home Assistant hat keinen MQTT-Broker – ohne den kann BSB-LAN nirgendwohin melden":
    "Home Assistant has no MQTT broker – without one BSB-LAN has nowhere to publish",
  "Ohne Adresse von BSB-LAN geht nichts": "Nothing works without BSB-LAN's address",
  "Das Abfrageintervall muss eine Zahl sein": "The polling interval has to be a number",
  "Das BSB-LAN-Logintervall muss eine Zahl sein":
    "The BSB-LAN log interval has to be a number",
  "Unbekannte Einheiten-Einstellung für BSB-LAN": "Unknown unit setting for BSB-LAN",
  "Unbekannte MQTT-Art für BSB-LAN": "Unknown MQTT flavour for BSB-LAN",
  "„melder“ kennt nur „addon“ und „bsblan“.":
    "“melder” only knows “addon” and “bsblan”.",
  "„versteckte_kategorien“ muss eine Liste sein.":
    "“versteckte_kategorien” has to be a list.",
  "Auffrischen fehlgeschlagen": "Refresh failed",
  "Mit automatischer Anmeldung in Home Assistant.":
    "With automatic registration in Home Assistant.",
  "In Home Assistant kommt gerade nichts an, denn der Manager hält sich zurück. Ein Klick auf „Speichern“ schaltet das Senden dort ein.":
    "Nothing is arriving in Home Assistant right now, because the manager is holding back. A click on “Save” switches publishing on over there.",
  "BSB-LAN meldet nichts – obwohl es soll.":
    "BSB-LAN publishes nothing – although it should.",
  "BSB-LAN meldet nichts von sich aus.": "BSB-LAN publishes nothing on its own.",
  "Abstellen lässt sich das hier: „BSB-LAN meldet“ wählen und speichern.":
    "You can stop that here: choose “BSB-LAN publishes” and save.",
  "Was im Menü stehen soll.": "What the menu should show.",
  "Abgehakte Kategorien verschwinden aus der Auswahl – gelöscht wird nichts, ein Klick holt sie zurück.":
    "Unticked categories disappear from the menu – nothing is deleted, one click brings them back.",
  "Noch kein Katalog.": "No catalogue yet.",
  "Lies ihn unter „Einstellungen“ einmal ein – danach steht hier die Gliederung deiner Regelung.":
    " Read it once under “Settings” – after that the structure of your controller appears here.",
  "Lies ihn unter „Einstellungen“ einmal ein – danach steht hier die Liste deiner Regelung.":
    " Read it once under “Settings” – after that the list of your controller appears here.",
  "Keine Schaltzeiten gefunden.": "No switching times found.",
  "Deine Regelung führt keine Parameter vom Typ TIMEPROG – dann gibt es hier nichts einzustellen.":
    "Your controller holds no parameters of type TIMEPROG – so there is nothing to set here.",
  "Keine Verbindung zu BSB-LAN.": "No connection to BSB-LAN.",
  "Adresse prüfen unter „Einstellungen“.": "Check the address under “Settings”.",
  "Deine Regelung führt keine Parameter vom Typ TIMEPROG – dann gibt es hier nichts einzustellen.":
    " Your controller holds no parameters of type TIMEPROG – so there is nothing to set here.",
  "Einstellungen von BSB-LAN nicht lesbar.": "BSB-LAN settings not readable.",
  "Sobald der Parameterkatalog eingelesen ist, sucht der Manager hier die üblichen Messwerte deiner Anlage zusammen.":
    "Once the parameter catalogue has been read, the manager collects the usual readings of your system here.",
  "Verbunden – aber es ist noch nichts ausgewählt. Unter Auswahl bestimmst du, welche Werte nach Home Assistant gehen.":
    "Connected – but nothing is selected yet. Under Selection you decide which values go to Home Assistant.",
  "Die Auswahl durch BSB-LANs Liste ersetzen?": "Replace the selection with BSB-LAN's list?",
  "Das geht unmittelbar an die Heizung.": "This goes straight to the heating system.",
  },

  // Was die Regelung selbst sagt – Kategorien, Parameternamen, Auswahlwerte –
  // steht hier nicht und bleibt, wie das Gerät es führt. Vier von 27
  // Kategorien zu übersetzen ergäbe eine Scheinordnung, während die übrigen
  // 238 Namen deutsch blieben; und wer BSB-LAN auf Englisch stellt, bekommt
  // sie von dort ohnehin englisch.
  muster: [
  // ── Zahlen in Meldungen ──
  [/^(\d+) Parameter gespeichert$/, "$1 parameters saved"],
  [/^(\d+) Parameter übernommen$/, "$1 parameters taken over"],
  [/^(\d+) ausgewählt$/, "$1 selected"],
  [/^([\d.]+) Abfragen je Minute · rund (\d+) % Buszeit$/,
   "$1 queries per minute · roughly $2 % bus time"],
  [/^BSB-LAN ([\d.]+)$/, "BSB-LAN $1"],
  [/^([\d.]+) verfügbar$/, "$1 available"],
  [/^(\d+) Parameter$/, "$1 parameters"],
  [/^(\d+) Parameter · (\d+) ausgewählt$/, "$1 parameters · $2 selected"],
  [/^(\d+) Eintrag\(e\) entfernt$/, "$1 entr(ies) removed"],
  [/^(\d+) Tag\(e\) gespeichert$/, "$1 day(s) saved"],
  [/^(\d+) Tag\(e\) gespeichert, dann: (.+)$/, "$1 day(s) saved, then: $2"],
  [/^(\d+) Einstellung\(en\) geschrieben$/, "$1 setting(s) written"],
  [/^Gespeichert – (\d+) Einstellung\(en\) in BSB-LAN geändert$/,
   "Saved – $1 setting(s) changed in BSB-LAN"],
  [/^Gespeichert – (\d+) Einstellung\(en\) in BSB-LAN geändert, nicht übernommen: (.+)$/,
   "Saved – $1 setting(s) changed in BSB-LAN, not accepted: $2"],
  [/^Gespeichert, aber BSB-LAN nicht erreicht: (.+)$/,
   "Saved, but BSB-LAN could not be reached: $1"],
  [/^(\d+) Einstellung\(en\) geschrieben – nicht übernommen: (.+)$/,
   "$1 setting(s) written – not accepted: $2"],
  [/^(\d+) geänderten? Tage?n? speichern$/, "Save $1 changed day(s)"],
  [/^BSB-LAN meldet jetzt (\d+) Parameter$/, "BSB-LAN now publishes $1 parameters"],
  [/^BSB-LAN führt (\d+) Parameter – es hat die Liste gekürzt$/,
   "BSB-LAN holds $1 parameters – it truncated the list"],
  [/^Parameter (\S+) gestellt$/, "Parameter $1 set"],
  [/^Auf „(.+)“ gestellt$/, "Set to “$1”"],
  [/^geführt vom (.+)$/, "controlled by $1"],
  [/^Auffrischen fehlgeschlagen: (.+)$/, "Refresh failed: $1"],
  [/^Unverständliche Antwort \((\d+)\)\.$/, "Unintelligible answer ($1)."],

  // ── Alter der gemerkten Werte ──
  [/^gerade eben gelesen$/, "read just now"],
  [/^vor einer Minute gelesen$/, "read a minute ago"],
  [/^vor (\d+) Minuten gelesen$/, "read $1 minutes ago"],
  [/^vor einer Stunde gelesen$/, "read an hour ago"],
  [/^vor (\d+) Stunden gelesen$/, "read $1 hours ago"],
  [/^(.+) · wird aufgefrischt …$/, "$1 · refreshing …"],
  [/^(.+) · Auffrischen fehlgeschlagen$/, "$1 · refresh failed"],
  [/^(\d+) Parameter · zuletzt gelesen: (.+)$/, "$1 parameters · last read: $2"],
  [/^(\d+) Parameter, gelesen (.+)$/, "$1 parameters, read at $2"],
  [/^Zuletzt gelesen: (.+)$/, "Last read: $1"],

  // ── Kataloge und Kategorien ──
  [/^(\d+) Parameter, eingelesen am (.+)$/, "$1 parameters, read on $2"],
  [/^(\d+) von (\d+) Kategorien$/, "$1 of $2 categories"],
  [/^, gruppiert nach dem, was sie tun\.$/, ", grouped by what they do."],
  [/^in (\d+) Bereichen\.$/, " in $1 areas. "],
  [/^(\d+) ausgeblendet – über „Anpassen“ zurückholen\.$/,
   "$1 hidden – bring them back via “Customise”."],
  [/^(\d+) von (\d+) – (.+)$/, "$1 of $2 – $3"],
  [/^wieder einblenden$/, "show again"],
  [/^ausblenden$/, "hide"],

  // ── Werte, die keine sind ──
  [/^Regelung meldet Fehler (\d+)$/, "Controller reports error $1"],
  [/^Parameter (\S+) – nicht ausgewählt$/, "Parameter $1 – not selected"],
  [/^Parameter (\S+)$/, "Parameter $1"],

  // ── Betriebsart und Programme ──
  [/^Danach gilt „(.+)“ für die Heizung\.$/, "“$1” will then apply to the heating."],
  [/^Danach gilt Zeitprogramm (\d+)\.$/, "Time programme $1 will then apply."],
  [/^Danach gilt kein Zeitprogramm, sondern durchgehend „(.+)“\.$/,
   "No time programme will apply then, but “$1” continuously."],
  [/^Betriebsart – Parameter (\S+) In der Parameterliste geführt als „(.+)“\.$/,
   "Operating mode – parameter $1\nListed in the parameter list as “$2”."],
  [/^Warmwasser-Betrieb – Parameter (\S+) In der Parameterliste geführt als „(.+)“\.$/,
   "Hot water mode – parameter $1\nListed in the parameter list as “$2”."],
  [/^Betriebsart – Parameter (\S+)$/, "Operating mode – parameter $1"],
  [/^Warmwasser-Betrieb – Parameter (\S+)$/, "Hot water mode – parameter $1"],
  [/^Das Stellen ist nicht freigegeben (.+)$/, "Writing is not released\n$1"],
  [/^(.+) – Parameter (\S+)$/, "$1 – parameter $2"],

  // ── Die Lagemeldung: wer meldet gerade was ──
  [/^BSB-LAN meldet: (\d+) Parameter alle (\S+) Sekunden an (.+) unter (.+)$/,
   "BSB-LAN publishes: $1 parameters every $2 seconds to $3 under $4"],
  [/^BSB-LAN meldet selbst: (\d+) Parameter alle (\S+) Sekunden an (.+) unter (.+)$/,
   "BSB-LAN publishes on its own: $1 parameters every $2 seconds to $3 under $4"],
  [/^Die (\d+) Entitäten? in Home Assistant kommen allein aus diesem Add-on\.$/,
   "The $1 entities in Home Assistant come from this add-on alone."],
  [/^Dieses Add-on meldet zusätzlich (\d+) Parameter\. Beide fragen denselben Bus ab; in Home Assistant stehen die Werte doppelt\.$/,
   "This add-on publishes another $1 parameters. Both poll the same bus; in Home Assistant the values appear twice."],
  [/^Die Auswahl hier führt (\d+) Parameter – mit „Auswahl an BSB-LAN geben“ gleichst du das an\.$/,
   "The selection here holds $1 parameters – “Hand the selection to BSB-LAN” aligns them."],
  [/^(\d+) ausgewählter? Parameter steht nicht im Katalog$/,
   "$1 selected parameter is not in the catalogue"],
  [/^(\d+) ausgewählte Parameter stehen nicht im Katalog$/,
   "$1 selected parameters are not in the catalogue"],

  [/^Deine Regelung kennt (\d+) Parameter\.$/, "Your controller knows $1 parameters."],
  [/^Davon gehen (\d+) nach Home Assistant\.$/, " $1 of them go to Home Assistant."],

  // ── Rückfragen vor dem Schreiben ──
  [/^Betriebsart auf „(.+)“ stellen\?$/, "Set the operating mode to “$1”?"],
  [/^Warmwasser-Betrieb auf „(.+)“ stellen\?$/, "Set the hot water mode to “$1”?"],
  [/^Parameter (\S+) „(.+)“ auf (.+) stellen\?$/, "Set parameter $1 “$2” to $3?"],
  [/^(\d+) Tag\(e\) an die Heizung schicken\?$/, "Send $1 day(s) to the heating system?"],
  [/^Die Übernahme durch (.+) aufheben\?$/, "Release control held by $1?"],
  [/^Danach stellst du diese Parameter hier wieder selbst – (.+) wird sie nicht mehr nachführen\.$/,
   "You will then set these parameters here yourself again – $1 will no longer track them."],
  [/^Die Auswahl durch BSB-LANs Liste ersetzen\?$/,
   "Replace the selection with BSB-LAN's list?"],
  [/^Das geht unmittelbar an die Heizung\.$/, "This goes straight to the heating system."],
  [/^Die Kategorie „(.+)“ ausblenden\?$/, "Hide the category “$1”?"],

  // ── Meldungen des Backends mit Werten darin ──
  [/^Parameter (\S+) lässt sich nicht stellen – die Regelung führt ihn als nur lesbar\.$/,
   "Parameter $1 cannot be set – the controller lists it as read-only."],
  [/^Die Regelung hat den Wert nicht übernommen\. Liegt er innerhalb der erlaubten Grenzen\?(.*)$/,
   "The controller did not accept the value. Is it within the permitted limits?$1"],
  [/^ BSB-LAN meldet zudem „nur lesen“; prüf dort unter Einstellungen den „Schreibzugriff \(Ebene\)“\.$/,
   " BSB-LAN also reports “read only”; check “write access (level)” in its settings."],
  [/^BSB-LAN nicht erreichbar: (.+)$/, "BSB-LAN unreachable: $1"],
  [/^Schreiben fehlgeschlagen: (.+)$/, "Writing failed: $1"],
  [/^BSB-LAN-Einstellungen nicht lesbar: (.+)$/, "BSB-LAN settings not readable: $1"],
  [/^Einstellungen nicht schreibbar: (.+)$/, "Settings not writable: $1"],
  [/^Parameter (\S+) „(.+)“ ist laut Regelung nur lesbar$/,
   "Parameter $1 “$2” is read-only according to the controller"],
  [/^Parameter (\S+) wird vom (.+) geführt\. Zum selbst Stellen die Übernahme aufheben\.$/,
   "Parameter $1 is controlled by $2. Release control to set it yourself."],
  [/^Das Abfrageintervall muss zwischen (\d+) und (\d+) Sekunden liegen$/,
   "The polling interval has to be between $1 and $2 seconds"],
  [/^Das BSB-LAN-Logintervall muss zwischen (\d+) und (\d+) Sekunden liegen$/,
   "The BSB-LAN log interval has to be between $1 and $2 seconds"],
  ],
};
