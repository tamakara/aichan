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
        adapter_api_url=settings.hub.adapter_url,
    )
    hub_pipeline_service = HubPipelineService(
        reminder_service=reminder_service,
        outbound_service=outbound_client,
    )

    app = FastAPI(
        title="hub-service",
        version="0.1.0",
        description="QQ reminder hub for triggering agent and replying via adapter.",
    )

    app.include_router(create_router(hub_pipeline_service=hub_pipeline_service))

    @app.on_event("shutdown")
    async def shutdown() -> None:
        await outbound_client.aclose()

    return app


app = create_app()
