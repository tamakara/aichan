from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager, suppress
from datetime import datetime, timezone
from typing import Any, Literal

import httpx
import uvicorn
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from loguru import logger
from pydantic import BaseModel, Field

# ==========================================
# ⚙️ 全局默认配置常量
# ==========================================
CLI_SERVER_HOST = os.getenv("CLI_SERVER_HOST", "127.0.0.1")
CLI_SERVER_PORT = int(os.getenv("CLI_SERVER_PORT", "8765"))
CLI_GATEWAY_BASE_HOST = os.getenv("CLI_GATEWAY_BASE_HOST", "127.0.0.1")

# Uvicorn 服务器配置
CLI_SERVER_TIMEOUT_KEEP_ALIVE_SECONDS = 1
CLI_SERVER_TIMEOUT_GRACEFUL_SHUTDOWN_SECONDS = 2

# SSE 与注册中心配置
CLI_SERVER_SSE_WAIT_TIMEOUT_SECONDS = 1.0
REGISTRY_RETRY_SECONDS = 3.0
DEFAULT_AICHAN_REGISTRY_URL = "http://127.0.0.1:8000/internal/registry/register"
AICHAN_REGISTRY_URL = os.getenv("AICHAN_REGISTRY_URL", DEFAULT_AICHAN_REGISTRY_URL)

CLIChannelIdentity = Literal["ai", "user"]


# ==========================================
# 📦 数据模型
# ==========================================
class SendMessageRequest(BaseModel):
    """客户端请求发送消息的载荷"""

    sender: CLIChannelIdentity
    text: str = Field(..., min_length=1)


class ChatMessage(BaseModel):
    """统一的聊天消息数据结构"""

    id: int = Field(..., ge=1)
    sender: CLIChannelIdentity
    text: str
    created_at: str


# ==========================================
# 🧠 纯异步内存状态管理
# ==========================================
class AsyncChatStore:
    """
    原生基于 asyncio 的最小内存消息存储。
    完全适配 FastAPI 的事件循环，杜绝线程阻塞问题。
    """

    def __init__(self) -> None:
        self._messages: list[ChatMessage] = []
        self._next_id = 1
        # 使用 asyncio.Lock 和 asyncio.Condition，替换原来的 threading 模块
        self._lock = asyncio.Lock()
        self._new_message_cond = asyncio.Condition(self._lock)

    async def list_messages(self, after_id: int = 0) -> list[ChatMessage]:
        """获取指定 ID 之后的所有历史消息"""
        async with self._lock:
            return self._collect_messages(after_id)

    async def wait_for_messages(
        self, after_id: int, timeout_seconds: float
    ) -> list[ChatMessage]:
        """
        挂起当前协程，等待新消息到达。
        结合了 Condition 唤醒与超时机制，实现高效的 SSE 推送。
        """
        async with self._new_message_cond:
            messages = self._collect_messages(after_id)
            if not messages:
                try:
                    # 使用 asyncio 的超时等待替代底层的 wait(timeout)
                    await asyncio.wait_for(
                        self._new_message_cond.wait(), timeout=timeout_seconds
                    )
                except asyncio.TimeoutError:
                    pass  # 超时唤醒，返回空列表供 SSE 发送 Keep-Alive
                messages = self._collect_messages(after_id)
            return messages

    def _collect_messages(self, after_id: int) -> list[ChatMessage]:
        """无锁状态下的消息过滤（调用方必须确保持有锁）"""
        return [msg for msg in self._messages if msg.id > after_id]

    async def send_message(self, sender: CLIChannelIdentity, text: str) -> ChatMessage:
        """接收新消息，并通知所有正在等待的 SSE 客户端"""
        clean_text = text.strip()
        if not clean_text:
            raise ValueError("text 不能为空")

        async with self._lock:
            message = ChatMessage(
                id=self._next_id,
                sender=sender,
                text=clean_text,
                created_at=datetime.now(timezone.utc).isoformat(),
            )
            self._messages.append(message)
            self._next_id += 1
            # 唤醒所有挂起在 wait_for_messages 处的协程
            self._new_message_cond.notify_all()

        return message


# ==========================================
# 🔌 注册中心交互与生命周期
# ==========================================
def _build_registry_payload() -> dict[str, Any]:
    """构建 CLI 网关注册载荷"""
    return {
        "name": "cli",
        "type": "channel",
        "base_url": f"http://{CLI_GATEWAY_BASE_HOST}:{CLI_SERVER_PORT}",
        "openapi_path": "/openapi.json",
        "sse_path": "/v1/events",
    }


