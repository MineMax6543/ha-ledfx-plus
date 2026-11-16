"""Constants for LedFx Plus."""

from datetime import timedelta

DOMAIN = "ledfx_plus"
DEFAULT_PORT = 8888

# Websocket events drive updates; polling is only a safety net.
FALLBACK_SCAN_INTERVAL = timedelta(seconds=60)
WS_RECONNECT_DELAY = 10  # seconds
REFRESH_DEBOUNCE = 0.5  # seconds

# LedFx events that indicate virtual/effect state changed.
# Deliberately NOT subscribing to high-frequency pixel/visualisation events.
WS_EVENTS = (
    "effect_set",
    "effect_cleared",
    "global_pause",
    "scene_activated",
    "virtual_config_update",
    "virtual_pause",
)

CONF_VIRTUALS = "virtuals"
CONF_INCLUDE_DEVICE_VIRTUALS = "include_device_virtuals"
