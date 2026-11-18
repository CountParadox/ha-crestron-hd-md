"""One switch per output: output enabled."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import CrestronHdMdConfigEntry, CrestronHdMdCoordinator
from .entity import CrestronHdMdEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CrestronHdMdConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        OutputEnabledSwitch(coordinator, output)
        for output in range(1, len(coordinator.data["output_enabled"]) + 1)
    )


class OutputEnabledSwitch(CrestronHdMdEntity, SwitchEntity):
    """Enables or disables one HDMI output."""

    _attr_translation_key = "output_enabled"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: CrestronHdMdCoordinator, output: int) -> None:
        super().__init__(coordinator, f"output_{output}_enabled")
        self._output = output
        self._attr_translation_placeholders = {"output": str(output)}

    @property
    def is_on(self) -> bool | None:
        enabled = self.coordinator.data["output_enabled"]
        return enabled[self._output - 1] if self._output <= len(enabled) else None

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.async_set_output_enabled(self._output, True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.async_set_output_enabled(self._output, False)
