from fastapi.testclient import TestClient

from qq_adapter_service.router.router import create_router
from qq_adapter_service.services.connection_state import NapcatConnectionState


class StubAdapterService:
    def build_send_message_action(self, session_id, content):
        if session_id == "bad":
            raise ValueError("bad session")
        return type("Action", (), {"action": "send_private_msg", "params": {"user_id": 1, "message": content}})()

    def build_get_user_info_action(self, abstract_user_id):
        if abstract_user_id == "bad":
            raise ValueError("bad user")
        return type("Action", (), {"action": "get_stranger_info", "params": {"user_id": 9}})()


class StubGateway:
    async def handle_connection(self, websocket):
        return None

    async def send_action(self, websocket, action, params):
        if action == "timeout":
            raise TimeoutError("timeout")
        return {"status": "ok", "retcode": 0, "data": {"message_id": 88, "action": action, "params": params}}


def build_client(service: StubAdapterService, gateway: StubGateway, state: NapcatConnectionState) -> TestClient:
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(
        create_router(
            adapter_service=service,
            napcat_ws_gateway=gateway,
            napcat_connection_state=state,
        )
    )
    return TestClient(app)


def test_healthz() -> None:
    client = build_client(StubAdapterService(), StubGateway(), NapcatConnectionState())
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_send_message_requires_ws_connection() -> None:
    client = build_client(StubAdapterService(), StubGateway(), NapcatConnectionState())
    response = client.post("/api/v1/message/send", json={"session_id": "private_1", "content": "x"})
    assert response.status_code == 503


def test_send_message_validation() -> None:
    state = NapcatConnectionState()
    state.set(object())  # type: ignore[arg-type]
    client = build_client(StubAdapterService(), StubGateway(), state)
    response = client.post("/api/v1/message/send", json={"session_id": "bad", "content": "x"})
    assert response.status_code == 422


def test_get_user_info_requires_ws_connection() -> None:
    client = build_client(StubAdapterService(), StubGateway(), NapcatConnectionState())
    response = client.get("/api/v1/user/qq_1/info")
    assert response.status_code == 503


def test_get_user_info_validation() -> None:
    state = NapcatConnectionState()
    state.set(object())  # type: ignore[arg-type]
    client = build_client(StubAdapterService(), StubGateway(), state)
    response = client.get("/api/v1/user/bad/info")
    assert response.status_code == 422
