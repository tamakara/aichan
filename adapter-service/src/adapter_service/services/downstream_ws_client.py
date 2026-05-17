from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from typing import Any

from websockets.asyncio.client import ClientConnection, connect
from websockets.exceptions import ConnectionClosed


class DownstreamWsClient:
    def __init__(
        self,
        ws_url: str,
        ws_token: str,
        open_timeout_seconds: float,
        reconnect_interval_seconds: float,
    ) -> None:
        self._ws_url = ws_url
        self._ws_token = ws_token
        self._open_timeout_seconds = open_timeout_seconds
        self._reconnect_interval_seconds = reconnect_interval_seconds
        self._logger = logging.getLogger(__name__)

        self._connection: ClientConnection | None = None
        self._connect_task: asyncio.Task[None] | None = None
        self._lock = asyncio.Lock()
        self._closed = False

    async def start(self) -> None:
        self._closed = False
        if self._connect_task is None or self._connect_task.done():
            self._connect_task = asyncio.create_task(self._connect_loop())

    async def stop(self) -> None:
        self._closed = True

        if self._connect_task is not None:
            self._connect_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._connect_task
            self._connect_task = None

        async with self._lock:
            if self._connection is not None:
                await self._connection.close()
                self._connection = None

    async def publish_event(self, payload: dict[str, Any]) -> bool:
        text = json.dumps(payload, ensure_ascii=False)

        async with self._lock:
            conn = self._connection
            if conn is None:
                return False

            try:
                await conn.send(text)
                return True
            except ConnectionClosed:
                self._connection = None
                self._logger.warning("downstream ws disconnected while sending event")
                return False
            except Exception:
                self._connection = None
                self._logger.exception("failed to send event to downstream ws")
                return False

    async def _connect_loop(self) -> None:
        headers = None
        if self._ws_token:
            headers = {"Authorization": f"Bearer {self._ws_token}"}

        while not self._closed:
            try:
                async with connect(
                    self._ws_url,
                    additional_headers=headers,
                    open_timeout=self._open_timeout_seconds,
                ) as conn:
                    self._logger.info("connected to downstream ws: %s", self._ws_url)
                    async with self._lock:
                        self._connection = conn

                    try:
                        # 业务只需要单向推送给下游，这里消费下游消息是为了维持连接并感知断链。
                        async for _ in conn:
                            pass
                    finally:
                        async with self._lock:
                            if self._connection is conn:
                                self._connection = None

            except asyncio.CancelledError:
                raise
            except Exception:
                self._logger.exception("downstream ws connect failed, will retry")

            if not self._closed:
                await asyncio.sleep(self._reconnect_interval_seconds)
