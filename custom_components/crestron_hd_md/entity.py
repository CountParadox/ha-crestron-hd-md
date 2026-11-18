"""Base entity for Crestron HD-MD switchers."""

from __future__ import annotations

from homeassistant.const import CONF_HOST, CONF_MAC
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_FIRMWARE, CONF_MODEL, CONF_SERIAL, DOMAIN, MANUFACTURER
from .coordinator import CrestronHdMdCoordinator


class CrestronHdMdEntity(CoordinatorEntity[CrestronHdMdCoordinator]):
    """Common device info."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: CrestronHdMdCoordinator, key: str) -> None:
        super().__init__(coordinator)
        entry = coordinator.config_entry
        data = entry.data
        device_id = entry.unique_id or entry.entry_id
        self._attr_unique_id = f"{device_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            manufacturer=MANUFACTURER,
            model=data.get(CONF_MODEL),
            name=entry.title,
            sw_version=data.get(CONF_FIRMWARE),
            serial_number=data.get(CONF_SERIAL),
            configuration_url=f"http://{data[CONF_HOST]}",
            connections=(
                {(CONNECTION_NETWORK_MAC, data[CONF_MAC])} if data.get(CONF_MAC) else set()
            ),
        )
