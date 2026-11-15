"""Houdt de boodschappenlijst bij."""

from __future__ import annotations

import logging
import uuid
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import BoodschappenApi, BoodschappenError, InvalidAuth
from .const import CONF_SCAN_INTERVAL, DOMAIN, scan_interval

_LOGGER = logging.getLogger(__name__)

type BoodschappenConfigEntry = ConfigEntry[BoodschappenCoordinator]


def new_cid() -> str:
    """Uniek id voor een nieuw item (zoals de app dat doet)."""
    return uuid.uuid4().hex


class BoodschappenCoordinator(DataUpdateCoordinator[list[dict[str, Any]]]):
    """Haalt de lijst op en stuurt wijzigingen door."""

    config_entry: BoodschappenConfigEntry

    def __init__(self, hass: HomeAssistant, entry: BoodschappenConfigEntry, api: BoodschappenApi) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=scan_interval(entry.options.get(CONF_SCAN_INTERVAL)),
        )
        self.api = api

    async def _async_update_data(self) -> list[dict[str, Any]]:
        try:
            return await self.api.get_items()
        except InvalidAuth as err:
            raise ConfigEntryAuthFailed("Opnieuw aanmelden nodig") from err
        except BoodschappenError as err:
            raise UpdateFailed(f"Boodschappen-server: {err}") from err

    async def async_apply(self, ops: list[dict[str, Any]]) -> None:
        """Wijzigingen doorsturen en de lijst meteen bijwerken."""
        if not ops:
            return
        try:
            items = await self.api.sync(ops)
        except InvalidAuth as err:
            self.config_entry.async_start_reauth(self.hass)
            raise HomeAssistantError("Opnieuw aanmelden bij Boodschappen nodig") from err
        except BoodschappenError as err:
            raise HomeAssistantError(f"Boodschappen-server: {err}") from err
        self.async_set_updated_data(items)

    @property
    def open_items(self) -> list[dict[str, Any]]:
        return [i for i in (self.data or []) if not i.get("done")]
