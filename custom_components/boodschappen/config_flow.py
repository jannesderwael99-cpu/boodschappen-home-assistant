"""Koppelen met je Boodschappen-account."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_PASSWORD
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .api import BoodschappenApi, CannotConnect, InvalidAuth, normalize_server
from .const import (
    CONF_SCAN_INTERVAL,
    CONF_SERVER,
    CONF_TOKEN,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SERVER,
    DOMAIN,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)

PASSWORD_SELECTOR = TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))


class BoodschappenConfigFlow(ConfigFlow, domain=DOMAIN):
    """Wachtwoord van de app eenmalig inruilen voor een token (het wachtwoord wordt niet bewaard)."""

    VERSION = 1

    async def _login(self, endpoint: str, password: str) -> tuple[str | None, dict[str, str]]:
        api = BoodschappenApi(async_get_clientsession(self.hass), endpoint)
        try:
            return await api.login(password), {}
        except InvalidAuth:
            return None, {"base": "invalid_auth"}
        except CannotConnect:
            return None, {"base": "cannot_connect"}
        except Exception:  # noqa: BLE001
            _LOGGER.exception("Onverwachte fout bij het aanmelden")
            return None, {"base": "unknown"}

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                endpoint = normalize_server(user_input[CONF_SERVER])
            except ValueError:
                errors[CONF_SERVER] = "invalid_url"
            else:
                await self.async_set_unique_id(endpoint.lower())
                self._abort_if_unique_id_configured()
                token, errors = await self._login(endpoint, user_input[CONF_PASSWORD])
                if token:
                    return self.async_create_entry(
                        title="Boodschappen", data={CONF_SERVER: endpoint, CONF_TOKEN: token}
                    )
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_SERVER, default=(user_input or {}).get(CONF_SERVER, DEFAULT_SERVER)
                ): TextSelector(TextSelectorConfig(type=TextSelectorType.URL)),
                vol.Required(CONF_PASSWORD): PASSWORD_SELECTOR,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            token, errors = await self._login(entry.data[CONF_SERVER], user_input[CONF_PASSWORD])
            if token:
                return self.async_update_reload_and_abort(entry, data_updates={CONF_TOKEN: token})
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_PASSWORD): PASSWORD_SELECTOR}),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: Any) -> OptionsFlow:
        return BoodschappenOptionsFlow()


class BoodschappenOptionsFlow(OptionsFlow):
    """Hoe vaak Home Assistant de lijst ophaalt."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data={CONF_SCAN_INTERVAL: int(user_input[CONF_SCAN_INTERVAL])})
        current = self.config_entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        schema = vol.Schema(
            {
                vol.Required(CONF_SCAN_INTERVAL, default=current): NumberSelector(
                    NumberSelectorConfig(
                        min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL, step=5,
                        unit_of_measurement="s", mode=NumberSelectorMode.BOX,
                    )
                )
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
