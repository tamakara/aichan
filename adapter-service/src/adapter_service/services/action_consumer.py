from __future__ import annotations

import asyncio
import logging

from pydantic import ValidationError

from .adapter_service import AdapterService
from .connection_state import NapcatConnectionState
from .errors import NapcatDownstreamError
from .napcat_ws_gateway import NapcatWsGateway
from .redis_stream import AdapterRedisStream
from .stream_models import ActionStreamMessage


class ActionConsumerWorker:
    def __init__(
        self,
        redis_stream: AdapterRedisStream,
        napcat_gateway: NapcatWsGateway,
        napcat_connection_state: NapcatConnectionState,
        adapter_service: AdapterService,
    ) -> None:
        self._logger = logging.getLogger(__name__)
        self._redis_stream = redis_stream
        self._napcat_gateway = napcat_gateway
        self._napcat_connection_state = napcat_connection_state
        self._adapter_service = adapter_service
        self._task: asyncio.Task[None] | None = None
        self._stopping = False

    async def start(self) -> None:
        self._stopping = False
        self._task = asyncio.create_task(self._run_loop(), name="adapter-action-consumer")

    async def stop(self) -> None:
        self._stopping = True
        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None

    async def _run_loop(self) -> None:
        while not self._stopping:
            pending = await self._redis_stream.read_pending_actions(count=10)
            if pending:
                await self._handle_batch(pending)
                continue

            fresh = await self._redis_stream.read_new_actions(count=10)
            if fresh:
                await self._handle_batch(fresh)

    async def _handle_batch(self, messages: list[tuple[str, dict[str, str]]]) -> None:
        for message_id, fields in messages:
            try:
                action = ActionStreamMessage.from_stream_fields(fields)
                await self._handle_action(action)
            except ValidationError:
                # 非法消息直接 ACK，避免毒消息卡死整个消费分组。
                self._logger.exception("invalid action stream message, drop: id=%s", message_id)
                await self._redis_stream.ack_action(message_id)
            except ValueError:
                # session_id 或动作参数不合法属于不可恢复输入错误，直接丢弃。
                self._logger.exception("invalid action payload, drop: id=%s", message_id)
                await self._redis_stream.ack_action(message_id)
            except Exception:
                # 运行期故障按未 ACK 留在 PEL，下一轮优先重试，保证至少一次投递。
                self._logger.exception("action handle failed, will retry: id=%s", message_id)
                await asyncio.sleep(1)
                continue
            await self._redis_stream.ack_action(message_id)

    async def _handle_action(self, action: ActionStreamMessage) -> None:
        if action.action_type != "send_message":
            self._logger.warning("unknown action_type=%s, skip", action.action_type)
            return

        websocket = self._napcat_connection_state.get()
        if websocket is None:
            raise RuntimeError("onebot reverse ws is not connected")

        outbound_action = self._adapter_service.build_send_message_action(
            session_id=action.session_id,
            content=action.payload.content,
        )
        result = await self._napcat_gateway.send_action(
            websocket=websocket,
            action=outbound_action.action,
            params=outbound_action.params,
        )
        if result.get("status") != "ok":
            raise NapcatDownstreamError(f"onebot action failed: {result}")
