from __future__ import annotations

from typing import Any

import httpx

from ..router.schemas import AgentChatRequest, AgentChatResponse, SendMessageRequest, SendMessageResponse
from .errors import DownstreamCallError


class OutboundClient:
    def __init__(
        self,
        agent_service_url: str,
        qq_adapter_api_url: str,
        agent_max_turns: int,
        timeout_seconds: float,
    ) -> None:
        self._agent_service_url = agent_service_url.rstrip("/")
        self._qq_adapter_api_url = qq_adapter_api_url.rstrip("/")
        self._agent_max_turns = agent_max_turns
        self._client = httpx.AsyncClient(timeout=timeout_seconds)

    async def call_agent(self, user_message: str) -> str:
        payload = AgentChatRequest(user_message=user_message, max_turns=self._agent_max_turns)
        data = await self._post_json(f"{self._agent_service_url}/chat", payload.model_dump())

        try:
            response = AgentChatResponse.model_validate(data)
        except Exception as exc:
            raise DownstreamCallError(f"invalid agent response: {data}") from exc

        return response.reply

    async def send_reply(self, session_id: str, content: str) -> None:
        payload = SendMessageRequest(session_id=session_id, content=content)
        data = await self._post_json(f"{self._qq_adapter_api_url}/api/v1/message/send", payload.model_dump())

        try:
            parsed = SendMessageResponse.model_validate(data)
        except Exception as exc:
            raise DownstreamCallError(f"invalid qq-adapter response: {data}") from exc

        if not parsed.ok:
            raise DownstreamCallError(f"qq-adapter send failed: {data}")

    async def _post_json(self, url: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            response = await self._client.post(url, json=payload)
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise DownstreamCallError(f"timeout calling downstream: url={url}") from exc
        except httpx.HTTPStatusError as exc:
            raise DownstreamCallError(
                f"http error calling downstream: url={url} status={exc.response.status_code} body={exc.response.text}"
            ) from exc
        except httpx.HTTPError as exc:
            raise DownstreamCallError(f"request failed calling downstream: url={url} err={exc}") from exc

        try:
            data = response.json()
        except ValueError as exc:
            raise DownstreamCallError(f"downstream response is not json: url={url}") from exc

        if not isinstance(data, dict):
            raise DownstreamCallError(f"downstream json is not object: url={url}")

        return data

    async def aclose(self) -> None:
        await self._client.aclose()
