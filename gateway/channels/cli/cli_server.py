from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field

CLIChannelIdentity = Literal["ai", "user"]

# SSE 业务等待超时时间（秒）
CLI_SERVER_SSE_WAIT_TIMEOUT_SECONDS = 1.0


class SendMessageRequest(BaseModel):
    """客户端请求发送消息的载荷"""

    sender: CLIChannelIdentity
    text: str = Field(..., min_length=1)


class ChatMessage(BaseModel):
    """统一的聊天消息数据结构"""

    id: int = Field(..., ge=1)
    sender: CLIChannelIdentity
    text: str
    created_at: str


class AsyncChatStore:
    """
    原生基于 asyncio 的最小内存消息存储。
    完全适配 FastAPI 的事件循环，杜绝线程阻塞问题。
    """

    def __init__(self) -> None:
        self._messages: list[ChatMessage] = []
        self._next_id = 1
        self._lock = asyncio.Lock()
        self._new_message_cond = asyncio.Condition(self._lock)

    async def list_messages(self, after_id: int = 0) -> list[ChatMessage]:
        """获取指定 ID 之后的所有历史消息"""
        async with self._lock:
            return self._collect_messages(after_id)

    async def wait_for_messages(
        self, after_id: int, timeout_seconds: float
    ) -> list[ChatMessage]:
        """
        挂起当前协程，等待新消息到达。
        结合 Condition 唤醒与超时机制，实现高效的 SSE 推送。
        """
        async with self._new_message_cond:
            messages = self._collect_messages(after_id)
            if not messages:
                try:
                    await asyncio.wait_for(
                        self._new_message_cond.wait(), timeout=timeout_seconds
                    )
                except asyncio.TimeoutError:
                    pass
                messages = self._collect_messages(after_id)
            return messages

    async def send_message(self, sender: CLIChannelIdentity, text: str) -> ChatMessage:
        """接收新消息，并通知所有正在等待的 SSE 客户端"""
        clean_text = text.strip()
        if not clean_text:
            raise ValueError("text 不能为空")

        async with self._lock:
            message = ChatMessage(
                id=self._next_id,
                sender=sender,
                text=clean_text,
                created_at=datetime.now(timezone.utc).isoformat(),
            )
            self._messages.append(message)
            self._next_id += 1
            self._new_message_cond.notify_all()

        return message

    def _collect_messages(self, after_id: int) -> list[ChatMessage]:
        """无锁状态下的消息过滤（调用方必须确保持有锁）"""
        return [msg for msg in self._messages if msg.id > after_id]


class CLIMessageService:
    """封装消息存储相关业务能力，供网关路由层调用。"""

    def __init__(self, store: AsyncChatStore | None = None) -> None:
        self._store = store or AsyncChatStore()

    async def list_messages(self, after_id: int = 0) -> list[ChatMessage]:
        return await self._store.list_messages(after_id=after_id)

    async def wait_incremental_messages(
        self,
        after_id: int,
        timeout_seconds: float = CLI_SERVER_SSE_WAIT_TIMEOUT_SECONDS,
    ) -> list[ChatMessage]:
        return await self._store.wait_for_messages(
            after_id=after_id,
            timeout_seconds=timeout_seconds,
        )

    async def save_message(self, payload: SendMessageRequest) -> ChatMessage:
        return await self._store.send_message(sender=payload.sender, text=payload.text)
