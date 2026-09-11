"""Der Draht zu BSB-LAN – lesen, schreiben, und wissen, wann man es nicht darf.

BSB-LAN ist ein kleiner ESP32 am Bus der Heizungsregelung. Er spricht HTTP und
liefert JSON; dieses Modul kapselt die vier Aufrufe, die der Heizungsanlagenmanager
braucht, und sonst nichts.

Zwei Dinge stehen über allem:

* **Der Bus ist langsam.** Jede Abfrage ist ein Telegramm auf einem Zweidraht-
  Bus mit 4800 Baud, und die Regelung antwortet in ihrem eigenen Takt. Wer 200
  Parameter im Sekundentakt abfragt, legt den Bus lahm. Deshalb fragt der
  Manager in Häppchen und mit Pausen.
* **Schreiben ist etwas anderes als Lesen.** Ein falscher Sollwert lässt im
  Winter eine Wohnung auskühlen. Die Bremse dafür sitzt im Add-on, nicht hier:
  Ohne ``schreiben_erlaubt`` kommt dieses Modul gar nicht erst zum Zuge.

  Was hier bewusst **nicht** geprüft wird, ist ``buswritable`` aus ``/JI``.
  Diese Zahl und die Sperre, die beim Schreiben wirklich greift, stammen in
  BSB-LAN aus zwei verschiedenen Rechnungen und können sich widersprechen –
  eine willige Anlage meldet dort durchaus eine Null. Wer darauf ein Verbot
  baut, sperrt den Benutzer aus seiner eigenen Heizung aus.
"""
from __future__ import annotations

