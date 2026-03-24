from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress

import uvicorn
from fastapi import FastAPI
from langchain_openai import ChatOpenAI

from brain.brain import Brain
from cli_server import create_app
from core.config import settings
from core.logger import logger
from nexus.agent import AgentOrchestrator
from nexus.hub import nexus_hub
from plugins.channels.cli import CLIChannelPlugin
from plugins.registry import PluginRegistry
from plugins.tools.time_tool import CurrentTimeToolPlugin


def register_default_plugins() -> None:
    """
    注册系统启动后的默认插件能力。

    说明：
    - `cli` 属于交互通道能力（负责把外部负载转成 UserMessage）
    - `get_current_time` 属于工具能力（可被 LLM 调用）
    """
    PluginRegistry.clear()
    PluginRegistry.register(CLIChannelPlugin())
    PluginRegistry.register(CurrentTimeToolPlugin())


def build_orchestrator() -> AgentOrchestrator:
    """
    组装核心模块并返回编排器（nexus）实例。

    组装顺序：
    1) 注册默认插件能力
    2) 初始化 LLM 并构建 brain
    3) 构建 nexus（AgentOrchestrator）
    """
    register_default_plugins()

    llm = ChatOpenAI(
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
        model=settings.llm_model_name,
        temperature=settings.llm_temperature,
    )

    brain = Brain(llm_client=llm, tools=PluginRegistry.all_tools())
    return AgentOrchestrator(brain=brain)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    heartbeat_task = asyncio.create_task(nexus_hub.start_heartbeat())
    try:
        yield
    finally:
        nexus_hub.stop_heartbeat()
        heartbeat_task.cancel()
        with suppress(asyncio.CancelledError):
            await heartbeat_task


def main() -> None:
    """
    本地启动入口：先完成系统模块组装，再启动 HTTP 服务。
    """
    orchestrator = build_orchestrator()
    app = create_app(orchestrator, lifespan=lifespan)

    logger.info(
        "AIChan 服务已启动：http://{}:{}",
        settings.chat_server_host,
        settings.chat_server_port,
    )
    logger.info("请在另一个终端运行 `uv run python cli_client.py` 发起对话。")

    uvicorn.run(
        app,
        host=settings.chat_server_host,
        port=settings.chat_server_port,
        log_level="info",
    )


if __name__ == "__main__":
    main()
