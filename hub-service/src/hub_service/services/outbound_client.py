from __future__ import annotations

from typing import Any

import httpx

from ..router.schemas import AgentChatRequest, AgentChatResponse, SendMessageRequest, SendMessageResponse


class OutboundClient:
    def __init__(
        self,
        agent_service_url: str,
        qq_adapter_api_url: str,
        agent_max_turns: int,
    ) -> None:
        self._agent_service_url = agent_service_url.rstrip("/")
        self._qq_adapter_api_url = qq_adapter_api_url.rstrip("/")
        self._agent_max_turns = agent_max_turns
        self._client = httpx.AsyncClient(timeout=None)

    async def call_agent(self, user_message: str) -> str:
        payload = AgentChatRequest(user_message=user_message, max_turns=self._agent_max_turns)
        data = await self._post_json(f"{self._agent_service_url}/chat", payload.model_dump())
        response = AgentChatResponse.model_validate(data)
        return response.reply

    async def send_reply(self, session_id: str, content: str) -> None:
        payload = SendMessageRequest(session_id=session_id, content=content)
        data = await self._post_json(f"{self._qq_adapter_api_url}/api/v1/message/send", payload.model_dump())
        parsed = SendMessageResponse.model_validate(data)
        if not parsed.ok:
            raise ValueError("qq-adapter send returned ok=false")

    async def _post_json(self, url: str, payload: dict[str, Any]) -> dict[str, Any]:
        response = await self._client.post(url, json=payload)
        response.raise_for_status()
        data = response.json()

        if not isinstance(data, dict):
            raise ValueError(f"downstream json is not object: url={url}")

        return data

    async def aclose(self) -> None:
        await self._client.aclose()
