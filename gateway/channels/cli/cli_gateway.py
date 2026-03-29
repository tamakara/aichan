from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager, suppress
from typing import Any

import httpx
import uvicorn
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from loguru import logger

from cli_server import (
    CLI_SERVER_SSE_WAIT_TIMEOUT_SECONDS,
    CLIMessageService,
    ChatMessage,
    SendMessageRequest,
)

# ==========================================
# ⚙️ 全局默认配置常量
# ==========================================
CLI_SERVER_HOST = os.getenv("CLI_SERVER_HOST", "localhost")
CLI_SERVER_PORT = int(os.getenv("CLI_SERVER_PORT", "9000"))
CLI_GATEWAY_BASE_HOST = os.getenv("CLI_GATEWAY_HOST", "localhost")

# Uvicorn 服务器配置
CLI_SERVER_TIMEOUT_KEEP_ALIVE_SECONDS = 1
CLI_SERVER_TIMEOUT_GRACEFUL_SHUTDOWN_SECONDS = 2

# SSE 与注册中心配置
REGISTRY_RETRY_SECONDS = 3.0
AICHAN_REGISTRY_URL = os.getenv(
    "AICHAN_REGISTRY_URL", "http://localhost:8000/internal/registry/register"
)


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

    yield

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
    service = CLIMessageService()

    @app.get("/health")
    async def health() -> dict[str, object]:
        return {"ok": True, "service": "cli_gateway"}

    @app.get("/v1/messages", response_model=list[ChatMessage])
    async def list_messages(
        after_id: int = Query(default=0, ge=0)
    ) -> list[ChatMessage]:
        return await service.list_messages(after_id=after_id)

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

                    messages = await service.wait_incremental_messages(
                        after_id=last_id,
                        timeout_seconds=CLI_SERVER_SSE_WAIT_TIMEOUT_SECONDS,
                    )

                    if not messages:
                        yield ": keep-alive\n\n"
                        continue

                    for message in messages:
                        if await request.is_disconnected():
                            return

                        payload = message.model_dump_json(by_alias=True)
                        logger.info(
                            "📡 [CLIGateway] 推送 SSE 消息，message_id={}", message.id
                        )

                        yield f"id: {message.id}\nevent: message\ndata: {payload}\n\n"
                        last_id = message.id

            except asyncio.CancelledError:
                pass

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
            message = await service.save_message(payload)
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
