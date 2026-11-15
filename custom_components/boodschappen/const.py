"""Constanten voor de Boodschappen-integratie."""

from datetime import timedelta

DOMAIN = "boodschappen"

CONF_SERVER = "server"
CONF_TOKEN = "token"
CONF_SCAN_INTERVAL = "scan_interval"

DEFAULT_SERVER = "https://u207124p432749.web0164.zxcs-klant.nl"
DEFAULT_SCAN_INTERVAL = 60  # seconden
MIN_SCAN_INTERVAL = 15
MAX_SCAN_INTERVAL = 3600

ADDED_BY = "Home Assistant"

SERVICE_ADD_ITEMS = "add_items"
ATTR_ITEMS = "items"
ATTR_NOTE = "note"
ATTR_CONFIG_ENTRY_ID = "config_entry_id"

def scan_interval(seconds: int | None) -> timedelta:
    """Geldige verversingstijd."""
    s = DEFAULT_SCAN_INTERVAL if seconds is None else int(seconds)
    return timedelta(seconds=max(MIN_SCAN_INTERVAL, min(MAX_SCAN_INTERVAL, s)))
