# Änderungen

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
