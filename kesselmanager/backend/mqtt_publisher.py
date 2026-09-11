"""Die ausgewählten Parameter als Entitäten in Home Assistant.

Jeder Parameter, den jemand in der Oberfläche anhakt, wird hier zu einem
Sensor – mit Einheit, Geräteklasse und, wo es passt, mit
``state_class: total_increasing``. Das Letzte ist das Wichtigste: Daraus baut
Home Assistant von selbst eine Langzeitstatistik, und eine angebundene
Zeitreihendatenbank bekommt den Verlauf ohne weiteres Zutun.

Abgewählte Parameter verschwinden wieder. Die Discovery-Nachricht ist
„retained“, überlebt also das Add-on – ohne aktives Abräumen bliebe für jeden
je angehakten Parameter eine Karteileiche in Home Assistant stehen.
"""
from __future__ import annotations

import json
import logging
import re
import threading

import paho.mqtt.client as mqtt

_LOGGER = logging.getLogger(__name__)

DISCOVERY_PREFIX = "homeassistant"
DEVICE_ID = "kesselmanager"


def _slug(text: str) -> str:
    text = (text or "").lower()
    for von, nach in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")):
        text = text.replace(von, nach)
    text = re.sub(r"[^a-z0-9]+", "_", text).strip("_")
    return text or "wert"


class Publisher:
    def __init__(self, host, port, user, password, praefix="kesselmanager"):
        self.praefix = praefix
        self.basis = praefix
        self.verfuegbarkeit = f"{praefix}/availability"
        self.connected = threading.Event()
        self._client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,
                                   client_id=f"{DEVICE_ID}-addon")
        if user:
            self._client.username_pw_set(user, password)
        self._client.will_set(self.verfuegbarkeit, "offline", retain=True)
        self._client.on_connect = self._verbunden
        self._host, self._port = host, int(port or 1883)
        self.on_ready = None

    # ----------------------------------------------------------- Technik ----

    def start(self) -> None:
        self._client.connect_async(self._host, self._port, keepalive=60)
        self._client.loop_start()

    def _verbunden(self, client, userdata, flags, reason_code, properties=None):
        if reason_code != 0:
            _LOGGER.error("MQTT-Verbindung abgelehnt: %s", reason_code)
            return
        self.connected.set()
        client.publish(self.verfuegbarkeit, "online", retain=True)
        _LOGGER.info("Mit MQTT-Broker verbunden")
        if self.on_ready:
            self.on_ready()

    def _publish(self, topic: str, payload: str) -> None:
        if self.connected.is_set():
            self._client.publish(topic, payload, retain=True)

    def _geraet(self, info: dict) -> dict:
        # Der Gerätename nennt den Regler, nicht das Add-on: In Home Assistant
        # steht dann "WRS-CPU-B2/E" im Gerätebaum und nicht "Add-on".
        regler = ""
        for eintrag in (info or {}).get("geraete") or []:
            if eintrag.get("dev_id") == 0:
                regler = eintrag.get("dev_name") or ""
        return {
            "identifiers": [DEVICE_ID],
            "name": "Heizungsregler" + (f" {regler}" if regler else ""),
            "manufacturer": "Heizungsanlagenmanager über BSB-LAN",
            "model": regler or "unbekannt",
            "sw_version": (info or {}).get("version") or "",
        }

    # -------------------------------------------------------- Entitäten ----

    def schluessel(self, eintrag: dict) -> str:
        """Der Themenname einer Entität – stabil über Umbenennungen hinweg.

        Er hängt an der **Parameternummer**, nicht am Namen: Wer die Anzeige
        umbenennt, soll keine zweite Entität bekommen und die Historie der
        ersten verlieren.
        """
        return f"p{_slug(str(eintrag.get('nr')))}"

    def discovery(self, auswahl: list, info: dict, vorher: list) -> list:
        """Anmelden, was ausgewählt ist – und abmelden, was fortgefallen ist."""
        geraet = self._geraet(info)
        aktuell = []
        for eintrag in auswahl:
            key = self.schluessel(eintrag)
            aktuell.append(key)
            nutzlast = {
                "name": eintrag.get("anzeige") or eintrag.get("name") or key,
                "unique_id": f"{DEVICE_ID}_{key}",
                "default_entity_id": f"sensor.{DEVICE_ID}_{key}",
                "state_topic": f"{self.basis}/{key}/state",
                "json_attributes_topic": f"{self.basis}/{key}/attributes",
                "availability_topic": self.verfuegbarkeit,
                "device": geraet,
            }
            if eintrag.get("einheit"):
                nutzlast["unit_of_measurement"] = eintrag["einheit"]
            if eintrag.get("device_class"):
                nutzlast["device_class"] = eintrag["device_class"]
            if eintrag.get("state_class"):
                nutzlast["state_class"] = eintrag["state_class"]
            self._publish(f"{DISCOVERY_PREFIX}/sensor/{DEVICE_ID}/{key}/config",
                          json.dumps(nutzlast))

        for alt in [k for k in (vorher or []) if k not in aktuell]:
            self._publish(f"{DISCOVERY_PREFIX}/sensor/{DEVICE_ID}/{alt}/config", "")
            self._publish(f"{self.basis}/{alt}/state", "")
            self._publish(f"{self.basis}/{alt}/attributes", "")
            _LOGGER.info("Entität %s abgemeldet", alt)
        return aktuell

    def werte(self, auswahl: list, werte: dict) -> None:
        """Die gelesenen Werte melden."""
        for eintrag in auswahl:
            key = self.schluessel(eintrag)
            gelesen = (werte or {}).get(str(eintrag.get("nr"))) or {}
            wert = gelesen.get("value")
            # Kein Wert heißt "None" – daraus wird in Home Assistant der
            # Zustand "unbekannt". Das Wort "unknown" wäre für einen Sensor
            # mit Geräteklasse keine gültige Zahl und ließe die Entität auf
            # "unavailable" fallen.
            zustand = "None" if wert in (None, "") else str(wert)
            self._publish(f"{self.basis}/{key}/state", zustand)
            self._publish(f"{self.basis}/{key}/attributes", json.dumps({
                "parameter": eintrag.get("nr"),
                "beschreibung": gelesen.get("desc") or "",
                "kategorie": eintrag.get("kategorie_name") or "",
                "fehler": gelesen.get("error"),
                "gelesen_am": gelesen.get("zeit"),
            }))
