"""Config and options flow for LedFx Plus."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
)

from .api import LedFxClient, LedFxError
from .const import CONF_VIRTUALS, DEFAULT_PORT, DOMAIN
from .coordinator import is_device_virtual

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
    }
)


class LedFxPlusConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return LedFxPlusOptionsFlow()

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            host, port = user_input[CONF_HOST], user_input[CONF_PORT]
            await self.async_set_unique_id(f"{host}:{port}")
            self._abort_if_unique_id_configured()
            client = LedFxClient(async_get_clientsession(self.hass), host, port)
            try:
                await client.get_info()
            except LedFxError:
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(title=f"LedFx ({host})", data=user_input)
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(DATA_SCHEMA, user_input),
            errors=errors,
        )


class LedFxPlusOptionsFlow(OptionsFlow):
    """Choose which LedFx virtuals become Home Assistant entities."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        coordinator = self.config_entry.runtime_data
        virtuals = coordinator.data.virtuals

        if user_input is not None:
            return self.async_create_entry(data=user_input)

        options = [
            SelectOptionDict(
                value=vid,
                label=v.get("config", {}).get("name", vid)
                + (" (device)" if is_device_virtual(v) else ""),
            )
            for vid, v in sorted(virtuals.items(), key=lambda i: i[1].get("config", {}).get("name", i[0]))
        ]
        default = sorted(coordinator.wanted_virtual_ids())

        schema = vol.Schema(
            {
                vol.Optional(CONF_VIRTUALS, default=default): SelectSelector(
                    SelectSelectorConfig(options=options, multiple=True)
                ),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
