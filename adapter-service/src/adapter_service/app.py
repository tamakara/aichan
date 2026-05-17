from fastapi import FastAPI

from .config import get_settings
from .router.router import create_router
from .services.action_consumer import ActionConsumerWorker
from .services.adapter_service import AdapterService
from .services.connection_state import NapcatConnectionState
from .services.napcat_ws_gateway import NapcatWsGateway
from .services.redis_stream import AdapterRedisStream


def create_app() -> FastAPI:
    settings = get_settings()

    redis_stream = AdapterRedisStream(settings.redis)
    adapter_service = AdapterService()
    napcat_connection_state = NapcatConnectionState()
    napcat_ws_gateway = NapcatWsGateway(
        adapter_service=adapter_service,
        redis_stream=redis_stream,
        action_timeout_seconds=settings.adapter.onebot_ws_action_timeout_seconds,
    )
    action_consumer = ActionConsumerWorker(
        redis_stream=redis_stream,
        napcat_gateway=napcat_ws_gateway,
        napcat_connection_state=napcat_connection_state,
        adapter_service=adapter_service,
    )

    app = FastAPI(
        title="adapter-service",
        version="0.1.0",
        description="Redis-stream QQ adapter for NapCat OneBot v11 and hub module.",
    )

    app.include_router(
        create_router(
            adapter_service=adapter_service,
            napcat_ws_gateway=napcat_ws_gateway,
            napcat_connection_state=napcat_connection_state,
        )
    )

    @app.on_event("startup")
    async def startup() -> None:
        await redis_stream.startup()
        await action_consumer.start()

    @app.on_event("shutdown")
    async def shutdown() -> None:
        await action_consumer.stop()
        await redis_stream.shutdown()

    return app


app = create_app()
