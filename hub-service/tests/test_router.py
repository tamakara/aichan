from fastapi.testclient import TestClient

from hub_service.router.router import create_router


class StubHubPipelineService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, str]] = []

    async def handle_private_event(self, user_id: str, session_id: str, content: str, raw_event: dict) -> None:
        self.calls.append((user_id, session_id, content))


def build_client(service: StubHubPipelineService) -> TestClient:
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(create_router(hub_pipeline_service=service))
    return TestClient(app)


def test_healthz() -> None:
    client = build_client(StubHubPipelineService())
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_ws_private_event_triggers_pipeline() -> None:
    service = StubHubPipelineService()
    client = build_client(service)

    with client.websocket_connect("/qq/events") as ws:
        ws.send_json(
            {
                "session_id": "private_1",
                "user_id": "qq_1",
                "content": "hello",
                "source": "qq",
                "message_type": "private",
                "raw_event": {"k": 1},
            }
        )

    assert service.calls == [("qq_1", "private_1", "hello")]


def test_ws_group_event_is_ignored() -> None:
    service = StubHubPipelineService()
    client = build_client(service)

    with client.websocket_connect("/qq/events") as ws:
        ws.send_json(
            {
                "session_id": "group_1",
                "user_id": "qq_1",
                "content": "hello",
                "source": "qq",
                "message_type": "group",
                "raw_event": {"k": 1},
            }
        )

    assert service.calls == []


def test_ws_bad_payload_is_ignored() -> None:
    service = StubHubPipelineService()
    client = build_client(service)

    with client.websocket_connect("/qq/events") as ws:
        ws.send_json({"foo": "bar"})

    assert service.calls == []
