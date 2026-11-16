"""Base entities for LedFx Plus."""

from __future__ import annotations

from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import LedFxCoordinator


def server_device_info(coordinator: LedFxCoordinator) -> DeviceInfo:
    entry = coordinator.config_entry
    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name=entry.title,
        manufacturer="LedFx",
        model="LedFx Server",
        sw_version=coordinator.info.get("version"),
        configuration_url=coordinator.client.base_url,
    )


class LedFxServerEntity(CoordinatorEntity[LedFxCoordinator]):
    """An entity on the LedFx server (hub) device."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: LedFxCoordinator, key: str) -> None:
        super().__init__(coordinator)
        self._attr_translation_key = key
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{key}"
        self._attr_device_info = server_device_info(coordinator)


class LedFxVirtualEntity(CoordinatorEntity[LedFxCoordinator]):
    """An entity belonging to one LedFx virtual (one HA device per virtual)."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: LedFxCoordinator, virtual_id: str, key: str) -> None:
        super().__init__(coordinator)
        entry_id = coordinator.config_entry.entry_id
        self.virtual_id = virtual_id
        self._attr_unique_id = f"{entry_id}_{virtual_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry_id}_{virtual_id}")},
            name=self.virtual.get("config", {}).get("name", virtual_id),
            manufacturer="LedFx",
            model="Device virtual" if self.virtual.get("is_device") else "Virtual",
            via_device=(DOMAIN, entry_id),
        )

    @property
    def virtual(self) -> dict[str, Any]:
        return self.coordinator.data.virtuals.get(self.virtual_id, {})

    @property
    def available(self) -> bool:
        return super().available and self.virtual_id in self.coordinator.data.virtuals
