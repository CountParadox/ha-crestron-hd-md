"""Signal and display detection for inputs and outputs."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
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
    entities: list[BinarySensorEntity] = [
        SyncSensor(coordinator, "input", number)
        for number in range(1, len(coordinator.data["input_sync"]) + 1)
    ]
    entities.extend(
        SyncSensor(coordinator, "output", number)
        for number in range(1, len(coordinator.data["output_sync"]) + 1)
    )
    async_add_entities(entities)


class SyncSensor(CrestronHdMdEntity, BinarySensorEntity):
    """On when an input sees a source, or an output sees a display."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self, coordinator: CrestronHdMdCoordinator, kind: str, number: int
    ) -> None:
        super().__init__(coordinator, f"{kind}_{number}_sync")
        self._kind = kind
        self._number = number
        self._attr_translation_key = f"{kind}_sync"
        self._attr_translation_placeholders = {kind: str(number)}
        self._attr_device_class = (
            BinarySensorDeviceClass.PLUG
            if kind == "output"
            else BinarySensorDeviceClass.RUNNING
        )

    @property
    def is_on(self) -> bool | None:
        values = self.coordinator.data[f"{self._kind}_sync"]
        return values[self._number - 1] if self._number <= len(values) else None

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        if self._kind == "input":
            return {"input_name": self.coordinator.input_name(self._number)}
        return {"output_name": self.coordinator.output_name(self._number)}
