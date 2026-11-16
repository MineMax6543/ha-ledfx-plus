"""Global pause switch for the LedFx server."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import LedFxConfigEntry
from .api import LedFxError
from .entity import LedFxServerEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: LedFxConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_entities([LedFxPauseSwitch(entry.runtime_data, "pause")])


class LedFxPauseSwitch(LedFxServerEntity, SwitchEntity):
    """On = all LedFx output paused."""

    @property
    def is_on(self) -> bool:
        return self.coordinator.data.paused

    async def _set(self, paused: bool) -> None:
        # LedFx only exposes a toggle, so only call it when the state differs.
        if self.coordinator.data.paused == paused:
            return
        try:
            await self.coordinator.client.toggle_global_pause()
        except LedFxError as err:
            raise HomeAssistantError(f"LedFx: {err}") from err
        await self.coordinator.async_request_refresh()

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._set(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._set(False)
