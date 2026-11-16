"""LedFx virtuals as Home Assistant lights."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_EFFECT,
    ColorMode,
    LightEntity,
    LightEntityFeature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import LedFxConfigEntry
from .api import LedFxError
from .const import ATTR_CONFIG, SERVICE_SET_EFFECT
from .coordinator import LedFxCoordinator
from .entity import LedFxVirtualEntity

DEFAULT_EFFECT = "energy"


async def async_setup_entry(
    hass: HomeAssistant, entry: LedFxConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
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

    entity_platform.async_get_current_platform().async_register_entity_service(
        SERVICE_SET_EFFECT,
        {
            vol.Optional(ATTR_EFFECT): cv.string,
            vol.Optional(ATTR_CONFIG): dict,
        },
        "async_set_effect",
    )


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

    async def _call(self, coro) -> None:
        try:
            await coro
        except LedFxError as err:
            raise HomeAssistantError(f"LedFx: {err}") from err

    async def async_turn_on(self, **kwargs: Any) -> None:
        client = self.coordinator.client
        config: dict[str, Any] = {}
        if ATTR_BRIGHTNESS in kwargs:
            config["brightness"] = round(kwargs[ATTR_BRIGHTNESS] / 255, 3)

        effect = kwargs.get(ATTR_EFFECT)
        if effect is None and not self.effect:
            # Nothing running: resume the last effect LedFx remembers, else a default.
            effect = self.virtual.get("last_effect") or DEFAULT_EFFECT

        if effect and effect != self.effect:
            await self._call(client.set_effect(self.virtual_id, effect, config))
        elif config:
            await self._call(client.update_effect_config(self.virtual_id, config))
        if not self.virtual.get("active"):
            await self._call(client.set_virtual_active(self.virtual_id, True))
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._call(self.coordinator.client.set_virtual_active(self.virtual_id, False))
        await self.coordinator.async_request_refresh()

    async def async_set_effect(
        self, effect: str | None = None, config: dict[str, Any] | None = None
    ) -> None:
        """Service ledfx_plus.set_effect: set an effect and/or merge effect config."""
        if effect is None and not config:
            raise ServiceValidationError("Provide an effect, a config, or both.")
        if effect is not None and effect not in self.coordinator.effect_types:
            raise ServiceValidationError(f"Unknown LedFx effect: {effect}")
        client = self.coordinator.client
        if effect is not None and effect != self.effect:
            await self._call(client.set_effect(self.virtual_id, effect, config))
        else:
            await self._call(client.update_effect_config(self.virtual_id, config or {}))
        if not self.virtual.get("active"):
            await self._call(client.set_virtual_active(self.virtual_id, True))
        await self.coordinator.async_request_refresh()
