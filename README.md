# Kesselmanager / Boiler Manager

Ein Home-Assistant-Add-on, das eine Heizungsregelung über
[BSB-LAN](https://github.com/fredlcore/BSB-LAN) lesbar und stellbar macht.

*A Home Assistant add-on that makes a heating controller readable and
adjustable through BSB-LAN.*

## Installation

1. In Home Assistant unter **Einstellungen → Add-ons → Add-on-Store** über das
   Dreipunktmenü **Repositories** hinzufügen:
   `https://github.com/Melle79/HA-kesselmanager`
2. *Kesselmanager* installieren und starten.
3. Unter **Einstellungen** die Adresse von BSB-LAN eintragen und den
   **Parameterkatalog einlesen**.
4. Unter **Auswahl** anhaken, was nach Home Assistant soll.

Alles Weitere steht in der [Dokumentation](kesselmanager/DOCS.de.md)
([English](kesselmanager/DOCS.md)).

## Was es kann

* Parameterkatalog direkt aus BSB-LAN – also genau die Liste, die zur eigenen
  Anlage geflasht ist
* Auswahl per Häkchen, mit Suche und Kategoriefilter
* Automatische Geräteklassen; Betriebsstunden und Zählerstände bekommen
  `total_increasing` und damit eine Langzeitstatistik
* Sollwerte stellen – hinter zwei Schaltern, beide ab Werk aus
* Schonender Umgang mit dem Bus: Bündel statt Einzelabfragen, Pausen dazwischen

## Lizenz

MIT
