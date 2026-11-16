"""Minimal async client for the LedFx REST + websocket API."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable, Iterable
from typing import Any

import aiohttp

_LOGGER = logging.getLogger(__name__)


class LedFxError(Exception):
    """Raised when the LedFx API cannot be reached or returns an error."""


class LedFxClient:
    """Talks to a LedFx instance over HTTP and websocket."""

    def __init__(self, session: aiohttp.ClientSession, host: str, port: int) -> None:
        self._session = session
        self.base_url = f"http://{host}:{port}"

    async def _request(self, method: str, path: str, json: Any = None) -> dict[str, Any]:
        try:
            async with self._session.request(
                method,
                f"{self.base_url}/api{path}",
                json=json,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                resp.raise_for_status()
                data = await resp.json(content_type=None)
        except (aiohttp.ClientError, TimeoutError, ValueError) as err:
            raise LedFxError(f"{method} {path} failed: {err}") from err
        if isinstance(data, dict) and data.get("status") == "failed":
            raise LedFxError(str(data.get("payload") or data))
        return data or {}

    # --- read -------------------------------------------------------------

    async def get_info(self) -> dict[str, Any]:
        return await self._request("GET", "/info")

    async def get_virtuals(self) -> dict[str, Any]:
        return await self._request("GET", "/virtuals")

    async def get_effect_types(self) -> dict[str, str]:
        """Return {effect_id: display_name}."""
        data = await self._request("GET", "/schema")
        effects = data.get("effects", {})
        return {eid: (e.get("name") or eid) for eid, e in effects.items()}

    # --- write ------------------------------------------------------------

    async def set_virtual_active(self, virtual_id: str, active: bool) -> None:
        await self._request("PUT", f"/virtuals/{virtual_id}", {"active": active})

    async def set_effect(self, virtual_id: str, effect_type: str, config: dict | None = None) -> None:
        await self._request(
            "POST", f"/virtuals/{virtual_id}/effects", {"type": effect_type, "config": config or {}}
        )

    async def update_effect_config(self, virtual_id: str, effect_type: str, config: dict) -> None:
        await self._request(
            "PUT", f"/virtuals/{virtual_id}/effects", {"type": effect_type, "config": config}
        )

    # --- push -------------------------------------------------------------

    async def listen(self, events: Iterable[str], on_event: Callable[[str], None]) -> None:
        """Connect to the websocket, subscribe to events and call on_event until closed.

        Raises LedFxError when the connection drops so the caller can reconnect.
        """
        try:
            async with self._session.ws_connect(
                f"{self.base_url}/api/websocket", heartbeat=30
            ) as ws:
                for i, event in enumerate(events, start=1):
                    await ws.send_json({"id": i, "type": "subscribe_event", "event_type": event})
                async for msg in ws:
                    if msg.type != aiohttp.WSMsgType.TEXT:
                        if msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                            break
                        continue
                    try:
                        data = msg.json()
                    except ValueError:
                        continue
                    if data.get("type") == "event":
                        on_event(data.get("event_type", ""))
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise LedFxError(f"websocket error: {err}") from err
        raise LedFxError("websocket closed")
