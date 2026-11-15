"""De boodschappenlijst als takenlijst in Home Assistant."""

from __future__ import annotations

import re
from typing import Any

from homeassistant.components.todo import (
    TodoItem,
    TodoItemStatus,
    TodoListEntity,
    TodoListEntityFeature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import BoodschappenConfigEntry, BoodschappenCoordinator, new_cid

PARALLEL_UPDATES = 0

_QTY = re.compile(r"^(.*\S)\s*\(([^()]{1,40})\)\s*$")


def split_summary(summary: str) -> tuple[str, str | None]:
    """'Gehakt (500 g)' -> ('Gehakt', '500 g'); 'Melk' -> ('Melk', None)."""
    text = (summary or "").strip()
    m = _QTY.match(text)
    if m:
        return m.group(1).strip(), m.group(2).strip()
    return text, None


def join_summary(name: str, qty: str | None) -> str:
    return f"{name} ({qty})" if qty else name


def device_info(entry: BoodschappenConfigEntry) -> DeviceInfo:
    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name="Boodschappen",
        manufacturer="Boodschappen",
        model="Gedeelde boodschappenlijst",
        entry_type=DeviceEntryType.SERVICE,
    )


async def async_setup_entry(
    hass: HomeAssistant, entry: BoodschappenConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    async_add_entities([BoodschappenTodoList(entry.runtime_data, entry)])


class BoodschappenTodoList(CoordinatorEntity[BoodschappenCoordinator], TodoListEntity):
    """Boodschappenlijst: toevoegen, aanpassen, afvinken en verwijderen."""

    _attr_has_entity_name = True
    _attr_name = None  # heet gewoon "Boodschappen" (handig voor Assist: "zet melk op Boodschappen")
    _attr_supported_features = (
        TodoListEntityFeature.CREATE_TODO_ITEM
        | TodoListEntityFeature.UPDATE_TODO_ITEM
        | TodoListEntityFeature.DELETE_TODO_ITEM
        | TodoListEntityFeature.SET_DESCRIPTION_ON_ITEM
    )

    def __init__(self, coordinator: BoodschappenCoordinator, entry: BoodschappenConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_lijst"
        self._attr_device_info = device_info(entry)

    @property
    def todo_items(self) -> list[TodoItem]:
        return [
            TodoItem(
                uid=i["cid"],
                summary=join_summary(i.get("name") or "", i.get("qty")),
                status=TodoItemStatus.COMPLETED if i.get("done") else TodoItemStatus.NEEDS_ACTION,
                description=i.get("note") or None,
            )
            for i in (self.coordinator.data or [])
        ]

    def _find(self, uid: str | None) -> dict[str, Any] | None:
        return next((i for i in (self.coordinator.data or []) if i.get("cid") == uid), None)

    async def async_create_todo_item(self, item: TodoItem) -> None:
        name, qty = split_summary(item.summary or "")
        if not name:
            return
        cid = new_cid()
        op: dict[str, Any] = {"op": "add", "cid": cid, "name": name}
        if qty:
            op["qty"] = qty
        if item.description:
            op["note"] = item.description
        ops = [op]
        if item.status == TodoItemStatus.COMPLETED:
            ops.append({"op": "done", "cid": cid})
        await self.coordinator.async_apply(ops)

    async def async_update_todo_item(self, item: TodoItem) -> None:
        current = self._find(item.uid)
        if current is None:
            return
        ops: list[dict[str, Any]] = []
        upd: dict[str, Any] = {}
        if item.summary is not None:
            name, qty = split_summary(item.summary)
            if name and name != current.get("name"):
                upd["name"] = name
            if (qty or "") != (current.get("qty") or ""):
                upd["qty"] = qty or ""
        if (item.description or "") != (current.get("note") or ""):
            upd["note"] = item.description or ""
        if upd:
            ops.append({"op": "update", "cid": item.uid, **upd})
        done = item.status == TodoItemStatus.COMPLETED
        if item.status is not None and done != bool(current.get("done")):
            ops.append({"op": "done" if done else "undone", "cid": item.uid})
        await self.coordinator.async_apply(ops)

    async def async_delete_todo_items(self, uids: list[str]) -> None:
        await self.coordinator.async_apply([{"op": "delete", "cid": uid} for uid in uids])

    @callback
    def _handle_coordinator_update(self) -> None:
        super()._handle_coordinator_update()
