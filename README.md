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
- Each virtual is a **light**: on/off, effect selection, brightness. Turning on resumes the last effect.
- LedFx server device:
  - **Pause** switch (global pause)
  - **Scene** select: one entity for all LedFx scenes
  - **Audio input** select: switch LedFx's audio source from HA
- Service **`ledfx_plus.set_effect`**: set an effect and/or change its settings

```yaml
action: ledfx_plus.set_effect
target:
  entity_id: light.desk_strip
data:
  effect: energy
  config:
    gradient: "linear-gradient(90deg, #ff0000 0%, #0000ff 100%)"
    brightness: 0.8
```

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
