from __future__ import annotations

import logging
from datetime import datetime, timezone
from threading import Lock

from .errors import DownstreamCallError
from ..router.schemas import ReminderItem


class ReminderService:
    def __init__(self) -> None:
        self._logger = logging.getLogger(__name__)
        self._lock = Lock()
        self._reminders_by_user: dict[str, list[ReminderItem]] = {}

    def add_reminder(self, user_id: str, session_id: str, content: str, raw_event: dict) -> ReminderItem:
        # 这里按 user_id 分桶保存提醒，是为了把后续基于用户的策略扩展
        # （例如限流、优先级、摘要）限制在单用户维度，避免跨用户状态污染。
        item = ReminderItem(
            user_id=user_id,
            session_id=session_id,
            content=content,
            created_at=datetime.now(timezone.utc),
            raw_event=raw_event,
        )
        with self._lock:
            self._reminders_by_user.setdefault(user_id, []).append(item)
        return item

    def list_reminders(self, user_id: str) -> list[ReminderItem]:
        with self._lock:
            return list(self._reminders_by_user.get(user_id, []))


class HubPipelineService:
    def __init__(self, reminder_service: ReminderService, outbound_service: OutboundServiceProtocol) -> None:
        self._logger = logging.getLogger(__name__)
        self._reminder_service = reminder_service
        self._outbound_service = outbound_service

    async def handle_private_event(self, user_id: str, session_id: str, content: str, raw_event: dict) -> None:
        self._reminder_service.add_reminder(
            user_id=user_id,
            session_id=session_id,
            content=content,
            raw_event=raw_event,
        )

        try:
            reply = await self._outbound_service.call_agent(user_message=content)
        except DownstreamCallError:
            self._logger.exception(
                "hub stage=agent user_id=%s session_id=%s", user_id, session_id
            )
            return

        try:
            await self._outbound_service.send_reply(session_id=session_id, content=reply)
        except DownstreamCallError:
            self._logger.exception(
                "hub stage=reply user_id=%s session_id=%s", user_id, session_id
            )
            return


class OutboundServiceProtocol:
    async def call_agent(self, user_message: str) -> str:  # pragma: no cover
        raise NotImplementedError

    async def send_reply(self, session_id: str, content: str) -> None:  # pragma: no cover
        raise NotImplementedError
