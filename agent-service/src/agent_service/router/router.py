from threading import Lock

from fastapi import APIRouter, HTTPException

from ..logger import elapsed_ms, get_logger, log_exception, log_info, start_timer
from ..services import AgentCore, Session
from ..services.prompts import SYSTEM_PROMPT
from .schemas import ChatRequest, ChatResponse, HealthResponse


def create_router(
    agent: AgentCore,
    session_contexts: dict[str, tuple[Session, Lock]],
    registry_lock: Lock,
) -> APIRouter:
    # 每次装配时创建独立路由对象，避免测试或重复初始化时重复注册同一路由。
    router = APIRouter()
    logger = get_logger("router")

    @router.get("/healthz", response_model=HealthResponse)
    def healthz() -> HealthResponse:
        return HealthResponse(status="ok")

    @router.post("/chat", response_model=ChatResponse)
    def chat(req: ChatRequest) -> ChatResponse:
        request_started_at = start_timer()
        log_info(
            logger,
            "agent.chat_received",
            session_id=req.session_id,
            user_message_len=len(req.user_message),
        )

        try:
            # 注册表只负责“首次创建”，锁粒度很小；
            # 实际串行控制仍在会话级锁上，不会把不同 session 串在一起。
            with registry_lock:
                context = session_contexts.get(req.session_id)
                created_new_session = False
                if context is None:
                    session = Session(session_id=req.session_id)
                    # system prompt 在会话初始化时注入，保证每个 session 都遵循统一行为边界。
                    session.add_message(role="system", content=SYSTEM_PROMPT)
                    session.add_message(role="system", content=f"<session_start session_id={req.session_id}>")
                    context = (session, Lock())
                    session_contexts[req.session_id] = context
                    created_new_session = True

            log_info(
                logger,
                "agent.session_bound",
                session_id=req.session_id,
                created_new_session=created_new_session,
            )

            session, session_lock = context

            # 同一会话必须串行，避免并发写同一段消息历史导致上下文错乱；
            # 不同会话拥有各自独立锁，因此可以并行执行。
            with session_lock:
                reply = agent.run(
                    session=session,
                    user_message=req.user_message,
                )
            log_info(
                logger,
                "agent.chat_completed",
                session_id=req.session_id,
                reply_len=len(reply),
                elapsed_ms=elapsed_ms(request_started_at),
            )
        except Exception as exc:
            log_exception(
                logger,
                "agent.chat_failed",
                session_id=req.session_id,
                elapsed_ms=elapsed_ms(request_started_at),
            )
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        return ChatResponse(reply=reply)

    return router
