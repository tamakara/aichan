from __future__ import annotations

from typing import Any

import httpx

from ..router.schemas import AgentChatRequest, AgentChatResponse
from .redis_stream import HubRedisStream


class OutboundClient:
    def __init__(
        self,
        agent_service_url: str,
        redis_stream: HubRedisStream,
    ) -> None:
        self._agent_service_url = agent_service_url.rstrip("/")
        self._redis_stream = redis_stream
        self._client = httpx.AsyncClient(timeout=None)

    async def call_agent(self, session_id: str, user_message: str) -> str:
        payload = AgentChatRequest(
            session_id=session_id,
            user_message=user_message,
        )
        data = await self._post_json(f"{self._agent_service_url}/chat", payload.model_dump())
        response = AgentChatResponse.model_validate(data)
        return response.reply

    async def send_reply(self, session_id: str, content: str) -> None:
        await self._redis_stream.enqueue_send_message(session_id=session_id, content=content)

    async def _post_json(self, url: str, payload: dict[str, Any]) -> dict[str, Any]:
        response = await self._client.post(url, json=payload)
        if response.status_code >= 400:
            # 下游非 2xx 时保留响应体，避免只看到状态码而丢失关键错误上下文。
            raise RuntimeError(
                f"downstream http error: url={url} status={response.status_code} body={response.text}"
            )
        data = response.json()

        if not isinstance(data, dict):
            raise ValueError(f"downstream json is not object: url={url}")

        return data

    async def aclose(self) -> None:
        await self._client.aclose()
