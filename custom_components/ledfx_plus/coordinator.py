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
    AUDIO_EVENTS,
    CONF_EXCLUDED_VIRTUALS,
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
    scenes: dict[str, Any] = field(default_factory=dict)
    audio_devices: dict[int, str] = field(default_factory=dict)
    audio_device: int | None = None


def is_device_virtual(virtual: dict[str, Any]) -> bool:
    """LedFx auto-creates one virtual per physical device."""
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
        # Audio device enumeration is comparatively expensive on the LedFx side,
        # so only re-read it at startup and when LedFx reports a change.
        self._audio_dirty = True

    # --- lifecycle --------------------------------------------------------

    async def _async_setup(self) -> None:
        try:
            self.info = await self.client.get_info()
            self.effect_types = await self.client.get_effect_types()
        except LedFxError as err:
            raise UpdateFailed(str(err)) from err

    async def _async_update_data(self) -> LedFxData:
        prev = self.data or LedFxData()
        try:
            virtuals, scenes = await asyncio.gather(
                self.client.get_virtuals(), self.client.get_scenes()
            )
            audio_devices, audio_device = prev.audio_devices, prev.audio_device
            if self._audio_dirty:
                audio = await self.client.get_audio_devices()
                audio_devices = {int(i): n for i, n in (audio.get("devices") or {}).items()}
                audio_device = audio.get("active_device_index")
                self._audio_dirty = False
        except LedFxError as err:
            raise UpdateFailed(str(err)) from err
        return LedFxData(
            virtuals=virtuals.get("virtuals", {}),
            paused=bool(virtuals.get("paused")),
            scenes=scenes,
            audio_devices=audio_devices,
            audio_device=audio_device,
        )

    @callback
    def start_push(self) -> None:
        self.config_entry.async_create_background_task(
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
        if event_type in AUDIO_EVENTS:
            self._audio_dirty = True
        self.config_entry.async_create_task(self.hass, self.async_request_refresh())

    def mark_audio_dirty(self) -> None:
        self._audio_dirty = True

    # --- filtering --------------------------------------------------------

    def wanted_virtual_ids(self) -> set[str]:
        """Virtual IDs that should have entities: everything not explicitly excluded."""
        excluded = set(self.config_entry.options.get(CONF_EXCLUDED_VIRTUALS, []))
        virtuals = self.data.virtuals if self.data else {}
        return set(virtuals) - excluded
