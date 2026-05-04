from threading import Lock

from fastapi import FastAPI

from .agent import AgentCore, MessagesStorage
from .config import get_settings
from .prompts import SYSTEM_PROMPT
from .router import create_router

settings = get_settings()

messages_storage = MessagesStorage()
messages_storage.add_system_message(SYSTEM_PROMPT)

agent = AgentCore(
    model_name=settings.model_name,
    openai_api_key=settings.openai_api_key,
    openai_base_url=settings.openai_base_url,
    messages_storage=messages_storage,
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
