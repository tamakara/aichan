from fastapi import APIRouter

from .schemas import HealthResponse


def create_router() -> APIRouter:
    router = APIRouter()

    @router.get("/healthz", response_model=HealthResponse)
    async def healthz() -> HealthResponse:
        return HealthResponse()

    return router
