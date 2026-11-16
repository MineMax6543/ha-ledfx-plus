"""Minimal async client for the LedFx REST + websocket API.

Endpoints verified against LedFx `main` (ledfx/api/*.py).
"""

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
                data = await resp.json(content_type=None)
                if resp.status >= 400 and not isinstance(data, dict):
                    resp.raise_for_status()
        except (aiohttp.ClientError, TimeoutError, ValueError) as err:
            raise LedFxError(f"{method} {path} failed: {err}") from err
        if isinstance(data, dict) and data.get("status") == "failed":
            payload = data.get("payload") or {}
            reason = payload.get("reason") if isinstance(payload, dict) else payload
            raise LedFxError(str(reason or data))
        return data or {}

    # --- read -------------------------------------------------------------

    async def get_info(self) -> dict[str, Any]:
        return await self._request("GET", "/info")

    async def get_virtuals(self) -> dict[str, Any]:
        """{"virtuals": {id: {...}}, "paused": bool}"""
        return await self._request("GET", "/virtuals")

    async def get_scenes(self) -> dict[str, Any]:
        """{scene_id: {"name": ..., "active": bool, ...}}"""
        return (await self._request("GET", "/scenes")).get("scenes", {})

    async def get_audio_devices(self) -> dict[str, Any]:
        """{"active_device_index": int, "devices": {index: name}}"""
        return await self._request("GET", "/audio/devices")

    async def get_effect_types(self) -> dict[str, str]:
        """Return {effect_id: display_name}. Only requests the effects schema."""
        data = await self._request("GET", "/schema", "effects")
        effects = data.get("effects", {})
        return {eid: (e.get("name") or eid) for eid, e in effects.items()}

    # --- write ------------------------------------------------------------

    async def set_virtual_active(self, virtual_id: str, active: bool) -> None:
        await self._request("PUT", f"/virtuals/{virtual_id}", {"active": active})

    async def toggle_global_pause(self) -> None:
        """LedFx only offers a toggle (PUT /api/virtuals)."""
        await self._request("PUT", "/virtuals")

    async def set_effect(self, virtual_id: str, effect_type: str, config: dict | None = None) -> None:
        """Set a new effect. Without config, LedFx uses the effect's stored config."""
        body: dict[str, Any] = {"type": effect_type}
        if config:
            body["config"] = config
        await self._request("POST", f"/virtuals/{virtual_id}/effects", body)

    async def update_effect_config(self, virtual_id: str, config: dict) -> None:
        """Merge config into the active effect (PUT keeps the current type)."""
        await self._request("PUT", f"/virtuals/{virtual_id}/effects", {"config": config})

    async def activate_scene(self, scene_id: str) -> None:
        await self._request("PUT", "/scenes", {"id": scene_id, "action": "activate"})

    async def set_audio_device(self, index: int) -> None:
        await self._request("PUT", "/audio/devices", {"audio_device": index})

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
                    if msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                        break
                    if msg.type != aiohttp.WSMsgType.TEXT:
                        continue
                    try:
                        data = msg.json()
                    except ValueError:
                        continue
                    if isinstance(data, dict) and data.get("type") == "event":
                        on_event(data.get("event_type", ""))
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise LedFxError(f"websocket error: {err}") from err
        raise LedFxError("websocket closed")
