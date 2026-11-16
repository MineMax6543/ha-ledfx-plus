"""Data update coordinator for LedFx Plus (websocket push + slow fallback poll)."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import LedFxClient, LedFxError
from .const import (
    CONF_INCLUDE_DEVICE_VIRTUALS,
    CONF_VIRTUALS,
    DOMAIN,
    FALLBACK_SCAN_INTERVAL,
    REFRESH_DEBOUNCE,
    WS_EVENTS,
    WS_RECONNECT_DELAY,
)

if TYPE_CHECKING:
    from . import LedFxConfigEntry

_LOGGER = logging.getLogger(__name__)


@dataclass
class LedFxData:
    virtuals: dict[str, Any] = field(default_factory=dict)
    paused: bool = False


def is_device_virtual(virtual: dict[str, Any]) -> bool:
    """LedFx auto-creates one virtual per physical device; these are usually duplicates."""
    return bool(virtual.get("is_device"))


class LedFxCoordinator(DataUpdateCoordinator[LedFxData]):
    """Keeps LedFx state; refreshes on websocket events, polls rarely as fallback."""

    config_entry: LedFxConfigEntry

    def __init__(self, hass: HomeAssistant, entry: LedFxConfigEntry, client: LedFxClient) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=FALLBACK_SCAN_INTERVAL,
            request_refresh_debouncer=Debouncer(
                hass, _LOGGER, cooldown=REFRESH_DEBOUNCE, immediate=False
            ),
        )
        self.client = client
        self.effect_types: dict[str, str] = {}
        self.info: dict[str, Any] = {}
        self._ws_task: asyncio.Task | None = None

    # --- lifecycle --------------------------------------------------------

    async def _async_setup(self) -> None:
        try:
            self.info = await self.client.get_info()
            self.effect_types = await self.client.get_effect_types()
        except LedFxError as err:
            raise UpdateFailed(str(err)) from err

    async def _async_update_data(self) -> LedFxData:
        try:
            data = await self.client.get_virtuals()
        except LedFxError as err:
            raise UpdateFailed(str(err)) from err
        return LedFxData(virtuals=data.get("virtuals", {}), paused=bool(data.get("paused")))

    @callback
    def start_push(self) -> None:
        self._ws_task = self.config_entry.async_create_background_task(
            self.hass, self._ws_loop(), f"{DOMAIN}_websocket"
        )

    async def _ws_loop(self) -> None:
        while True:
            try:
                await self.client.listen(WS_EVENTS, self._on_event)
            except LedFxError as err:
                _LOGGER.debug("LedFx websocket disconnected: %s", err)
            await asyncio.sleep(WS_RECONNECT_DELAY)
            # Catch up on anything missed while disconnected.
            await self.async_request_refresh()

    @callback
    def _on_event(self, event_type: str) -> None:
        _LOGGER.debug("LedFx event: %s", event_type)
        self.hass.async_create_task(self.async_request_refresh())

    # --- filtering --------------------------------------------------------

    def wanted_virtual_ids(self) -> set[str]:
        """Virtual IDs that should have entities, based on the entry options."""
        options = self.config_entry.options
        virtuals = self.data.virtuals if self.data else {}
        selected = options.get(CONF_VIRTUALS)
        if selected is not None:
            return {vid for vid in selected if vid in virtuals}
        include_dev = options.get(CONF_INCLUDE_DEVICE_VIRTUALS, False)
        return {
            vid for vid, v in virtuals.items() if include_dev or not is_device_virtual(v)
        }
