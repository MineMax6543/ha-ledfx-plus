"""Scene and audio input selects on the LedFx server device."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import LedFxConfigEntry
from .api import LedFxError
from .entity import LedFxServerEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: LedFxConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        [LedFxSceneSelect(coordinator, "scene"), LedFxAudioInputSelect(coordinator, "audio_input")]
    )


def _unique_labels(items: dict) -> dict[str, object]:
    """{label: key}; disambiguate duplicate names so every option maps to one key."""
    labels: dict[str, object] = {}
    for key, name in items.items():
        label = str(name) or str(key)
        if label in labels:
            label = f"{label} ({key})"
        labels[label] = key
    return labels


class LedFxSceneSelect(LedFxServerEntity, SelectEntity):
    """One select for all LedFx scenes instead of one entity per scene."""

    _attr_icon = "mdi:palette"

    @property
    def _labels(self) -> dict[str, object]:
        scenes = self.coordinator.data.scenes
        return _unique_labels({sid: s.get("name", sid) for sid, s in scenes.items()})

    @property
    def options(self) -> list[str]:
        return list(self._labels)

    @property
    def current_option(self) -> str | None:
        active = {sid for sid, s in self.coordinator.data.scenes.items() if s.get("active")}
        return next((label for label, sid in self._labels.items() if sid in active), None)

    async def async_select_option(self, option: str) -> None:
        scene_id = self._labels.get(option)
        if scene_id is None:
            raise ServiceValidationError(f"Unknown LedFx scene: {option}")
        try:
            await self.coordinator.client.activate_scene(str(scene_id))
        except LedFxError as err:
            raise HomeAssistantError(f"LedFx: {err}") from err
        await self.coordinator.async_request_refresh()


class LedFxAudioInputSelect(LedFxServerEntity, SelectEntity):
    """Which audio input LedFx listens to."""

    _attr_icon = "mdi:microphone"
    _attr_entity_category = EntityCategory.CONFIG

    @property
    def _labels(self) -> dict[str, object]:
        return _unique_labels(self.coordinator.data.audio_devices)

    @property
    def options(self) -> list[str]:
        return list(self._labels)

    @property
    def current_option(self) -> str | None:
        current = self.coordinator.data.audio_device
        return next((label for label, idx in self._labels.items() if idx == current), None)

    async def async_select_option(self, option: str) -> None:
        index = self._labels.get(option)
        if index is None:
            raise ServiceValidationError(f"Unknown audio input: {option}")
        try:
            await self.coordinator.client.set_audio_device(int(index))
        except LedFxError as err:
            raise HomeAssistantError(f"LedFx: {err}") from err
        self.coordinator.mark_audio_dirty()
        await self.coordinator.async_request_refresh()
