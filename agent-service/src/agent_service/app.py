from threading import Lock

from fastapi import FastAPI

from .agent import AgentCore
from .config import get_settings
from .prompts import SYSTEM_PROMPT
from .router import create_router

settings = get_settings()

agent = AgentCore(
    llm_model_name=settings.llm_model_name,
    llm_api_key=settings.llm_api_key,
    llm_base_url=settings.llm_base_url,
    system_prompt=SYSTEM_PROMPT,
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
