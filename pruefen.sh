#!/bin/sh
# Die Trockenprüfung starten – und beim ersten Mal die Umgebung dafür bauen.
#
# Der Heizungsanlagenmanager hängt an requests, paho-mqtt und Flask. Die kommen im
# Add-on aus dem Dockerfile; auf dem Rechner, auf dem entwickelt wird, muss
# jemand sie hinstellen. Ein Systempython hat sie erfahrungsgemäß irgendwann
# nicht mehr – darum eine eigene Umgebung neben dem Quelltext, die niemanden
# sonst stört und nicht mit ins Repo wandert.
set -e
cd "$(dirname "$0")"

if [ ! -x .venv/bin/python ]; then
  echo "Lege die Prüfumgebung an (einmalig) …"
  python3 -m venv .venv
  .venv/bin/pip install --quiet --upgrade pip
  .venv/bin/pip install --quiet -r heizungsanlage/backend/requirements.txt
fi

exec .venv/bin/python heizungsanlage/tests/test_kessel.py
