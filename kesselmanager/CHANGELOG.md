# Änderungen

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
