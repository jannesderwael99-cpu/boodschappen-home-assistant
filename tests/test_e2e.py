"""Echte test tegen de Boodschappen-server (lokale PHP-testserver op 127.0.0.1:8765)."""

import socket

import pytest
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.boodschappen.const import DOMAIN

URL = "http://127.0.0.1:8765"


def server_up() -> bool:
    try:
        with socket.create_connection(("127.0.0.1", 8765), timeout=1):
            return True
    except OSError:
        return False


@pytest.mark.enable_socket
@pytest.mark.allow_hosts(["127.0.0.1"])
@pytest.mark.skipif(not server_up(), reason="lokale PHP-testserver draait niet")
async def test_real_server(hass: HomeAssistant) -> None:
    import pytest_socket

    pytest_socket.enable_socket()  # de HA-testomgeving blokkeert netwerk; hier mag het (alleen lokaal)
    pytest_socket.socket_allow_hosts(["127.0.0.1"], allow_unix_socket=True)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"server": URL, "password": "fout"})
    assert result["errors"] == {"base": "invalid_auth"}
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"server": URL, "password": "TestWachtwoord"})
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert entry.state is config_entries.ConfigEntryState.LOADED
    todo = "todo.boodschappen"
    start = int(hass.states.get(todo).state)

    await hass.services.async_call("todo", "add_item", {"item": "Tomaten (1 kg)", "description": "Voor soep"}, target={"entity_id": todo}, blocking=True)
    assert int(hass.states.get(todo).state) == start + 1
    items = (await entry.runtime_data.api.get_items())
    tom = next(i for i in items if i["name"] == "Tomaten")
    assert tom["qty"] == "1 kg" and tom["note"] == "Voor soep" and tom["added_by"] == "Home Assistant"

    await hass.services.async_call("todo", "update_item", {"item": "Tomaten (1 kg)", "status": "completed"}, target={"entity_id": todo}, blocking=True)
    assert int(hass.states.get(todo).state) == start
    await hass.services.async_call(DOMAIN, "add_items", {"items": ["Uien (2)"]}, blocking=True)
    await hass.services.async_call("todo", "remove_item", {"item": ["Uien (2)"]}, target={"entity_id": todo}, blocking=True)
    items = (await entry.runtime_data.api.get_items())
    assert next(i for i in items if i["name"] == "Tomaten")["done"] is True
    assert not any(i["name"] == "Uien" for i in items)
    assert await hass.config_entries.async_unload(entry.entry_id)
