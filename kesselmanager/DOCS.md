# Boiler Manager

The Boiler Manager brings a heating controller into Home Assistant – through
[BSB-LAN](https://github.com/fredlcore/BSB-LAN), a small ESP32 sitting on the
controller's bus.

It does three things:

* **Select.** Out of every parameter your controller knows, you tick the ones
  that matter to you. Only those are read and published as entities.
* **Read.** On a configurable cycle, gently on the bus, with a sensible device
  class for Home Assistant.
* **Set.** Change setpoints and operating modes – behind two switches, both off
  by default.

## Requirements

A running BSB-LAN on the same network and an MQTT broker in Home Assistant.
Both are checked at startup; without the broker the interface still works, you
simply get no entities.

## The parameter catalogue

Which parameters a controller knows depends on the device. With Siemens
controllers – and therefore Weishaupt, Brötje, Elco and many others – it even
differs between device families. That is why there is the **tailored parameter
list** the BSB-LAN developer builds from a system's raw data, which goes into
the firmware as `BSB_LAN_custom_defs.h`.

The Boiler Manager does not parse that file; it reads the list **from BSB-LAN
itself**. That is more robust: what BSB-LAN serves is by definition what is
actually flashed. “Parameter 72” becomes “Operating hours”.

You read the catalogue once, and after that only when you flash the firmware
with a new list. It takes a minute or two, because every category goes over the
bus separately.

## Selection: what reaches Home Assistant

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

## Values in the control tab: on demand

The *Control* tab lists every parameter the controller reports as writable –
on a Weishaupt system that is over 160. Polling all of them would occupy the
bus permanently, and hardly any of them are worth watching continuously.

So the control tab reads **on demand**:

* Up to 25 displayed parameters it reads by itself. That happens as soon as you
  search for something specific – and that is exactly when you want figures.
* Above that it waits for the *Read values of the displayed parameters* button
  and reads at most 40 at a time.
* After a change it re-reads **only the changed parameter**. That is the proof
  the controller accepted the value.

Whatever you want to see continuously belongs under *Selection* – only those
parameters run on the cycle and become entities.

## Time programmes

A time programme is not a measurement but a string holding **three switching
windows** per day:

```
06:00-22:00 ##:##-##:## ##:##-##:##
```

`##:##` means “unused”. For readability the control tab shows only the windows
in use; the input field holds the full string, because that is exactly what is
expected when writing. To add a second window, replace the hashes:

```
06:00-08:00 16:00-22:00 ##:##-##:##
```

## Setting: the two switches

A wrong setpoint lets a flat go cold in winter. Setting therefore requires
**two** switches to be on:

1. in **BSB-LAN** itself (there it is called `buswritable`),
2. under *Settings → Write access* in this add-on.

Both are off by default. The *Control* tab always shows which of the two is
still missing. On top of that the manager only accepts parameters the
controller itself reports as writable, and asks before every change.

## The bus is slow

Every query is a telegram on a two-wire bus, and the controller answers in its
own time. The manager therefore asks in bundles of twelve parameters with short
pauses in between. A hiccup in one bundle costs that bundle, not the whole
round.

A five-minute interval is ample for a heating system – its inertia is measured
in hours.

## Working with the Heating Planner

The entities are ordinary sensors and can be used anywhere. In the
[Heating Planner](https://github.com/Melle79/HA-heizungsplaner-heating-planner)
one of them matters in particular: the **operating hours counter**. Enter it
under *Oil tank → Runtime counter* and the planner turns it into consumption,
days left and cost.
