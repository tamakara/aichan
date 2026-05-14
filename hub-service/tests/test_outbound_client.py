import asyncio

import pytest

from hub_service.services.outbound_client import OutboundClient


class DummyResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code
        self.text = str(payload)

    def raise_for_status(self):
        if self.status_code >= 400:
            from httpx import HTTPStatusError, Request

            raise HTTPStatusError(
                message="bad status",
                request=Request("POST", "http://dummy"),
                response=self,
            )

    def json(self):
        return self._payload


class DummyHttpClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    async def post(self, url, json):
        self.calls.append((url, json))
        return self.responses.pop(0)

    async def aclose(self):
        return None


def test_call_agent_and_send_reply_success() -> None:
    client = OutboundClient(
        agent_service_url="http://agent-service:8000",
        qq_adapter_api_url="http://qq-adapter-service:8010",
        agent_max_turns=10,
    )
    client._client = DummyHttpClient(
        [
            DummyResponse({"reply": "ok"}),
            DummyResponse({"ok": True, "data": {"message_id": 1}}),
        ]
    )  # type: ignore[attr-defined]

    reply = asyncio.run(client.call_agent("hello"))
    assert reply == "ok"

    asyncio.run(client.send_reply("private_1", "ok"))


def test_call_agent_invalid_response_raises() -> None:
    client = OutboundClient(
        agent_service_url="http://agent-service:8000",
        qq_adapter_api_url="http://qq-adapter-service:8010",
        agent_max_turns=10,
    )
    client._client = DummyHttpClient([DummyResponse({"bad": "shape"})])  # type: ignore[attr-defined]

    with pytest.raises(Exception):
        asyncio.run(client.call_agent("hello"))
