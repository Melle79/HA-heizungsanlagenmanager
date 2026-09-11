"""Der Parameterkatalog: einmal holen, dann nachschlagen.

Welche Parameter eine Regelung kennt, hängt am Gerät – und bei Weishaupt und
Siemens sogar an der Gerätefamilie. Genau deshalb gibt es die Liste, die
Frederik aus den Rohdaten der Anlage baut: Sie steckt als ``custom_defs`` in
der BSB-LAN-Firmware und macht aus „Parameter 72“ eine
„Gerätebetriebsstunden“.

Dieses Modul liest sie dort ab, wo sie schon aufbereitet ist – über die
JSON-Schnittstelle von BSB-LAN selbst. Das ist robuster, als die ``.h``-Datei
zu zerlegen: Was BSB-LAN ausliefert, ist per Definition das, was auch
tatsächlich geflasht ist.

Der Katalog wird gespeichert, weil sein Aufbau den Bus mehrere Minuten
beschäftigt – 27 Kategorien, jede eine eigene Abfrage.
"""
from __future__ import annotations

import logging
import time

import bsb as bsb_modul
import store

_LOGGER = logging.getLogger(__name__)

# Pause zwischen zwei Kategorien. Der Katalogaufbau ist das Unhöflichste, was
# der Manager je mit dem Bus anstellt; er soll es wenigstens langsam tun.
PAUSE_S = 0.5


def aufbauen(client: "bsb_modul.Bsb", fortschritt=None) -> dict:
    """Alle Kategorien durchgehen und einen flachen Katalog bauen.

    Ergebnis::

        {"kategorien": {"5": {"name": "Einstellwerte", "parameter": ["50", …]}},
         "parameter":  {"50": {"name": …, "unit": …, "readwrite": 0, …}},
         "gebaut_am": "2026-09-11T…", "geraete": [...]}
    """
    info = client.info()
    kategorien = client.kategorien()
    katalog = {"kategorien": {}, "parameter": {},
               "gebaut_am": time.strftime("%Y-%m-%dT%H:%M:%S"),
               "geraete": info.get("busdevices") or [],
               "bus": info.get("bus"), "version": info.get("version")}

    gesamt = len(kategorien)
    for i, (kid, kopf) in enumerate(sorted(kategorien.items(),
                                           key=lambda x: float(x[0]))):
        name = (kopf or {}).get("name") or f"Kategorie {kid}"
        if fortschritt:
            fortschritt(i + 1, gesamt, name)
        try:
            eintraege = client.kategorie(kid)
        except bsb_modul.BsbFehler as err:
            _LOGGER.warning("Kategorie %s (%s) übersprungen: %s", kid, name, err)
            eintraege = {}

        nummern = []
        for nr, eintrag in (eintraege or {}).items():
            if not isinstance(eintrag, dict):
                continue
            nummern.append(nr)
            katalog["parameter"][nr] = {
                "nr": nr,
                "name": eintrag.get("name") or f"Parameter {nr}",
                "kategorie": kid,
                "kategorie_name": name,
                "unit": eintrag.get("unit") or "",
                "dataType_name": eintrag.get("dataType_name") or "",
                # readwrite: 0 heißt bei BSB-LAN les- und schreibbar,
                # 1 heißt nur lesbar. Das ist verdreht zur Erwartung, deshalb
                # steht hier zusätzlich ein sprechendes Feld.
                "readwrite": eintrag.get("readwrite"),
                "schreibbar": eintrag.get("readwrite") == 0,
                "precision": eintrag.get("precision"),
                "isswitch": eintrag.get("isswitch"),
                "possibleValues": eintrag.get("possibleValues") or [],
            }
            katalog["parameter"][nr].update(store.vorschlag(
                katalog["parameter"][nr]))

        katalog["kategorien"][kid] = {"name": name, "parameter": nummern}
        if i + 1 < gesamt:
            time.sleep(PAUSE_S)

    _LOGGER.info("Katalog gebaut: %d Kategorien, %d Parameter",
                 len(katalog["kategorien"]), len(katalog["parameter"]))
    return katalog


def suchen(katalog: dict, text: str = "", nur_schreibbar: bool = False,
           kategorie: str = "") -> list:
    """Parameter suchen – nach Name, Nummer oder Kategorie."""
    text = (text or "").strip().lower()
    raus = []
    for eintrag in (katalog.get("parameter") or {}).values():
        if kategorie and str(eintrag.get("kategorie")) != str(kategorie):
            continue
        if nur_schreibbar and not eintrag.get("schreibbar"):
            continue
        if text:
            heuhaufen = f"{eintrag.get('nr')} {eintrag.get('name')} " \
                        f"{eintrag.get('kategorie_name')}".lower()
            if text not in heuhaufen:
                continue
        raus.append(eintrag)
    raus.sort(key=lambda e: float(e["nr"]) if _zahl(e["nr"]) else 1e9)
    return raus


def _zahl(text) -> bool:
    try:
        float(text)
        return True
    except (TypeError, ValueError):
        return False
