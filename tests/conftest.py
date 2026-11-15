"""Testopstelling."""

from __future__ import annotations

import copy
from typing import Any
from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


class FakeServer:
    """Speelt de Boodschappen-server na (zelfde regels als list_sync)."""

    def __init__(self) -> None:
        self.items: list[dict[str, Any]] = []
        self.ops: list[dict[str, Any]] = []
        self.fail_auth = False

    def _check(self):
        from custom_components.boodschappen.api import InvalidAuth

        if self.fail_auth:
            raise InvalidAuth

    async def get_items(self):
        self._check()
        return copy.deepcopy(self.items)

    async def sync(self, ops):
        self._check()
        self.ops.extend(ops)
        for o in ops:
            cur = next((i for i in self.items if i["cid"] == o.get("cid")), None)
            if o["op"] == "add" and cur is None:
                self.items.append({"cid": o["cid"], "name": o["name"], "qty": o.get("qty"), "note": o.get("note"), "done": False, "added_by": "Home Assistant"})
            elif o["op"] == "update" and cur:
                for k in ("name", "qty", "note"):
                    if k in o:
                        cur[k] = o[k] or None
            elif o["op"] == "done" and cur:
                cur["done"] = True
            elif o["op"] == "undone" and cur:
                cur["done"] = False
            elif o["op"] == "delete" and cur:
                self.items.remove(cur)
        return copy.deepcopy(self.items)


@pytest.fixture
def fake_server():
    server = FakeServer()
    with (
        patch("custom_components.boodschappen.api.BoodschappenApi.get_items", side_effect=server.get_items),
        patch("custom_components.boodschappen.api.BoodschappenApi.sync", side_effect=server.sync),
    ):
        yield server
