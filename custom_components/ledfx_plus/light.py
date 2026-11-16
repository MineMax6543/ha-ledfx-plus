"""LedFx virtuals as Home Assistant lights."""

from __future__ import annotations

from typing import Any

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_EFFECT,
    ColorMode,
    LightEntity,
    LightEntityFeature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import LedFxConfigEntry
from .coordinator import LedFxCoordinator
from .entity import LedFxVirtualEntity, server_device_info

DEFAULT_EFFECT = "rainbow"


async def async_setup_entry(
    hass: HomeAssistant, entry: LedFxConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = entry.runtime_data

    # Register the hub device first so virtual devices can reference it via via_device.
    dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id, **server_device_info(coordinator)
    )

    known: set[str] = set()

    @callback
    def _sync() -> None:
        wanted = coordinator.wanted_virtual_ids()
        # Removed virtuals: their device is pruned in __init__, which removes the entity.
        known.intersection_update(wanted)
        new = wanted - known
        if new:
            known.update(new)
            async_add_entities(LedFxVirtualLight(coordinator, vid) for vid in new)

    _sync()
    entry.async_on_unload(coordinator.async_add_listener(_sync))


class LedFxVirtualLight(LedFxVirtualEntity, LightEntity):
    _attr_name = None  # use the device (virtual) name
    _attr_color_mode = ColorMode.BRIGHTNESS
    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}
    _attr_supported_features = LightEntityFeature.EFFECT

    def __init__(self, coordinator: LedFxCoordinator, virtual_id: str) -> None:
        super().__init__(coordinator, virtual_id, "light")
        self._attr_effect_list = sorted(coordinator.effect_types)

    @property
    def _effect(self) -> dict[str, Any]:
        return self.virtual.get("effect") or {}

    @property
    def is_on(self) -> bool:
        return bool(self.virtual.get("active")) and bool(self._effect.get("type"))

    @property
    def effect(self) -> str | None:
        return self._effect.get("type")

    @property
    def brightness(self) -> int | None:
        value = self._effect.get("config", {}).get("brightness")
        return None if value is None else round(float(value) * 255)

    async def async_turn_on(self, **kwargs: Any) -> None:
        client = self.coordinator.client
        effect = kwargs.get(ATTR_EFFECT) or self.effect or DEFAULT_EFFECT
        config: dict[str, Any] = {}
        if ATTR_BRIGHTNESS in kwargs:
            config["brightness"] = round(kwargs[ATTR_BRIGHTNESS] / 255, 3)

        if effect != self.effect:
            await client.set_effect(self.virtual_id, effect, config)
        elif config:
            await client.update_effect_config(self.virtual_id, effect, config)
        if not self.virtual.get("active"):
            await client.set_virtual_active(self.virtual_id, True)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.client.set_virtual_active(self.virtual_id, False)
        await self.coordinator.async_request_refresh()
