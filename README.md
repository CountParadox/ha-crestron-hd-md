# Crestron HD-MD Switcher for Home Assistant

A Home Assistant custom integration (installable through HACS) for Crestron
HD-MD series HDMI switchers. It selects which input each output shows, using
the switcher's built-in web interface over your LAN. No control processor,
cloud or extra software is needed.

> **Status:** developed and tested against an HD-MD4x2-4K-E (firmware
> 1.0.0.2162). Other HD-MD switchers with the same style of web interface
> (`aj.html`) should work, but are untested. The newer "-4KZ-E" models use a
> different web interface and are not supported.

## Features

- **Source selection**: one select per output, listing the switcher's inputs by
  the names stored in the switcher, plus **None** to disconnect the output.
- **Output enable**: a switch per output.
- **Signal detection**: a sensor per input (source detected) and per output
  (display detected).
- **Select input by number** action for automations that should not depend on
  input names.

The number of inputs and outputs is read from the switcher, so a 4x2 gives four
inputs and two outputs without any configuration.

## Installation

### HACS

1. In HACS open the menu (top right) and choose **Custom repositories**.
2. Add `https://github.com/CountParadox/ha-crestron-hd-md` with type **Integration**.
3. Install **Crestron HD-MD Switcher** and restart Home Assistant.

### Manual

Copy `custom_components/crestron_hd_md` into your Home Assistant
`config/custom_components` folder and restart.

## Setup

**Settings → Devices & services → Add integration → Crestron HD-MD Switcher**,
then enter the switcher's IP address. No user name or password is asked for
(see [Security](#security)).

Options (the **Configure** button): polling interval, 10 seconds by default.

## Entities

For a 4x2 switcher named "AV switcher":

| Entity | What it does |
| --- | --- |
| `select.av_switcher_output_1_source` | Input shown on output 1 |
| `select.av_switcher_output_2_source` | Input shown on output 2 |
| `switch.av_switcher_output_1_enabled`, `..._2_enabled` | Enable or disable an output |
| `binary_sensor.av_switcher_input_1_signal` ... `_4_signal` | A source is detected on the input |
| `binary_sensor.av_switcher_output_1_display`, `..._2_display` | A display is detected on the output |

The select's options are the input names set in the switcher's own web
interface (**Routing → Save Names**). Renaming an input there renames the
option in Home Assistant within one polling interval. If two inputs have the
same name, the input number is added to tell them apart.

Each select also has the attributes `input_number`, `output_name` and
`output_format` (what the output reports sending, for example `No Source`).

## Actions

Choose a source by name with the standard select action:

```yaml
action: select.select_option
target:
  entity_id: select.av_switcher_output_1_source
data:
  option: INPUT2
```

Or by number, which keeps working when inputs are renamed:

```yaml
action: crestron_hd_md.select_input
target:
  entity_id: select.av_switcher_output_1_source
data:
  input: 2
```

`input: 0` disconnects the output.

## Security

On the tested firmware the switcher's web login only hides the menus of its own
web page. The switcher itself answers status requests and accepts commands from
anyone on the network, logged in or not. That is why this integration needs no
credentials, and it also means the login does not protect the switcher: keep it
on a trusted network or VLAN.

## How it works

- `GET /` embeds the model, serial number, firmware and MAC address.
- `GET /aj.html?a=rout|input|outp` returns the status as JSON.
- `GET /aj.html?a=command&cmd=A&p1=2` routes input 2 to output 1 (`B` is
  output 2). The switcher stores any number it is given, so the integration
  checks the range before sending.

## Development

```bash
pip install pytest-homeassistant-custom-component
```

```bash
pytest tests
```

The client lives in `custom_components/crestron_hd_md/api.py` and has no Home
Assistant dependency. The Home Assistant test harness does not support Windows.

## Trademark

Crestron and the Crestron logo are trademarks of Crestron Electronics, Inc. The
logo is used only to identify the switchers this integration controls; this
project is not affiliated with or endorsed by Crestron.
