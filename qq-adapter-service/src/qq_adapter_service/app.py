from fastapi import FastAPI

from .config import get_settings
from .router.router import create_router
from .services.connection_state import NapcatConnectionState
from .services.downstream_ws_client import DownstreamWsClient
from .services.adapter_service import AdapterService
from .services.napcat_ws_gateway import NapcatWsGateway


def create_app() -> FastAPI:
    settings = get_settings()

    downstream_ws_client = DownstreamWsClient(
        ws_url=settings.adapter.downstream_ws_url,
        ws_token=settings.adapter.downstream_ws_token,
        open_timeout_seconds=settings.adapter.downstream_ws_open_timeout_seconds,
        reconnect_interval_seconds=settings.adapter.downstream_ws_reconnect_interval_seconds,
    )
    adapter_service = AdapterService()
    napcat_ws_gateway = NapcatWsGateway(
        adapter_service=adapter_service,
        downstream_ws_client=downstream_ws_client,
        action_timeout_seconds=settings.adapter.onebot_ws_action_timeout_seconds,
    )
    napcat_connection_state = NapcatConnectionState()


    app = FastAPI(
        title="qq-adapter-service",
        version="0.1.0",
        description="WebSocket bridge filter for NapCat OneBot v11 and downstream module.",
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
        await downstream_ws_client.start()

    @app.on_event("shutdown")
    async def shutdown() -> None:
        await downstream_ws_client.stop()

    return app


app = create_app()
