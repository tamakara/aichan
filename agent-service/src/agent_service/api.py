from fastapi import APIRouter, HTTPException

from .agent_core import AgentCore
from .schemas import ChatRequest, ChatResponse, HealthResponse


def create_router(agent: AgentCore, agent_lock) -> APIRouter:
    router = APIRouter()

    @router.get("/healthz", response_model=HealthResponse)
    def healthz() -> HealthResponse:
        return HealthResponse(status="ok")

    @router.post("/chat", response_model=ChatResponse)
    def chat(req: ChatRequest) -> ChatResponse:
        try:
            with agent_lock:
                reply = agent.chat(user_input=req.user_input, max_turns=req.max_turns)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        return ChatResponse(reply=reply)

    return router
