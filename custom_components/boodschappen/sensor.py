"""Hoeveel er nog te halen is."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import BoodschappenConfigEntry, BoodschappenCoordinator
from .todo import device_info, join_summary

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant, entry: BoodschappenConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    async_add_entities([BoodschappenOpenSensor(entry.runtime_data, entry)])


class BoodschappenOpenSensor(CoordinatorEntity[BoodschappenCoordinator], SensorEntity):
    """Aantal items dat nog op de lijst staat (handig voor dashboards en meldingen)."""

    _attr_has_entity_name = True
    _attr_translation_key = "open_items"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: BoodschappenCoordinator, entry: BoodschappenConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_te_halen"
        self._attr_device_info = device_info(entry)

    @property
    def native_value(self) -> int:
        return len(self.coordinator.open_items)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"items": [join_summary(i.get("name") or "", i.get("qty")) for i in self.coordinator.open_items]}
