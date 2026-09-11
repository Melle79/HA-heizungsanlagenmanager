"""Der Draht zu BSB-LAN – lesen, schreiben, und wissen, wann man es nicht darf.

BSB-LAN ist ein kleiner ESP32 am Bus der Heizungsregelung. Er spricht HTTP und
liefert JSON; dieses Modul kapselt die vier Aufrufe, die der Kesselmanager
braucht, und sonst nichts.

Zwei Dinge stehen über allem:

* **Der Bus ist langsam.** Jede Abfrage ist ein Telegramm auf einem Zweidraht-
  Bus mit 4800 Baud, und die Regelung antwortet in ihrem eigenen Takt. Wer 200
  Parameter im Sekundentakt abfragt, legt den Bus lahm. Deshalb fragt der
  Manager in Häppchen und mit Pausen.
* **Schreiben ist etwas anderes als Lesen.** Ein falscher Sollwert lässt im
  Winter eine Wohnung auskühlen. BSB-LAN hat dafür einen eigenen Schalter
  (``buswritable``); ist er aus, wird hier gar nicht erst gesendet.
"""
from __future__ import annotations

import logging
import time

import requests

_LOGGER = logging.getLogger(__name__)

# So viele Parameter kommen in eine Abfrage. BSB-LAN verkraftet mehr, aber
# jede Antwort muss auch in den Speicher des ESP32 passen, und eine kurze
# Abfrage blockiert den Bus kürzer.
BUENDEL = 12

# Pause zwischen zwei Bündeln. Sie klingt großzügig und ist es auch – der Bus
# gehört der Heizung, nicht uns.
PAUSE_S = 0.4


class BsbFehler(RuntimeError):
    """Etwas ging schief – verbunden mit einem Satz, den man anzeigen kann."""


class Bsb:
    def __init__(self, basis: str, passkey: str = "", zeitlimit: float = 12.0):
        self.basis = (basis or "").rstrip("/")
        self.passkey = (passkey or "").strip("/")
        self.zeitlimit = zeitlimit

    # ------------------------------------------------------------ intern ----

    def _pfad(self, befehl: str) -> str:
        # Ein gesetzter Passkey wird bei BSB-LAN zum ersten Pfadelement.
        vorn = f"/{self.passkey}" if self.passkey else ""
        return f"{self.basis}{vorn}/{befehl.lstrip('/')}"

    def _holen(self, befehl: str) -> dict:
        url = self._pfad(befehl)
        try:
            antwort = requests.get(url, timeout=self.zeitlimit)
            antwort.raise_for_status()
            return antwort.json()
        except requests.Timeout as err:
            raise BsbFehler(
                "BSB-LAN antwortet nicht. Läuft das Gerät, und stimmt die "
                "Adresse?") from err
        except requests.RequestException as err:
            raise BsbFehler(f"BSB-LAN nicht erreichbar: {err}") from err
        except ValueError as err:
            raise BsbFehler(
                "BSB-LAN antwortet, aber nicht mit JSON. Meist steckt ein "
                "falscher Passkey dahinter.") from err

    # ------------------------------------------------------------- lesen ----

    def info(self) -> dict:
        """Version, Bustyp, Adressen – und wer sonst noch am Bus hängt."""
        return self._holen("JI")

    def kategorien(self) -> dict:
        """{id: {name, min, max}} – die Gliederung, die auch der Regler kennt."""
        return self._holen("JK=ALL")

    def kategorie(self, nummer) -> dict:
        """Alle Parameter einer Kategorie samt Datentyp, Einheit und Schreibrecht."""
        return self._holen(f"JK={nummer}")

    def werte(self, parameter: list) -> dict:
        """Werte abfragen – in Häppchen, mit Pausen, damit der Bus atmen kann."""
        raus: dict = {}
        liste = [str(p) for p in parameter if str(p).strip()]
        for i in range(0, len(liste), BUENDEL):
            teil = liste[i:i + BUENDEL]
            try:
                raus.update(self._holen("JQ=" + ",".join(teil)))
            except BsbFehler as err:
                # Ein Aussetzer in einem Bündel darf nicht die ganze Runde
                # kosten – die übrigen Werte sind ja in Ordnung.
                _LOGGER.warning("Bündel %s fehlgeschlagen: %s", teil, err)
            if i + BUENDEL < len(liste):
                time.sleep(PAUSE_S)
        return raus

    # --------------------------------------------------------- schreiben ----

    def schreibbar(self) -> bool:
        """Erlaubt BSB-LAN gerade das Schreiben auf den Bus?"""
        try:
            return bool(self.info().get("buswritable"))
        except BsbFehler:
            return False

    def setzen(self, parameter, wert, typ: int = 1) -> dict:
        """Einen Parameter stellen.

        ``typ`` 1 ist eine SET-Nachricht – das normale Stellen eines Wertes.
        ``typ`` 0 wäre eine INF-Nachricht, mit der ein Raumgerät seine
        Temperatur verkündet; die braucht hier niemand.

        Vor jedem Schreiben wird ``buswritable`` geprüft. Das kostet eine
        zusätzliche Abfrage und ist es wert: Steht der Schalter in BSB-LAN auf
        "nur lesen", ginge der Befehl sonst ins Leere, und die Oberfläche
        meldete fälschlich einen Erfolg.
        """
        if not self.schreibbar():
            raise BsbFehler(
                "BSB-LAN steht auf „nur lesen“. Der Schreibzugriff lässt sich "
                "in dessen eigener Oberfläche freischalten – erst danach nimmt "
                "die Heizung Änderungen an.")
        url = self._pfad("JS")
        nutzlast = {"Parameter": str(parameter), "Value": str(wert), "Type": str(typ)}
        try:
            antwort = requests.post(url, json=nutzlast, timeout=self.zeitlimit)
            antwort.raise_for_status()
            ergebnis = antwort.json()
        except requests.RequestException as err:
            raise BsbFehler(f"Schreiben fehlgeschlagen: {err}") from err
        except ValueError as err:
            raise BsbFehler("BSB-LAN antwortet beim Schreiben nicht mit JSON") from err

        # BSB-LAN meldet je Parameter einen Status: 0 heißt angenommen.
        eintrag = ergebnis.get(str(parameter)) or next(iter(ergebnis.values()), {})
        if isinstance(eintrag, dict) and eintrag.get("status") not in (0, "0", None):
            raise BsbFehler(
                f"Die Regelung hat den Wert abgelehnt (Status "
                f"{eintrag.get('status')}). Liegt er innerhalb der erlaubten "
                f"Grenzen?")
        return ergebnis
