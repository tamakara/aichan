from fastapi import FastAPI

from .config import get_settings
from .router import create_router
from .services import EventConsumerWorker, HubRedisStream, OutboundClient, SessionCoordinator


def create_app() -> FastAPI:
    settings = get_settings()

    redis_stream = HubRedisStream(settings.redis)
    outbound_client = OutboundClient(
        agent_service_url=settings.hub.agent_url,
        redis_stream=redis_stream,
    )
    session_coordinator = SessionCoordinator(
        outbound_client=outbound_client,
        debounce_seconds=settings.hub.debounce_seconds,
    )
    event_consumer = EventConsumerWorker(
        redis_stream=redis_stream,
        session_coordinator=session_coordinator,
    )

    app = FastAPI(
        title="hub-service",
        version="0.1.0",
        description="QQ reminder hub driven by Redis streams.",
    )

    app.include_router(create_router())

    @app.on_event("startup")
    async def startup() -> None:
        await redis_stream.startup()
        await event_consumer.start()

    @app.on_event("shutdown")
    async def shutdown() -> None:
        await event_consumer.stop()
        await session_coordinator.shutdown()
        await outbound_client.aclose()
        await redis_stream.shutdown()

    return app


app = create_app()
