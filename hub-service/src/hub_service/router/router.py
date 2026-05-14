from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from .schemas import HealthResponse
from ..services.reminder_service import HubPipelineService


def create_router(hub_pipeline_service: HubPipelineService) -> APIRouter:
    router = APIRouter()
    logger = logging.getLogger(__name__)

    @router.get("/healthz", response_model=HealthResponse)
    async def healthz() -> HealthResponse:
        return HealthResponse()

    @router.websocket("/qq/events")
    async def qq_events(websocket: WebSocket) -> None:
        await websocket.accept()

        try:
            while True:
                data = await websocket.receive_json()
                event = _parse_hub_event(data)
                if event is None:
                    continue

                if event["message_type"] != "private":
                    # 当前中枢仅处理私聊触发，群聊事件直接忽略。
                    continue

                # 每条私聊提醒独立调度，避免某次下游慢调用阻塞 WS 消息读取循环。
                asyncio.create_task(
                    _run_pipeline_safely(
                        hub_pipeline_service=hub_pipeline_service,
                        user_id=event["user_id"],
                        session_id=event["session_id"],
                        content=event["content"],
                        raw_event=event["raw_event"],
                        logger=logger,
                    )
                )
        except WebSocketDisconnect:
            return

    return router


async def _run_pipeline_safely(
    hub_pipeline_service: HubPipelineService,
    user_id: str,
    session_id: str,
    content: str,
    raw_event: dict,
    logger: logging.Logger,
) -> None:
    try:
        await hub_pipeline_service.handle_private_event(
            user_id=user_id,
            session_id=session_id,
            content=content,
            raw_event=raw_event,
        )
    except Exception:
        logger.exception("hub stage=receive user_id=%s session_id=%s", user_id, session_id)


def _parse_hub_event(data: Any) -> dict[str, Any] | None:
    if not isinstance(data, dict):
        return None

    session_id = data.get("session_id")
    user_id = data.get("user_id")
    content = data.get("content")
    source = data.get("source")
    message_type = data.get("message_type")
    raw_event = data.get("raw_event")

    if not isinstance(session_id, str) or not session_id:
        return None
    if not isinstance(user_id, str) or not user_id:
        return None
    if not isinstance(content, str) or not content:
        return None
    if source != "qq":
        return None
    if message_type not in ("group", "private"):
        return None
    if not isinstance(raw_event, dict):
        return None

    return {
        "session_id": session_id,
        "user_id": user_id,
        "content": content,
        "message_type": message_type,
        "raw_event": raw_event,
    }
