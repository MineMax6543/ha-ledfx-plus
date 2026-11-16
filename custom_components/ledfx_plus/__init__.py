"""LedFx Plus integration for Home Assistant."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import LedFxClient
from .const import DOMAIN
from .coordinator import LedFxCoordinator

PLATFORMS: list[Platform] = [Platform.LIGHT]

type LedFxConfigEntry = ConfigEntry[LedFxCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: LedFxConfigEntry) -> bool:
    client = LedFxClient(async_get_clientsession(hass), entry.data[CONF_HOST], entry.data[CONF_PORT])
    coordinator = LedFxCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    # Keep the device registry in sync with LedFx: no dead devices/entities.
    @callback
    def _prune() -> None:
        _remove_stale_devices(hass, entry, coordinator)

    _prune()
    entry.async_on_unload(coordinator.async_add_listener(_prune))
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    coordinator.start_push()
    return True


async def async_unload_entry(hass: HomeAssistant, entry: LedFxConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_options_updated(hass: HomeAssistant, entry: LedFxConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_remove_config_entry_device(
    hass: HomeAssistant, entry: LedFxConfigEntry, device: dr.DeviceEntry
) -> bool:
    """Allow manual deletion of a virtual's device once it no longer exists/is wanted."""
    coordinator = entry.runtime_data
    wanted = coordinator.wanted_virtual_ids()
    return not any(
        domain == DOMAIN and ident.removeprefix(f"{entry.entry_id}_") in wanted
        for domain, ident in device.identifiers
    )


@callback
def _remove_stale_devices(
    hass: HomeAssistant, entry: LedFxConfigEntry, coordinator: LedFxCoordinator
) -> None:
    """Remove devices (and with them their entities) for virtuals that are gone or deselected."""
    if not coordinator.last_update_success:
        return  # never prune based on a failed/empty fetch
    wanted = {f"{entry.entry_id}_{vid}" for vid in coordinator.wanted_virtual_ids()}
    wanted.add(entry.entry_id)  # the server/hub device itself
    dev_reg = dr.async_get(hass)
    for device in dr.async_entries_for_config_entry(dev_reg, entry.entry_id):
        idents = {ident for domain, ident in device.identifiers if domain == DOMAIN}
        if idents and not idents & wanted:
            dev_reg.async_update_device(device.id, remove_config_entry_id=entry.entry_id)
