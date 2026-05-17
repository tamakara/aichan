from fastapi.testclient import TestClient

from hub_service.router.router import create_router


def build_client() -> TestClient:
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(create_router())
    return TestClient(app)


def test_healthz() -> None:
    client = build_client()
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
