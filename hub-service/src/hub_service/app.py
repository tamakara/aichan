from fastapi import FastAPI

from .config import get_settings
from .router import create_router
from .services.outbound_client import OutboundClient
from .services.reminder_service import HubPipelineService, ReminderService


def create_app() -> FastAPI:
    settings = get_settings()

    reminder_service = ReminderService()
    outbound_client = OutboundClient(
        agent_service_url=settings.hub.agent_url,
        qq_adapter_api_url=settings.hub.qq_adapter_url,
        agent_max_turns=settings.hub.max_turns,
    )
    hub_pipeline_service = HubPipelineService(
        reminder_service=reminder_service,
        outbound_service=outbound_client,
    )

    app = FastAPI(
        title="hub-service",
        version="0.1.0",
        description="QQ reminder hub for triggering agent and replying via qq-adapter.",
    )

    app.include_router(create_router(hub_pipeline_service=hub_pipeline_service))

    @app.on_event("shutdown")
    async def shutdown() -> None:
        await outbound_client.aclose()

    return app


app = create_app()
