"""De lijst in Home Assistant: tonen, toevoegen, aanpassen, afvinken, verwijderen."""

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.boodschappen.const import DOMAIN
from custom_components.boodschappen.todo import split_summary

TODO = "todo.boodschappen"
SENSOR = "sensor.boodschappen_to_buy"  # in een Nederlandstalige HA: sensor.boodschappen_te_halen


async def setup(hass, fake_server):
    fake_server.items = [
        {"cid": "a1", "name": "Melk", "qty": "2 l", "note": None, "done": False},
        {"cid": "b2", "name": "Brood", "qty": None, "note": "volkoren", "done": False},
        {"cid": "c3", "name": "Choco", "qty": None, "note": None, "done": True},
    ]
    entry = MockConfigEntry(domain=DOMAIN, unique_id="x", data={"server": "https://s/api/index.php", "token": "t"})
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


def test_split_summary() -> None:
    assert split_summary("Gehakt (500 g)") == ("Gehakt", "500 g")
    assert split_summary("Melk") == ("Melk", None)
    assert split_summary("  Kaas (jong)  ") == ("Kaas", "jong")


async def test_entities(hass: HomeAssistant, fake_server) -> None:
    await setup(hass, fake_server)
    assert hass.states.get(TODO).state == "2"  # 2 open items
    s = hass.states.get(SENSOR)
    assert s.state == "2" and s.attributes["items"] == ["Melk (2 l)", "Brood"]
    res = await hass.services.async_call("todo", "get_items", {}, target={"entity_id": TODO}, blocking=True, return_response=True)
    items = {i["summary"]: i for i in res[TODO]["items"]}
    assert items["Melk (2 l)"]["status"] == "needs_action"
    assert items["Brood"]["description"] == "volkoren"
    assert items["Choco"]["status"] == "completed"


async def test_add_update_check_delete(hass: HomeAssistant, fake_server) -> None:
    await setup(hass, fake_server)
    await hass.services.async_call("todo", "add_item", {"item": "Gehakt (500 g)", "description": "Voor lasagne (4 p.)"}, target={"entity_id": TODO}, blocking=True)
    add = fake_server.ops[-1]
    assert add["op"] == "add" and add["name"] == "Gehakt" and add["qty"] == "500 g" and add["note"] == "Voor lasagne (4 p.)"
    assert hass.states.get(TODO).state == "3"

    await hass.services.async_call("todo", "update_item", {"item": "Melk (2 l)", "status": "completed"}, target={"entity_id": TODO}, blocking=True)
    assert fake_server.ops[-1] == {"op": "done", "cid": "a1"}
    assert hass.states.get(TODO).state == "2"

    await hass.services.async_call("todo", "update_item", {"item": "Brood", "rename": "Brood (2)", "description": ""}, target={"entity_id": TODO}, blocking=True)
    assert fake_server.ops[-1] == {"op": "update", "cid": "b2", "qty": "2", "note": ""}

    await hass.services.async_call("todo", "remove_item", {"item": ["Choco"]}, target={"entity_id": TODO}, blocking=True)
    assert fake_server.ops[-1] == {"op": "delete", "cid": "c3"}
    assert not any(i["cid"] == "c3" for i in fake_server.items)

    await hass.services.async_call("todo", "remove_completed_items", {}, target={"entity_id": TODO}, blocking=True)
    assert fake_server.ops[-1] == {"op": "delete", "cid": "a1"}


async def test_add_items_service(hass: HomeAssistant, fake_server) -> None:
    await setup(hass, fake_server)
    res = await hass.services.async_call(
        DOMAIN, "add_items",
        {"items": ["melk (1 l), eieren", {"name": "Gehakt", "quantity": "500 g"}], "note": "Voor lasagne (4 p.)"},
        blocking=True, return_response=True,
    )
    assert res == {"added": ["Melk (1 l)", "Eieren", "Gehakt (500 g)"]}
    new = fake_server.ops[-3:]
    assert [o["name"] for o in new] == ["Melk", "Eieren", "Gehakt"]
    assert all(o["note"] == "Voor lasagne (4 p.)" for o in new)
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(DOMAIN, "add_items", {"items": [" "]}, blocking=True)


async def test_unload(hass: HomeAssistant, fake_server) -> None:
    entry = await setup(hass, fake_server)
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
