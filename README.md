# LedFx Plus

A Home Assistant custom integration for [LedFx](https://github.com/LedFx/LedFx), built to stay fast and clean.

> Early development – features are still being planned.

## Design goals

- **Push, not polling.** Listens to the LedFx websocket and refreshes only when something changes. A 60 s poll runs only as a safety net.
- **No dead entities.** Each LedFx virtual is a device in HA. If you delete a virtual in LedFx or deselect it in the options, its device and entities are removed automatically.
- **Only what you want.** You choose which virtuals to import. LedFx's auto-created device mirror virtuals are skipped by default.
- **No entity spam.** Detailed effect settings will be handled by services, not by dozens of number/select entities.

## Features (v0.1.0)

- UI setup (host + port)
- Each selected virtual is a **light**: on/off, effect selection, brightness

## Installation

### HACS (custom repository)

1. HACS → ⋮ → *Custom repositories*
2. Add `https://github.com/MineMax6543/ha-ledfx-plus`, category **Integration**
3. Install **LedFx Plus** and restart Home Assistant
4. *Settings → Devices & Services → Add Integration → LedFx Plus*

### Manual

Copy `custom_components/ledfx_plus` into `config/custom_components/` and restart Home Assistant.

## Configuration

| Field | Default | Description |
|-------|---------|-------------|
| Host  | –       | IP or hostname of your LedFx server |
| Port  | `8888`  | LedFx web/API port |

Use **Configure** on the integration to choose which virtuals are imported.

## License

MIT
