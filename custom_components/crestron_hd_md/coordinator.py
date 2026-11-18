"""Data update coordinator for Crestron HD-MD switchers."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import CrestronHdMdClient, CrestronHdMdError
from .const import CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)

type CrestronHdMdConfigEntry = ConfigEntry[CrestronHdMdCoordinator]


class CrestronHdMdCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Poll one switcher and send commands to it."""

    config_entry: CrestronHdMdConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: CrestronHdMdConfigEntry,
        client: CrestronHdMdClient,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} {client.host}",
            update_interval=timedelta(
                seconds=entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
            ),
        )
        self.client = client

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            return await self.client.async_get_state()
        except CrestronHdMdError as err:
            raise UpdateFailed(str(err)) from err

    @property
    def input_count(self) -> int:
        return len(self.data["input_names"])

    @property
    def output_count(self) -> int:
        return len(self.data["routes"])

    def input_name(self, number: int) -> str:
        """Name of an input (numbered from 1), unique among the inputs."""
        names = self.data["input_names"]
        name = names[number - 1].strip() if number <= len(names) else ""
        if not name:
            return f"Input {number}"
        # Two inputs with the same name would be indistinguishable in a list.
        if [n.strip() for n in names].count(name) > 1:
            return f"{name} ({number})"
        return name

    def output_name(self, number: int) -> str:
        names = self.data["output_names"]
        name = names[number - 1].strip() if number <= len(names) else ""
        return name or f"Output {number}"

    async def async_set_route(self, output: int, input_number: int) -> None:
        try:
            await self.client.async_set_route(
                output, input_number, self.input_count, self.output_count
            )
        except (CrestronHdMdError, ValueError) as err:
            raise HomeAssistantError(str(err)) from err
        await self.async_refresh()

    async def async_set_output_enabled(self, output: int, enabled: bool) -> None:
        try:
            await self.client.async_set_output_enabled(output, enabled)
        except CrestronHdMdError as err:
            raise HomeAssistantError(str(err)) from err
        await self.async_refresh()
