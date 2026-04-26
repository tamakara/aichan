from threading import Lock

import anyio
import uvicorn
from fastapi import FastAPI, HTTPException

from .agent_core import AgentCore
from .config import get_settings, get_system_prompt
from .schemas import ChatRequest, ChatResponse, HealthResponse

settings = get_settings()
system_prompt = get_system_prompt()
agent = AgentCore(
    llm_model_name=settings.llm_model_name,
    llm_api_key=settings.llm_api_key,
    llm_base_url=settings.llm_base_url,
    system_prompt=system_prompt,
    mcp_sse_url=settings.mcp_sse_url,
    mcp_sse_bearer_token=settings.mcp_sse_bearer_token,
)
agent_lock = Lock()

app = FastAPI(
    title="agent-service FastAPI service",
    version="0.1.0",
    description="HTTP API wrapper around AgentCore.",
)


def _chat(user_input: str, max_turns: int) -> str:
    with agent_lock:
        return agent.chat(user_input=user_input, max_turns=max_turns)


def _clear_session() -> None:
    with agent_lock:
        agent.clear_session()


@app.get("/healthz", response_model=HealthResponse)
async def healthz() -> HealthResponse:
    return HealthResponse(status="ok")


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest) -> ChatResponse:
    try:
        reply = await anyio.to_thread.run_sync(_chat, req.user_input, req.max_turns)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return ChatResponse(reply=reply)


@app.delete("/session", status_code=204)
async def clear_session() -> None:
    await anyio.to_thread.run_sync(_clear_session)


def run() -> None:
    uvicorn.run(
        "agent_service.main:app",
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level,
    )
