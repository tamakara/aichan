from __future__ import annotations

import asyncio
import uuid
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect

from .adapter_service import AdapterService
from .downstream_ws_client import DownstreamWsClient


class NapcatWsGateway:
    def __init__(
        self,
        adapter_service: AdapterService,
        downstream_ws_client: DownstreamWsClient,
        action_timeout_seconds: float,
    ) -> None:
        self._adapter_service = adapter_service
        self._downstream_ws_client = downstream_ws_client
        self._action_timeout_seconds = action_timeout_seconds
        self._pending_actions: dict[str, asyncio.Future[dict[str, Any]]] = {}
        self._pending_lock = asyncio.Lock()

    async def handle_connection(self, websocket: WebSocket) -> None:
        await websocket.accept()

        try:
            while True:
                message = await websocket.receive_json()
                if not isinstance(message, dict):
                    continue

                if self._is_event(message):
                    await self._handle_event(message)
                    continue

                if self._is_action_response(message):
                    await self._resolve_action(message)
                    continue
        except WebSocketDisconnect:
            return

    async def send_action(self, websocket: WebSocket, action: str, params: dict[str, Any]) -> dict[str, Any]:
        echo = str(uuid.uuid4())
        request = {
            "action": action,
            "params": params,
            "echo": echo,
        }

        future: asyncio.Future[dict[str, Any]] = asyncio.get_running_loop().create_future()

        async with self._pending_lock:
            self._pending_actions[echo] = future

        try:
            await websocket.send_json(request)
            return await asyncio.wait_for(future, timeout=self._action_timeout_seconds)
        finally:
            async with self._pending_lock:
                self._pending_actions.pop(echo, None)

    async def _handle_event(self, raw_event: dict[str, Any]) -> None:
        clean_result = self._adapter_service.clean_event(raw_event)
        if not clean_result.accepted:
            return

        assert clean_result.payload is not None
        await self._downstream_ws_client.publish_event(clean_result.payload.model_dump())

    async def _resolve_action(self, response: dict[str, Any]) -> None:
        echo = str(response.get("echo", ""))
        if not echo:
            return

        async with self._pending_lock:
            future = self._pending_actions.get(echo)

        if future is not None and not future.done():
            future.set_result(response)

    @staticmethod
    def _is_event(message: dict[str, Any]) -> bool:
        return "post_type" in message

    @staticmethod
    def _is_action_response(message: dict[str, Any]) -> bool:
        return "echo" in message and "status" in message and "retcode" in message
