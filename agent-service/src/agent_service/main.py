from threading import Lock

import uvicorn
from fastapi import FastAPI

from .agent_core import AgentCore
from .api import create_router
from .config import get_settings, get_system_prompt

settings = get_settings()
system_prompt = get_system_prompt()
agent = AgentCore(
    llm_model_name=settings.llm_model_name,
    llm_api_key=settings.llm_api_key,
    llm_base_url=settings.llm_base_url,
    system_prompt=system_prompt,
    mcp_gateway_sse_url=settings.mcp_gateway_sse_url,
    mcp_gateway_auth_token=settings.mcp_gateway_auth_token,
)
agent_lock = Lock()

app = FastAPI(
    title="agent-service FastAPI service",
    version="0.1.0",
    description="HTTP API wrapper around AgentCore.",
)
app.include_router(create_router(agent=agent, agent_lock=agent_lock))


def run() -> None:
    uvicorn.run(
        "agent_service.main:app",
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level,
    )
