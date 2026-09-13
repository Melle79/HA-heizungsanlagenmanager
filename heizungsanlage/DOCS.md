# Heating System Manager via BSB-LAN

The Heating System Manager brings a heating controller into Home Assistant – through
[BSB-LAN](https://github.com/fredlcore/BSB-LAN), a small ESP32 sitting on the
controller's bus.

It does three things:

* **Select.** Out of every parameter your controller knows, you tick the ones
  that matter to you. Only those are read and published as entities.
* **Read.** On a configurable cycle, gently on the bus, with a sensible device
  class for Home Assistant.
* **Set.** Change setpoints and operating modes – behind two switches, both off
  by default.

## Language

The interface speaks German and English. Which one appears is decided by Home
Assistant – the add-on asks on load and follows suit.

**German is the source**: the German sentence is also the key the translation
is stored under. A forgotten entry does not break anything; it simply stays
German instead of showing a placeholder.

**What the controller says stays as the controller says it.** Categories,
parameter names and enum values come from your device and read exactly as they
do on the boiler's own panel. Set BSB-LAN itself to English and they arrive in
English.

Another language is one file: copy `frontend/sprachen/<code>.js` from `en.js`,
translate the right-hand side, done.

## Requirements

A running BSB-LAN on the same network and an MQTT broker in Home Assistant.
Both are checked at startup; without the broker the interface still works, you
simply get no entities.

**Which systems?** Every controller BSB-LAN speaks to – BSB, LPB and PPS, that
is the Siemens controllers behind Brötje, Elco, Weishaupt, Atlantic, Baxi and
others. The Heating System Manager knows no parameter number by heart: what appears on
the overview, and which categories hold switching times, is derived from your
own system's catalogue – from the names, and from the data type BSB-LAN
assigns. If nothing matches a tile, the tile is left out rather than showing a
number from someone else's boiler.

What it cannot do is know more than BSB-LAN: if your firmware does not carry a
parameter, it does not exist here either. And whether a value can be set is
decided by the controller itself.

## The parameter catalogue

Which parameters a controller knows depends on the device. With Siemens
controllers – and therefore Weishaupt, Brötje, Elco and many others – it even
differs between device families. That is why there is the **tailored parameter
list** the BSB-LAN developer builds from a system's raw data, which goes into
the firmware as `BSB_LAN_custom_defs.h`.

The Heating System Manager does not parse that file; it reads the list **from BSB-LAN
itself**. That is more robust: what BSB-LAN serves is by definition what is
actually flashed. “Parameter 72” becomes “Operating hours”.

You read the catalogue once, and after that only when you flash the firmware
with a new list. It takes a minute or two, because every category goes over the
bus separately.

## The “Regelung” tab

![Time programme as a weekly table](https://raw.githubusercontent.com/Melle79/HA-heizungsanlagenmanager/main/heizungsanlage/doku/bilder/regelung.png)


Here you operate the system the way you would at the unit on the boiler –
**with the same structure**. The 27 categories are not mine, they come from the
controller itself: *Time*, *Setpoints*, *Holiday*, *Operating mode*, *Heating
circuit*, *Hot water*, *Boiler* and so on. Nobody has to sort anything; the
system knows best what belongs together.

Pick a category and the manager reads its values and shows them. Categories are
small – usually between two and thirty parameters – so it takes seconds.
Writable parameters get a fitting control: a number field for temperatures, a
dropdown for operating modes, a text field otherwise.

The four time programmes have a **tab of their own** – a line of text would be
no way to set them.

## Time programmes

Four programmes – heating circuits 1, 2, 3 and hot water – each with seven days
and **three switching windows per day**. The tab shows them as a table of time
fields: one row per day, three from–to pairs side by side.

An empty window means “not used”. The ✕ at the end of a row clears a whole day.

Two buttons save most of the typing: **copy Monday to Mon–Fri** and **copy
Monday to all days**.

Nothing changes until you save, and even then only the days you touched – they
are highlighted while you edit. A confirmation shows the times in plain text
before writing. If the controller rejects a day, the manager stops at once
instead of writing on blindly.

Technically each day is a string, exactly as BSB-LAN delivers and expects it:

```
06:00-22:00 ##:##-##:## ##:##-##:##
```

Fine to read, impossible to edit – hence the editor.

## Setting: the two switches

A wrong setpoint lets a flat go cold in winter. Setting therefore requires
**two** switches to be on:

1. in **BSB-LAN** itself (there it is called `buswritable`),
2. under *Settings → Write access* in this add-on.

Both are off by default. The *Regelung* tab always shows which of the two is
still missing. On top of that the manager only accepts parameters the
controller itself reports as writable, and asks before every change.

## Selection: what reaches Home Assistant

The list is grouped by the controller's own categories, in the controller's own
order. Each group starts collapsed and states how many parameters it holds and
how many are ticked; a click opens it. Searching or filtering opens the
matching groups for you.

Every ticked parameter becomes a sensor. Unit and device class are suggested
from the data type:

| recognised by | device class | state class |
|---|---|---|
| °C, °F, K | `temperature` | `measurement` |
| bar | `pressure` | `measurement` |
| kW / kWh | `power` / `energy` | `measurement` / `total_increasing` |
| h, min, s | `duration` | `measurement` |
| “operating hours”, “starts”, “consumption” in the name | – | **`total_increasing`** |
| enumerations, date, time | none | none |

That last row about counters matters most: from a value that only grows, Home
Assistant builds **long-term statistics** on its own, with daily, monthly and
yearly figures. Feed a time-series database from Home Assistant and the history
lands there with no further effort.

The entity is tied to the **parameter number**, not the name. Rename the label
and you keep your history.

## The BSB-LAN version

Top right, next to the BSB-LAN and MQTT indicators, stands the flashed version
of the adapter. If a newer one exists, a hint appears beside it linking to the
releases. The comparison uses `bsb-lan.de/bsb-version.h`, the same source
BSB-LAN itself queries, fetched at most once a day.

## Who publishes to Home Assistant?

Two programs can publish the same system, and both do it well – just not at the
same time. Under *Home Assistant* you choose – with the fields belonging to
the chosen path right below it: **the manager publishes** (default,
curated device classes, but nothing arrives while the add-on is stopped), or
**BSB-LAN publishes** – it carries its own MQTT with auto-discovery, polls the
bus anyway, publishes more often and also creates controls.

In the second mode the manager configures the adapter: broker, user and
password come from Home Assistant itself (passed through, never shown or
stored here – and the broker address is translated from the Docker name
`core-mosquitto` into the IP of the machine Home Assistant runs on, because an
ESP32 on the house network cannot resolve the former; if no address can be
found, neither address nor credentials are written), prefix, device id, interval, units and MQTT flavour come from
the fields below the choice, and auto-discovery is switched on. Whichever way
you pick, only the prefix that is actually in effect is on screen – and saving
writes the values straight into the device, because a separate button for that
would leave the new prefix in the add-on while BSB-LAN kept publishing under
the old one. Anything else BSB-LAN does –
logging to SD card, say – is left alone; only differences are written.

### When BSB-LAN answers but publishes nothing

There is a state that looks like “running” from the outside and is not:
BSB-LAN answers every HTTP request but never started its MQTT part. It happens
after a Wi-Fi dropout – the adapter opens an access point of its own and skips
MQTT while the Wi-Fi silently reconnects. The manager therefore listens on
`<prefix>/status`, where BSB-LAN posts its “online”. If that stays “offline”
while the device is reachable, a hint appears with a **Restart adapter**
button. The restart uses `/N` and leaves every setting in the device alone.

### Every parameter at its own rate

BSB-LAN's publish interval applies to all parameters alike, and that is where
the limit of 40 comes from: a bus query takes one to two seconds, so forty
parameters every minute occupy the bus completely. The **Rate** column in the
selection lets each parameter run at its own pace – boiler temperature often,
operating hours once an hour. Left on *base rate*, BSB-LAN's own interval
applies; with a value set, the manager asks for that parameter over MQTT
(`<prefix>/poll`), the same interface one would otherwise drive with Home
Assistant automations. Next to the selection stands what it costs: queries per
minute and the estimated share of bus time.

The selection is pushed into BSB-LAN's log parameter list on save, and *take
over the list from BSB-LAN* does the reverse. Both buttons sit with the
selection itself, and only while BSB-LAN publishes. Every write is read back: BSB-LAN
silently truncates long lists.

## Remembered values

Reading a category over the bus takes a few seconds – 4800 baud, and the
controller answers at its own pace. Tick **"show the last values immediately"**
under *Settings → Display* and the table appears at once, with its age next to
it, while fresh values are fetched in the background.

Off by default on purpose: if you also adjust the system at the boiler's own
panel, you would see the old value for those few seconds. If everything goes
through Home Assistant, that cannot happen.

A number being typed survives the refresh, and in the time programs only
untouched days are refreshed – edits are never overwritten.

## Reading happens on demand

A controller easily knows two hundred parameters, and on a Weishaupt system
over 160 of them are writable. Polling all of them would occupy the bus
permanently, and hardly any are worth watching continuously.

So the *Regelung* tab reads only what is open: the category you clicked, at
most 40 parameters at a time. After a change it re-reads **only the changed
parameter** – that is the proof the controller accepted the value.

What you want to see permanently belongs in the selection under *Home
Assistant*: only those parameters run on the clock and become entities.

## The bus is slow

Every query is a telegram on a two-wire bus, and the controller answers in its
own time. The manager therefore asks in bundles of twelve parameters with short
pauses in between. A hiccup in one bundle costs that bundle, not the whole
round.

A five-minute interval is ample for a heating system – its inertia is measured
in hours.

## Takeover by other add-ons

Another add-on can take charge of setpoints and schedules without this one
fighting back. Three rules make that bearable:

* **Nothing changes until someone registers.** Out of the box nobody owns
  anything; the add-on stays fully self-contained.
* **Owned means disabled, not hidden.** Values stay readable; only the input
  fields go quiet, with the owner's name next to them.
* **The person in front of it keeps the last word.** A *release* button sits
  above the table. A lock you cannot open is not collaboration.

Other add-ons reach this one at `http://local-heizungsanlage:8099` (hyphen –
the slug's underscore becomes a dash in the host name).

```
PUT /api/uebernahme
{"quelle": "heizungsplaner", "name": "Heizungsplaner",
 "hinweis": "setpoints come from the weekly plan", "parameter": ["710", "712"]}

POST /api/setzen
{"nr": "710", "wert": "21.5", "quelle": "heizungsplaner"}

GET    /api/uebernahme
DELETE /api/uebernahme/heizungsplaner
```

Each `PUT` replaces that source's whole list; an empty list unregisters it.
Setting an owned parameter without `quelle` answers **409** and names the
owner, rather than letting a hand-made change be silently overwritten on the
next tick.

## Working with the Heating Planner

The entities are ordinary sensors and can be used anywhere. In the
[Heating Planner](https://github.com/Melle79/HA-heizungsplaner-heating-planner)
one of them matters in particular: the **operating hours counter**. Enter it
under *Oil tank → Runtime counter* and the planner turns it into consumption,
days left and cost.
