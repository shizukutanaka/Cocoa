from __future__ import annotations

import asyncio
import base64
import hashlib
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, Optional

import aiohttp

from .interfaces import StreamingController
from .models import ConnectionParams, ControllerStatus, SceneInfo, SourceInfo
import contextlib


class OBSController(StreamingController):
    def __init__(self, params: ConnectionParams) -> None:
        super().__init__(params)
        self._session: Optional[aiohttp.ClientSession] = None
        self._ws: Optional[aiohttp.ClientWebSocketResponse] = None
        self._listener: Optional[asyncio.Task] = None
        self._status = ControllerStatus(connected=False)
        self._request_id = 0
        self._pending: Dict[str, asyncio.Future] = {}
        self._lock = asyncio.Lock()

    async def connect(self) -> None:
        await self.disconnect()
        scheme = "wss" if self.params.use_ssl else "ws"
        url = f"{scheme}://{self.params.host}:{self.params.port}"
        self._session = aiohttp.ClientSession()
        try:
            self._ws = await self._session.ws_connect(url, heartbeat=self.params.heartbeat_interval)
            hello = await asyncio.wait_for(self._ws.receive_json(), timeout=self.params.request_timeout)
            if hello.get("op") != 0:
                raise RuntimeError("Unexpected handshake from OBS")
            await self._perform_identify(hello)
            self._status.connected = True
            self._status.last_error = None
            self._status.last_heartbeat = datetime.now(timezone.utc)
            self._listener = asyncio.create_task(self._reader())
        except Exception:
            await self.disconnect()
            raise

    async def disconnect(self) -> None:
        if self._listener:
            self._listener.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._listener
            self._listener = None
        if self._ws:
            await self._ws.close()
            self._ws = None
        if self._session:
            await self._session.close()
            self._session = None
        for fut in list(self._pending.values()):
            if not fut.done():
                fut.set_exception(RuntimeError("Connection closed"))
        self._pending.clear()
        self._status.connected = False

    async def status(self) -> ControllerStatus:
        return ControllerStatus(
            connected=self._status.connected,
            latency_ms=self._status.latency_ms,
            last_error=self._status.last_error,
            last_heartbeat=self._status.last_heartbeat,
        )

    async def list_scenes(self) -> Iterable[SceneInfo]:
        response = await self._send_request("GetSceneList")
        payload = response.get("responseData", {})
        active = payload.get("currentProgramSceneName")
        scenes_data = payload.get("scenes", [])
        results = []
        for scene in scenes_data:
            name = scene.get("sceneName", "")
            sources = [
                SourceInfo(
                    name=item.get("sourceName", ""),
                    enabled=item.get("sceneItemEnabled", False),
                    kind=item.get("inputKind"),
                )
                for item in scene.get("sources", [])
            ]
            results.append(SceneInfo(name=name, is_active=name == active, sources=sources))
        return results

    async def switch_scene(self, scene_name: str) -> None:
        await self._send_request("SetCurrentProgramScene", sceneName=scene_name)

    async def list_sources(self, scene_name: str) -> Iterable[SourceInfo]:
        response = await self._send_request("GetSceneItemList", sceneName=scene_name)
        items = response.get("responseData", {}).get("sceneItems", [])
        results = []
        for item in items:
            results.append(
                SourceInfo(
                    name=item.get("sourceName", ""),
                    enabled=item.get("sceneItemEnabled", False),
                    kind=item.get("inputKind"),
                    group=item.get("sourceType"),
                )
            )
        return results

    async def set_source_enabled(self, scene_name: str, source_name: str, enabled: bool) -> None:
        scene_item_id = await self._resolve_scene_item(scene_name, source_name)
        if scene_item_id is None:
            raise ValueError(f"Source not found: {scene_name}/{source_name}")
        await self._send_request(
            "SetSceneItemEnabled",
            sceneName=scene_name,
            sceneItemId=scene_item_id,
            sceneItemEnabled=enabled,
        )

    async def _perform_identify(self, hello: Dict[str, Any]) -> None:
        identify: Dict[str, Any] = {
            "op": 1,
            "d": {
                "rpcVersion": 1,
                "eventSubscriptions": 0,
            },
        }
        auth = hello.get("d", {}).get("authentication")
        if auth:
            if not self.params.password:
                raise RuntimeError("OBS WebSocket requires a password")
            identify["d"]["authentication"] = self._compute_auth(auth)
        await self._ws.send_json(identify)
        identified = await asyncio.wait_for(self._ws.receive_json(), timeout=self.params.request_timeout)
        if identified.get("op") != 2:
            raise RuntimeError("Failed to identify with OBS")

    def _compute_auth(self, auth: Dict[str, str]) -> str:
        password = self.params.password or ""
        salt = auth.get("salt", "")
        challenge = auth.get("challenge", "")
        secret = hashlib.sha256((password + salt).encode("utf-8")).digest()
        secret_b64 = base64.b64encode(secret).decode("utf-8")
        auth_response = hashlib.sha256((secret_b64 + challenge).encode("utf-8")).digest()
        return base64.b64encode(auth_response).decode("utf-8")

    async def _reader(self) -> None:
        assert self._ws is not None
        try:
            async for msg in self._ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    data = msg.json()
                    op = data.get("op")
                    if op == 7:
                        await self._handle_response(data.get("d", {}))
                    elif op == 8:
                        self._status.last_heartbeat = datetime.now(timezone.utc)
                        metrics = data.get("d", {}).get("measurements", {})
                        duration = metrics.get("wsOpTime")
                        if duration is not None:
                            self._status.latency_ms = float(duration)
                    else:
                        continue
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    raise msg.data
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            self._status.last_error = str(exc)
        finally:
            self._status.connected = False
            self._cancel_pending_futures()

    def _cancel_pending_futures(self) -> None:
        for fut in list(self._pending.values()):
            if not fut.done():
                fut.set_exception(RuntimeError("Connection closed"))
        self._pending.clear()

    async def _handle_response(self, payload: Dict[str, Any]) -> None:
        request_id = payload.get("requestId")
        if request_id is None:
            return
        future = self._pending.pop(request_id, None)
        if future is None:
            return
        status = payload.get("requestStatus", {})
        if status.get("result", False):
            future.set_result(payload)
        else:
            future.set_exception(RuntimeError(status.get("comment", "OBS request failed")))

    async def _send_request(self, request_type: str, **request_data: Any) -> Dict[str, Any]:
        if not self._ws:
            raise RuntimeError("OBS controller is not connected")
        async with self._lock:
            self._request_id += 1
            request_id = str(self._request_id)
        future: asyncio.Future = asyncio.get_running_loop().create_future()
        self._pending[request_id] = future
        payload = {
            "op": 6,
            "d": {
                "requestType": request_type,
                "requestId": request_id,
                "requestData": request_data,
            },
        }
        await self._ws.send_json(payload)
        return await asyncio.wait_for(future, timeout=self.params.request_timeout)

    async def _resolve_scene_item(self, scene_name: str, source_name: str) -> Optional[int]:
        response = await self._send_request("GetSceneItemList", sceneName=scene_name)
        for item in response.get("responseData", {}).get("sceneItems", []):
            if item.get("sourceName") == source_name:
                return item.get("sceneItemId")
        return None
