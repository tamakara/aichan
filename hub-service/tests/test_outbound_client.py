import asyncio

import pytest

from hub_service.services.outbound_client import OutboundClient


class DummyResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code
        self.text = str(payload)

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


class StubRedisStream:
    def __init__(self) -> None:
        self.actions: list[tuple[str, str]] = []

    async def enqueue_send_message(self, session_id: str, content: str) -> None:
        self.actions.append((session_id, content))


def test_call_agent_and_enqueue_action_success() -> None:
    redis_stream = StubRedisStream()
    client = OutboundClient(
        agent_service_url="http://agent-service:8000",
        redis_stream=redis_stream,  # type: ignore[arg-type]
    )
    client._client = DummyHttpClient([DummyResponse({"reply": "ok"})])  # type: ignore[attr-defined]

    reply = asyncio.run(client.call_agent("private_1", "hello"))
    assert reply == "ok"

    asyncio.run(client.send_reply("private_1", "ok"))
    assert redis_stream.actions == [("private_1", "ok")]


def test_call_agent_invalid_response_raises() -> None:
    redis_stream = StubRedisStream()
    client = OutboundClient(
        agent_service_url="http://agent-service:8000",
        redis_stream=redis_stream,  # type: ignore[arg-type]
    )
    client._client = DummyHttpClient([DummyResponse({"bad": "shape"})])  # type: ignore[attr-defined]

    with pytest.raises(Exception):
        asyncio.run(client.call_agent("private_1", "hello"))