import json
import logging
import re
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
        if not self.basis:
            # Beim ersten Start steht hier nichts. Das ist kein Fehler der
            # Technik, sondern eine offene Frage an den Benutzer – und die
            # verdient einen Satz, der sie beantwortet.
            raise BsbFehler("Noch keine Adresse für BSB-LAN eingetragen. "
                            "Sie steht unter „Einstellungen“.")
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

    # ------------------------------------------ BSB-LANs eigene Einstellungen ----

    def konfiguration(self) -> dict:
        """Die Einstellungen von BSB-LAN selbst – Logging, MQTT, alles.

        ``/JL`` liefert sie als JSON, ``/JW`` nimmt dieselbe Struktur zum
        Schreiben zurück. Das ist der Weg, dem Adapter zu sagen, was er von
        sich aus melden soll, statt dieselben Werte ein zweites Mal über den
        Bus zu holen.

        **BSB-LAN 5.1.18 liefert hier kaputtes JSON**: Ein leerer Wert bleibt
        unbeendet (``"value": "`` und dann gleich die schließende Klammer) –
        zu sehen bei den One-Wire- und DHT-Pins, wenn keine gesetzt sind. Das
        wird hier geflickt, weil sonst die ganze Auskunft verlorengeht. Der
        Fehler steckt im Gerät, nicht in der Antwort.
        """
        url = self._pfad("JL")
        try:
            antwort = requests.get(url, timeout=self.zeitlimit)
            antwort.raise_for_status()
            roh = antwort.text
        except requests.RequestException as err:
            raise BsbFehler(f"BSB-LAN-Einstellungen nicht lesbar: {err}") from err
        geflickt = re.sub(r'"value":\s*"\s*\n(\s*\})', r'"value": ""\n\1', roh)
        try:
            daten = json.loads(geflickt)
        except ValueError as err:
            raise BsbFehler(
                "BSB-LAN antwortet auf die Einstellungen nicht mit gültigem "
                "JSON.") from err
        return daten if isinstance(daten, dict) else {}

    def konfiguration_schreiben(self, eintraege: dict) -> dict:
        """Einstellungen zurückschreiben.

        Der Aufrufer übergibt genau die Einträge, die er ändern will. Alles
        andere bleibt, wie es ist – in dieser Datei stehen auch Zugangsdaten,
        die niemanden hier angehen.

        **Nur ``parameter`` und ``value`` gehen raus.** Das klingt nach einer
        Kleinigkeit und ist der Unterschied zwischen Wirkung und Nichts: Gibt
        man BSB-LAN den vollständigen Eintrag zurück, wie ``/JL`` ihn liefert –
        mit ``type``, ``format``, ``category`` und ``name`` –, antwortet es mit
        einer leeren Struktur und ändert nichts. Kein Fehler, keine Meldung,
        nur ein stilles Nein. Am Anfang stand hier genau das, und das Add-on
        behauptete, geschrieben zu haben.
        """
        knapp = {}
        for schluessel, eintrag in (eintraege or {}).items():
            if not isinstance(eintrag, dict):
                continue
            knapp[str(schluessel)] = {"parameter": eintrag.get("parameter"),
                                      "value": eintrag.get("value")}
        url = self._pfad("JW")
        try:
            antwort = requests.post(url, json=knapp, timeout=self.zeitlimit)
            antwort.raise_for_status()
        except requests.RequestException as err:
            raise BsbFehler(f"Einstellungen nicht schreibbar: {err}") from err
        try:
            return antwort.json()
        except ValueError:
            return {}

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

        **Kein Vorab-Urteil über ``buswritable``.** Das war einmal anders und
        war falsch: Die Zahl aus ``/JI`` und die Sperre, die beim Schreiben
        wirklich greift, kommen in BSB-LAN aus zwei verschiedenen Rechnungen.
        Ist ``DEFAULT_FLAG`` auf ``FL_RONLY`` gesetzt, meldet ``/JI`` eine
        Null, während die eigentliche Prüfung jeden Parameter durchlässt, der
        nicht selbst als nur-lesbar markiert ist. Wer sich auf die Null
        verlässt, sperrt eine Anlage aus, die willig wäre.

        Also: fragen, nicht raten. Die Antwort auf den Schreibversuch ist die
        Auskunft, die zählt – BSB-LAN meldet je Parameter einen Status, und
        eine abgelehnte Änderung wird hier zum Fehler.
        """
        if not self.basis:
            raise BsbFehler("Noch keine Adresse für BSB-LAN eingetragen. "
                            "Sie steht unter „Einstellungen“.")
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

        # BSB-LAN meldet je Parameter einen Status. Die Zahlen stammen aus
        # dem Rückgabewert von set() und sind nicht selbsterklärend:
        #
        #   1  gesetzt – das ist der Erfolg
        #   2  Versuch, einen nur-lesbaren Parameter zu setzen
        #   0  fehlgeschlagen: Parameter unbekannt oder Wert unbrauchbar
        #
        # Die Eins als Erfolg zu lesen ist ungewohnt; wer aus Gewohnheit die
        # Null dafür hält, meldet jede gelungene Änderung als Fehler.
        eintrag = ergebnis.get(str(parameter)) or next(iter(ergebnis.values()), {})
        status = eintrag.get("status") if isinstance(eintrag, dict) else None
        try:
            status = int(status)
        except (TypeError, ValueError):
            status = None

        if status == 2:
            raise BsbFehler(
                f"Parameter {parameter} lässt sich nicht stellen – die Regelung "
                f"führt ihn als nur lesbar.")
        if status == 0:
            hinweis = ""
            if not self.schreibbar():
                # Die Null aus /JI ist hier ein Hinweis, kein Urteil – als
                # Erklärung hinterher, nicht als Verbot vorher.
                hinweis = (" BSB-LAN meldet zudem „nur lesen“; prüf dort unter "
                           "Einstellungen den „Schreibzugriff (Ebene)“.")
            raise BsbFehler(
                f"Die Regelung hat den Wert nicht übernommen. Liegt er "
                f"innerhalb der erlaubten Grenzen?{hinweis}")
        if status is None:
            _LOGGER.warning("Unerwartete Antwort auf das Schreiben: %s", ergebnis)
        return ergebnis
