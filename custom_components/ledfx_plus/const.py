"""Constants for LedFx Plus."""

from datetime import timedelta

DOMAIN = "ledfx_plus"
DEFAULT_PORT = 8888

# Websocket events drive updates; polling is only a safety net.
FALLBACK_SCAN_INTERVAL = timedelta(seconds=60)
WS_RECONNECT_DELAY = 10  # seconds
REFRESH_DEBOUNCE = 0.5  # seconds

# LedFx events (see ledfx/events.py) that change state we show in HA.
# High-frequency events (visualisation_update, graph_update, ...) are deliberately not subscribed.
AUDIO_EVENTS = ("audio_input_device_changed", "audio_device_list_changed")
WS_EVENTS = (
    "effect_set",
    "effect_updated",
    "effect_cleared",
    "global_pause",
    "virtual_pause",
    "virtual_config_update",
    "scene_activated",
    "scene_deleted",
    "preset_activated",
    *AUDIO_EVENTS,
)

# Options: virtual IDs the user chose NOT to import. New virtuals are imported automatically.
CONF_EXCLUDED_VIRTUALS = "excluded_virtuals"

SERVICE_SET_EFFECT = "set_effect"
ATTR_CONFIG = "config"
