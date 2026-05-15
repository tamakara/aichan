from threading import Lock

from fastapi import FastAPI

from .services import AgentCore, LlmClient, McpGateway, Session
from .services.prompts import SYSTEM_PROMPT
from .config import get_settings
from .router import create_router


def create_app() -> FastAPI:
    settings = get_settings()

    llm_client = LlmClient(
        model_name=settings.agent.model,
        api_key=settings.agent.openai_api_key,
        base_url=settings.agent.openai_base_url,
    )

    session_contexts: dict[str, tuple[Session, Lock]] = {}
    session_registry_lock = Lock()

    mcp_gateway = McpGateway(
        sse_url=settings.agent.mcp_sse_url,
        auth_token=settings.agent.mcp_auth_token,
    )
    mcp_gateway.register_mcp_server()

    agent = AgentCore(
        llm_client=llm_client,
        mcp_gateway=mcp_gateway,
        max_turns=settings.agent.max_turns,
    )

    app = FastAPI(
        title="agent-service FastAPI service",
        version="0.1.0",
        description="HTTP API wrapper around AgentCore.",
    )
    app.include_router(
        create_router(
            agent=agent,
            session_contexts=session_contexts,
            registry_lock=session_registry_lock,
        )
    )

    return app


app = create_app()
