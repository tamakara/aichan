from threading import Lock

from fastapi import FastAPI

from .agent import AgentCore, LlmClient, McpGateway, MessageList
from .config import get_settings
from .prompts import SYSTEM_PROMPT
from .router import create_router

settings = get_settings()

llm_client = LlmClient(
    model_name=settings.model_name,
    api_key=settings.openai_api_key,
    base_url=settings.openai_base_url,
)

messages_list = MessageList()
messages_list.add_message(role="system", content=SYSTEM_PROMPT)

mcp_gateway = McpGateway(
    sse_url=settings.mcp_gateway_sse_url,
    bearer_token=settings.mcp_gateway_bearer_token,
)

print(mcp_gateway.get_tools_schema())

agent = AgentCore(
    llm_client=llm_client,
    messages_list=messages_list,
    mcp_gateway=mcp_gateway,
)

app = FastAPI(
    title="agent-service FastAPI service",
    version="0.1.0",
    description="HTTP API wrapper around AgentCore.",
)

agent_lock = Lock()

app.include_router(create_router(agent=agent, agent_lock=agent_lock))