async def register_to_registry_loop() -> None:
    """后台异步无限重试：向 AICHAN 大脑注册当前网关"""
    payload = _build_registry_payload()
    while True:
        try:
            logger.info("🔌 [CLIGateway] 尝试注册到大脑，url='{}'", AICHAN_REGISTRY_URL)
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(AICHAN_REGISTRY_URL, json=payload)
                response.raise_for_status()
            logger.info("✅ [CLIGateway] 接入大脑成功！")
            return
        except asyncio.CancelledError:
            logger.info("🛑 [CLIGateway] 注册任务收到取消信号，结束后台注册")
            raise
        except Exception as exc:
            logger.error(
                "❌ [CLIGateway] 注册失败，error='{}'，{} 秒后重试",
                exc,
                REGISTRY_RETRY_SECONDS,
            )
            await asyncio.sleep(REGISTRY_RETRY_SECONDS)


@asynccontextmanager
async def gateway_lifespan(app: FastAPI):
    """网关生命周期管理：启动注册任务，关闭时清理资源"""
    logger.info("🚀 [CLIGateway] 服务启动，注册任务准备就绪")
    registration_task = asyncio.create_task(
        register_to_registry_loop(),
        name="cli-gateway-registry-registration",
    )
    app.state.registration_task = registration_task

    yield  # 挂起，等待应用运行完毕

    logger.info("🛑 [CLIGateway] 服务关闭中，清理后台任务")
    registration_task.cancel()
    with suppress(asyncio.CancelledError):
        await registration_task


# ==========================================
# 🌐 FastAPI 路由绑定
# ==========================================
def build_cli_gateway_app() -> FastAPI:
    """构建并配置 CLI 网关 FastAPI 应用"""
    app = FastAPI(
        title="CLI Gateway Server",
        version="2.0.0",
        lifespan=gateway_lifespan,
    )
    # 实例化全局单例的异步存储库
    store = AsyncChatStore()

    @app.get("/health")
    async def health() -> dict[str, object]:
        return {"ok": True, "service": "cli_gateway"}

    @app.get("/v1/messages", response_model=list[ChatMessage])
    async def list_messages(
        after_id: int = Query(default=0, ge=0)
    ) -> list[ChatMessage]:
        return await store.list_messages(after_id=after_id)

    @app.get("/v1/events")
    async def stream_events(
        request: Request,
        after_id: int = Query(default=0, ge=0),
    ) -> StreamingResponse:
        """SSE 接口：推送增量消息，支持断点续传与 Keep-Alive 保活"""

        async def _event_generator():
            last_id = after_id
            logger.info("📡 [CLIGateway] SSE 客户端已连接，起始 ID={}", after_id)
            try:
                while True:
                    if await request.is_disconnected():
                        logger.info("📡 [CLIGateway] SSE 客户端主动断开连接")
                        break

                    # 纯异步挂起等待，释放事件循环，不再需要 to_thread
                    messages = await store.wait_for_messages(
                        last_id, CLI_SERVER_SSE_WAIT_TIMEOUT_SECONDS
                    )

                    # 发送空的心跳包防止网关或 Nginx 超时断链
                    if not messages:
                        yield ": keep-alive\n\n"
                        continue

                    # 遍历并推送新消息
                    for message in messages:
                        if await request.is_disconnected():
                            return

                        # Pydantic 原生极速 JSON 序列化
                        payload = message.model_dump_json(by_alias=True)
                        logger.info(
                            "📡 [CLIGateway] 推送 SSE 消息，message_id={}", message.id
                        )

                        yield f"id: {message.id}\nevent: message\ndata: {payload}\n\n"
                        last_id = message.id

            except asyncio.CancelledError:
                pass  # 客户端断开或服务关闭时的正常退出

        return StreamingResponse(
            _event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    @app.post("/v1/messages", response_model=ChatMessage, status_code=201)
    async def send_message(payload: SendMessageRequest) -> ChatMessage:
        try:
            # 记得此处需要 await，因为 send_message 已经变成了异步协程
            message = await store.send_message(sender=payload.sender, text=payload.text)
            logger.info(
                "✅ [CLIGateway] 收到消息写入，message_id={}，sender='{}'",
                message.id,
                message.sender,
            )
            return message
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    return app


# ==========================================
# 🚀 启动入口
# ==========================================
def run_cli_gateway(host: str = CLI_SERVER_HOST, port: int = CLI_SERVER_PORT) -> None:
    logger.info("🚀 [CLIGateway] 准备在 {}:{} 启动服务...", host, port)
    uvicorn.run(
        build_cli_gateway_app(),
        host=host,
        port=port,
        log_level="info",
        access_log=True,
        timeout_keep_alive=CLI_SERVER_TIMEOUT_KEEP_ALIVE_SECONDS,
        timeout_graceful_shutdown=CLI_SERVER_TIMEOUT_GRACEFUL_SHUTDOWN_SECONDS,
    )


def main() -> None:
    run_cli_gateway()


if __name__ == "__main__":
    main()
