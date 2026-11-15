"""Koppelen (config flow), herauthenticatie en opties."""

from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.boodschappen.api import CannotConnect, InvalidAuth
from custom_components.boodschappen.const import CONF_SCAN_INTERVAL, DOMAIN

SERVER = "https://boodschappen.example"


async def test_user_flow_ok(hass: HomeAssistant, fake_server) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    with patch("custom_components.boodschappen.api.BoodschappenApi.login", return_value="tok123"):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {"server": SERVER, "password": "geheim"})
        await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Boodschappen"
    assert result["data"] == {"server": SERVER + "/api/index.php", "token": "tok123"}  # wachtwoord NIET bewaard


async def test_user_flow_errors(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    for exc, err in ((InvalidAuth, "invalid_auth"), (CannotConnect, "cannot_connect"), (RuntimeError, "unknown")):
        with patch("custom_components.boodschappen.api.BoodschappenApi.login", side_effect=exc):
            result = await hass.config_entries.flow.async_configure(result["flow_id"], {"server": SERVER, "password": "x"})
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": err}


async def test_already_configured(hass: HomeAssistant) -> None:
    MockConfigEntry(domain=DOMAIN, unique_id=(SERVER + "/api/index.php").lower(), data={"server": SERVER + "/api/index.php", "token": "t"}).add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    with patch("custom_components.boodschappen.api.BoodschappenApi.login", return_value="t2"):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {"server": SERVER + "/", "password": "x"})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reauth_when_token_rejected(hass: HomeAssistant, fake_server) -> None:
    fake_server.fail_auth = True
    entry = MockConfigEntry(domain=DOMAIN, unique_id="x", data={"server": SERVER + "/api/index.php", "token": "oud"})
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is config_entries.ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1 and flows[0]["context"]["source"] == "reauth"
    fake_server.fail_auth = False
    with patch("custom_components.boodschappen.api.BoodschappenApi.login", return_value="nieuw"):
        result = await hass.config_entries.flow.async_configure(flows[0]["flow_id"], {"password": "geheim"})
        await hass.async_block_till_done()
    assert result["type"] is FlowResultType.ABORT and result["reason"] == "reauth_successful"
    assert entry.data["token"] == "nieuw"
    assert entry.state is config_entries.ConfigEntryState.LOADED


async def test_options(hass: HomeAssistant, fake_server) -> None:
    entry = MockConfigEntry(domain=DOMAIN, unique_id="x", data={"server": SERVER + "/api/index.php", "token": "t"})
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(result["flow_id"], {CONF_SCAN_INTERVAL: 120})
    await hass.async_block_till_done()
    assert entry.options[CONF_SCAN_INTERVAL] == 120
    assert entry.runtime_data.update_interval.total_seconds() == 120


def test_normalize_server_https_only() -> None:
    """Gewone http wordt geweigerd, behalve voor lokaal testen."""
    import pytest
    from custom_components.boodschappen.api import normalize_server

    assert normalize_server("voorbeeld.be") == "https://voorbeeld.be/api/index.php"
    assert normalize_server("https://voorbeeld.be/") == "https://voorbeeld.be/api/index.php"
    assert normalize_server("http://127.0.0.1:8765") == "http://127.0.0.1:8765/api/index.php"
    with pytest.raises(ValueError):
        normalize_server("http://voorbeeld.be")
