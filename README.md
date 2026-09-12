# Heating System Manager · Heizungsanlagenmanager

A Home Assistant add-on that makes a heating controller usable through
[BSB-LAN](https://github.com/fredlcore/BSB-LAN) — with the same structure you
find on the boiler's own panel.

[![Add repository to Home Assistant](https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg)](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2FMelle79%2FHA-heizungsanlagenmanager)
[![Buy Me a Coffee](https://img.shields.io/badge/Buy%20Me%20a%20Coffee-melle79-ffdd00?logo=buymeacoffee&logoColor=black)](https://buymeacoffee.com/melle79)

> 📖 Full manual: **[DOCS.md](heizungsanlage/DOCS.md)** ·
> 🇩🇪 Auf Deutsch: **[README.de.md](README.de.md)**

**The interface is German.** The documentation comes in both languages; the
add-on itself does not yet.

![The “Regelung” tab with a time programme](heizungsanlage/doku/bilder/regelung.png)

## What it does

**Operate, not just display.** The categories come from the controller itself,
grouped by what they do — heating, domestic hot water, heat generator,
maintenance. Writable parameters get the matching control. Time programmes
appear as a **weekly table** instead of a string, and above it you see whether
that programme is the one currently running.

**No parameter numbers baked in.** What appears on the overview, which
categories hold switching times, which parameter selects the active
programme — all of it is derived from *your* system's catalogue, from names
and data types. So it runs on any controller BSB-LAN speaks to: BSB, LPB and
PPS.

**Two ways into Home Assistant.** Either the add-on publishes the selected
parameters itself — or it configures BSB-LAN to do it and then stands back.
Broker and credentials come from Home Assistant; you type nothing.

![The “Home Assistant” tab](heizungsanlage/doku/bilder/mqtt.png)

**Careful with the system.** Writing needs two switches — one in BSB-LAN, one
in the add-on, both off by default. The bus is polled in bundles with pauses,
not continuously. And every write is read back: what the device holds
afterwards counts, not what it was sent.

![A category with writable setpoints](heizungsanlage/doku/bilder/regler.png)

## Requirements

* A running [BSB-LAN](https://github.com/fredlcore/BSB-LAN) on the same
  network (developed and tested against 5.1.18)
* An MQTT broker in Home Assistant

## Installation

Add this address as an add-on repository in Home Assistant
(*Settings → Add-ons → Add-on Store → ⋮ → Repositories*):

```
https://github.com/Melle79/HA-heizungsanlagenmanager
```

Then install *Heizungsanlagenmanager via BSB-LAN* and start it. Under
**Einstellungen** enter the address of BSB-LAN and read the **parameter
catalogue** — that takes a minute or two, because every category goes over the
bus on its own. Under **Home Assistant**, tick what should become an entity.

## What BSB-LAN taught us along the way

A few quirks you only find on a live device — written down so the next person
does not have to look for them:

* `/JW` accepts only `parameter` and `value`. Hand back the complete entry as
  `/JL` delivers it and BSB-LAN answers with an empty structure and changes
  nothing — without an error.
* The log parameter list holds **at most 40** entries. Anything beyond that is
  dropped silently.
* Revoking auto-discovery (`/M0!<target>`) only affects what is currently in
  the list. So the order is: revoke, change the list, announce.
* `/JL` returns malformed JSON in 5.1.18 when no One-Wire or DHT pins are set.

## Working on it

The checks run without a boiler and without Home Assistant — BSB-LAN is faked:

```sh
./pruefen.sh
```

On first use the script creates its own Python environment under `.venv/` and
fetches what the Dockerfile provides inside the add-on.

## Thanks

To [Frederik Holst](https://github.com/fredlcore) and everyone who built
BSB-LAN. Without the adapted parameter list for one's own device family,
“parameter 72” would never have become “Gerätebetriebsstunden”.

## Disclaimer

This is a **private hobby project** with no commercial background. Use it at
your own risk – **all liability is excluded** (see also the MIT licence).
There is **no support**; issues and pull requests may go unanswered.

That carries weight here: the add-on writes to a bus that a house's heating
controller hangs on. Writing is therefore **locked by default** and has to be
released deliberately. A wrong setpoint lets a flat go cold in winter – check
every parameter before you write it.

## Licence

MIT
