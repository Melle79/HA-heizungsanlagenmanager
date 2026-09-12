# Bildquellen

`icon.svg` und `logo.svg` sind die Quellen für `icon.png` (256×256) und
`logo.png` (560×200) im Add-on-Verzeichnis. Neu erzeugen mit einem Browser im
Kopflos-Betrieb:

```sh
chrome --headless=new --hide-scrollbars --default-background-color=00000000 \
       --window-size=256,256 --screenshot=icon.png  doku/icon.svg
chrome --headless=new --hide-scrollbars \
       --window-size=560,200 --screenshot=logo.png  doku/logo.svg
```

Das Motiv: ein Kessel mit Betriebsleuchte, Anzeige und Schauglas, dahinter die
Flamme – die beiden Dinge, um die es geht. Der Kasten bleibt schlicht, weil das
Icon in der Seitenleiste bei **32 px** ankommt; jedes zusätzliche Detail wird
dort zu Grau. Wer etwas ändert, soll es bei dieser Größe gegenprüfen:

```sh
sips --resampleWidth 32 icon.png --out /tmp/probe.png
```

**Eine Falle beim Nachbauen:** Die Verläufe der Flamme stehen in festen
Koordinaten (`gradientUnits="userSpaceOnUse"`) und nicht in der Bounding-Box
des Pfades. Das ist Absicht – in der Bounding-Box verzerrt sich der Verlauf
mit jeder Formänderung, und aus dem Farbverlauf von Gelb nach Rot wird ein
Streifen. Dafür muss beim Einbetten ins Logo die **ganze Gruppe** skaliert
werden, nicht der einzelne Pfad.

Die Schrift im Logo ist *Avenir Next* (Rückfall: Nunito, System). Sie steckt
nicht in der SVG-Datei; wer das Logo auf einem Rechner ohne diese Schrift neu
erzeugt, bekommt ein anderes Schriftbild.

## bilder/

Die Bildschirmfotos für README und Handbuch. Sie entstehen aus der echten
Oberfläche, nicht aus einem Entwurf – mit einem gefälschten Backend, damit
keine fremde Anlage darauf zu sehen ist.
