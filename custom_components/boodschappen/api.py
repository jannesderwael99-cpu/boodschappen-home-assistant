"""Kleine client voor de Boodschappen-server (dezelfde API als de Android-app)."""

from __future__ import annotations

import asyncio
import re
from typing import Any
from urllib.parse import urlsplit

import aiohttp

from .const import ADDED_BY

# Sommige hostings weigeren onbekende programma's; we stellen ons netjes voor.
USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) HomeAssistant Boodschappen/1.0"
TIMEOUT = aiohttp.ClientTimeout(total=20)


class BoodschappenError(Exception):
    """Algemene fout."""


class CannotConnect(BoodschappenError):
    """Server niet bereikbaar."""


class InvalidAuth(BoodschappenError):
    """Wachtwoord of token klopt niet (meer)."""


def normalize_server(server: str) -> str:
    """'https://host', 'host/' of het volledige API-adres -> https://host/api/index.php."""
    s = server.strip()
    if not s:
        raise ValueError("leeg adres")
    if not re.match(r"^https?://", s, re.I):
        s = "https://" + s
    # Wachtwoord en token gaan nooit onversleuteld over het netwerk (http enkel voor lokaal testen).
    if s.lower().startswith("http://") and urlsplit(s).hostname not in ("localhost", "127.0.0.1", "::1"):
        raise ValueError("alleen https")
    s = s.rstrip("/")
    if s.lower().endswith(".php"):
        return s
    if s.lower().endswith("/api"):
        return s + "/index.php"
    return s + "/api/index.php"


class BoodschappenApi:
    """Praat met de Boodschappen-server."""

    def __init__(self, session: aiohttp.ClientSession, endpoint: str, token: str | None = None) -> None:
        self._session = session
        self._endpoint = endpoint
        self.token = token

    async def _request(self, method: str, action: str, payload: dict[str, Any] | None = None) -> Any:
        headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        try:
            async with self._session.request(
                method, self._endpoint, params={"action": action}, json=payload, headers=headers, timeout=TIMEOUT
            ) as resp:
                if resp.status == 401:
                    raise InvalidAuth
                try:
                    data = await resp.json(content_type=None)
                except (aiohttp.ContentTypeError, ValueError) as err:
                    raise BoodschappenError(f"Onverwacht antwoord van de server (HTTP {resp.status})") from err
                if resp.status >= 400:
                    msg = data.get("error") if isinstance(data, dict) else None
                    raise BoodschappenError(msg or f"HTTP {resp.status}")
                return data
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise CannotConnect(str(err)) from err

    async def login(self, password: str) -> str:
        """Wachtwoord inruilen voor een token (1 jaar geldig)."""
        data = await self._request("POST", "login", {"password": password})
        token = data.get("token") if isinstance(data, dict) else None
        if not token:
            raise BoodschappenError("Geen token ontvangen")
        self.token = token
        return token

    async def get_items(self) -> list[dict[str, Any]]:
        """Open items + wat de laatste 24 uur afgevinkt werd."""
        data = await self._request("GET", "list")
        return list(data.get("items", [])) if isinstance(data, dict) else []

    async def sync(self, ops: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Wijzigingen doorsturen; de server geeft meteen de actuele lijst terug."""
        data = await self._request("POST", "list_sync", {"ops": ops, "by": ADDED_BY})
        return list(data.get("items", [])) if isinstance(data, dict) else []
