"""Config flow for Crestron HD-MD switchers."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import CrestronHdMdClient, CrestronHdMdConnectionError, CrestronHdMdError
from .const import (
    CONF_FIRMWARE,
    CONF_MODEL,
    CONF_SCAN_INTERVAL,
    CONF_SERIAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)


class CrestronHdMdConfigFlow(ConfigFlow, domain=DOMAIN):
    """Add a switcher by IP address. The switcher needs no login."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            client = CrestronHdMdClient(async_get_clientsession(self.hass), host)
            try:
                info = await client.async_get_info()
                await client.async_get_state()
            except CrestronHdMdConnectionError:
                errors["base"] = "cannot_connect"
            except CrestronHdMdError:
                errors["base"] = "not_hd_md"
            else:
                await self.async_set_unique_id(
                    info.get("mac") or info.get("serial") or host
                )
                self._abort_if_unique_id_configured()
                data = {CONF_HOST: host}
                for key, conf in (
                    ("mac", CONF_MAC),
                    ("model", CONF_MODEL),
                    ("serial", CONF_SERIAL),
                    ("firmware", CONF_FIRMWARE),
                ):
                    if info.get(key):
                        data[conf] = info[key]
                title = user_input.get(CONF_NAME) or info.get("model") or host
                return self.async_create_entry(title=title, data=data)

        schema = vol.Schema(
            {
                vol.Required(CONF_HOST): str,
                vol.Optional(CONF_NAME): str,
            }
        )
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(schema, user_input),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return CrestronHdMdOptionsFlow()


class CrestronHdMdOptionsFlow(OptionsFlow):
    """Polling interval."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_SCAN_INTERVAL,
                    default=self.config_entry.options.get(
                        CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                    ),
                ): vol.All(vol.Coerce(int), vol.Range(min=2, max=300)),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
