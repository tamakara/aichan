from __future__ import annotations

from collections.abc import AsyncIterator, Callable

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from core.logger import logger
from nexus.agent import AgentOrchestrator
from nexus.hub import nexus_hub
from plugins.registry import PluginRegistry


class ChatRequest(BaseModel):
    """客户端发送到网关的标准请求体。"""

    channel: str = Field(default="cli", description="插件通道名称")
    content: str = Field(..., description="用户输入内容")


class ChatResponse(BaseModel):
    """网关返回给客户端的标准响应体。"""

    reply: str = Field(..., description="模型最终回复文本")


def create_app(
    _orchestrator: AgentOrchestrator,
    lifespan: Callable[[FastAPI], AsyncIterator[None]] | None = None,
) -> FastAPI:
    """
    创建 CLI 网关应用。

    约束：
    - 本文件只负责 HTTP 接口、请求/响应模型和错误码映射。
    - 系统模块组装（plugins/brain/memory/nexus）由 main.py 提供。
    - 在 Pull 架构下，HTTP 入口只负责把信号推入 Nexus 队列。
    """
    app = FastAPI(
        title="AIChan 聊天网关",
        description="AIChan 双进程模式下的聊天服务入口",
        version="0.1.0",
        lifespan=lifespan,
    )

    @app.get("/health")
    def health() -> dict[str, str]:
        """健康检查接口，用于探活与启动验证。"""
        return {"status": "ok"}

    @app.post("/chat", response_model=ChatResponse)
    async def chat(req: ChatRequest) -> ChatResponse:
        """
        聊天主入口：
        1) 校验 channel 是否已注册
        2) 将输入作为神经信号推送到 Nexus 中央队列
        3) 立即返回已入队状态，由 Brain 在后台消费
        """
        channel = PluginRegistry.get(req.channel)
        if channel is None:
            raise HTTPException(status_code=400, detail=f"未知通道: {req.channel}")

        try:
            content = req.content.strip()
            if not content:
                raise ValueError("content 不能为空")

            await nexus_hub.push_signal(
                source=req.channel,
                content=content,
                metadata={"transport": "http"},
            )
        except ValueError as exc:
            # 输入参数不完整或格式不合法时返回 400。
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            logger.exception(f"聊天处理失败：{exc}")
            raise HTTPException(status_code=500, detail="聊天处理失败") from exc

        return ChatResponse(reply="queued")

    return app
