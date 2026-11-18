"""One select per output: which input it shows."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import NO_INPUT
from .coordinator import CrestronHdMdConfigEntry, CrestronHdMdCoordinator
from .entity import CrestronHdMdEntity

SERVICE_SELECT_INPUT = "select_input"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CrestronHdMdConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        OutputSourceSelect(coordinator, output)
        for output in range(1, coordinator.output_count + 1)
    )

    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_SELECT_INPUT,
        {vol.Required("input"): vol.All(vol.Coerce(int), vol.Range(min=0))},
        "async_select_input",
    )


class OutputSourceSelect(CrestronHdMdEntity, SelectEntity):
    """The input routed to one output.

    The options are the input names stored in the switcher, so renaming an
    input in its web interface renames the option here.
    """

    _attr_translation_key = "output_source"

    def __init__(self, coordinator: CrestronHdMdCoordinator, output: int) -> None:
        super().__init__(coordinator, f"output_{output}_source")
        self._output = output
        self._attr_translation_placeholders = {"output": str(output)}

    def _input_options(self) -> dict[str, int]:
        coordinator = self.coordinator
        return {
            coordinator.input_name(number): number
            for number in range(1, coordinator.input_count + 1)
        }

    @property
    def options(self) -> list[str]:
        return [*self._input_options(), NO_INPUT]

    @property
    def current_option(self) -> str | None:
        routes = self.coordinator.data["routes"]
        if self._output > len(routes):
            return None
        number = routes[self._output - 1]
        if number == 0:
            return NO_INPUT
        if 1 <= number <= self.coordinator.input_count:
            return self.coordinator.input_name(number)
        return None

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        data = self.coordinator.data
        index = self._output - 1
        attributes: dict[str, object] = {
            "output_name": self.coordinator.output_name(self._output),
            "input_number": data["routes"][index] if index < len(data["routes"]) else None,
        }
        if index < len(data["output_formats"]):
            attributes["output_format"] = data["output_formats"][index]
        return attributes

    async def async_select_option(self, option: str) -> None:
        if option == NO_INPUT:
            number = 0
        else:
            options = self._input_options()
            if option not in options:
                raise ServiceValidationError(f"Unknown input: {option}")
            number = options[option]
        await self.coordinator.async_set_route(self._output, number)

    async def async_select_input(self, input: int) -> None:  # noqa: A002
        """Route an input by number (0 disconnects the output)."""
        if input > self.coordinator.input_count:
            raise ServiceValidationError(f"Input {input} does not exist")
        await self.coordinator.async_set_route(self._output, input)
