"""Boodschappen: je gedeelde boodschappenlijst in Home Assistant.

Home Assistant maakt zelf verbinding met de Boodschappen-server (met jouw eigen
account). De app of server kan je Home Assistant dus nooit bereiken.
"""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

from .api import BoodschappenApi
from .const import (
    ATTR_CONFIG_ENTRY_ID,
    ATTR_ITEMS,
    ATTR_NOTE,
    CONF_SERVER,
    CONF_TOKEN,
    DOMAIN,
    SERVICE_ADD_ITEMS,
)
from .coordinator import BoodschappenConfigEntry, BoodschappenCoordinator, new_cid
from .todo import split_summary

PLATFORMS = [Platform.TODO, Platform.SENSOR]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

ITEM_SCHEMA = vol.Any(
    cv.string,
    vol.Schema(
        {
            vol.Required("name"): cv.string,
            vol.Optional("quantity"): cv.string,
            vol.Optional("note"): cv.string,
        }
    ),
)

ADD_ITEMS_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ITEMS): vol.All(cv.ensure_list, [ITEM_SCHEMA]),
        vol.Optional(ATTR_NOTE): cv.string,
        vol.Optional(ATTR_CONFIG_ENTRY_ID): cv.string,
    }
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Service om (meerdere) producten in één keer toe te voegen, met hoeveelheid en notitie."""

    async def add_items(call: ServiceCall) -> ServiceResponse:
        entry = _resolve_entry(hass, call.data.get(ATTR_CONFIG_ENTRY_ID))
        common_note = (call.data.get(ATTR_NOTE) or "").strip()
        ops: list[dict[str, Any]] = []
        added: list[str] = []
        for raw in call.data[ATTR_ITEMS]:
            if isinstance(raw, str):
                parts = [p.strip() for p in raw.replace("\n", ",").split(",")]
                entries = [{"name": p} for p in parts if p]
            else:
                entries = [raw]
            for it in entries:
                name, qty = split_summary(str(it.get("name", "")))
                qty = (it.get("quantity") or qty or "").strip() or None
                if not name:
                    continue
                op: dict[str, Any] = {"op": "add", "cid": new_cid(), "name": name[:1].upper() + name[1:]}
                if qty:
                    op["qty"] = qty
                note = (it.get("note") or common_note).strip()
                if note:
                    op["note"] = note
                ops.append(op)
                added.append(op["name"] + (f" ({qty})" if qty else ""))
        if not ops:
            raise ServiceValidationError(translation_domain=DOMAIN, translation_key="no_items")
        await entry.runtime_data.async_apply(ops)
        return {"added": added}

    hass.services.async_register(
        DOMAIN, SERVICE_ADD_ITEMS, add_items, schema=ADD_ITEMS_SCHEMA, supports_response=SupportsResponse.OPTIONAL
    )
    return True


def _resolve_entry(hass: HomeAssistant, entry_id: str | None) -> BoodschappenConfigEntry:
    entries = [e for e in hass.config_entries.async_entries(DOMAIN) if e.state is ConfigEntryState.LOADED]
    if entry_id:
        entries = [e for e in entries if e.entry_id == entry_id]
    if len(entries) == 1:
        return entries[0]
    raise ServiceValidationError(
        translation_domain=DOMAIN, translation_key="no_entry" if not entries else "choose_entry"
    )


async def async_setup_entry(hass: HomeAssistant, entry: BoodschappenConfigEntry) -> bool:
    api = BoodschappenApi(async_get_clientsession(hass), entry.data[CONF_SERVER], entry.data[CONF_TOKEN])
    coordinator = BoodschappenCoordinator(hass, entry, api)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_options_updated))
    return True


async def _options_updated(hass: HomeAssistant, entry: BoodschappenConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: BoodschappenConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
