"""
AICHAN Brain 服务主入口。

模块职责：
1. 读取配置并构建 LLM 客户端；
2. 解析 MCP 端点并启动 MCP 管理器；
3. 装配 AgentRuntime，建立唤醒驱动的推理循环；
4. 暴露 FastAPI 健康检查与服务生命周期。
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import Any
from urllib.parse import urlparse
import re

import uvicorn
from fastapi import FastAPI
from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI

from agent import AgentRuntime
from core.config import settings
from core.logger import logger
from mcp_hub import MCPManager, MCPServerConfig


def build_llm_client() -> BaseChatModel:
    """
    构建 LLM 客户端。
    """
    return ChatOpenAI(
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
        model=settings.llm_model_name,
        temperature=settings.llm_temperature,
    )


def build_mcp_server_configs(raw_endpoints: str) -> list[MCPServerConfig]:
    """
    将环境变量中的 MCP 端点列表解析为标准配置。

    约定：
    - 逗号分隔多个端点 URL；
    - 自动生成稳定服务别名；
    - 唤醒行为由 MCP 自定义通知驱动，不再依赖 URL 查询参数过滤；
    - 当前版本默认全部视为强依赖服务。
    """
    # 先将逗号分隔输入清洗为“非空 URL 列表”。
    parsed_endpoints = [
        item.strip() for item in raw_endpoints.split(",") if item.strip()
    ]
    configs: list[MCPServerConfig] = []
    used_aliases: set[str] = set()
    for index, endpoint_url in enumerate(parsed_endpoints, start=1):
        clean_url = endpoint_url
        parsed = urlparse(clean_url)
        # 以域名为主生成服务别名，缺失时回退到顺序别名。
        raw_alias = parsed.netloc or f"mcp_{index}"
        alias = re.sub(r"[^A-Za-z0-9_]+", "_", raw_alias).strip("_").lower()
        if not alias:
            alias = f"mcp_{index}"
        if alias[0].isdigit():
            alias = f"mcp_{alias}"

        # 处理别名冲突，保证同一轮配置内别名唯一。
        if alias in used_aliases:
            alias = f"{alias}_{index}"
        used_aliases.add(alias)

        configs.append(
            MCPServerConfig(
                name=alias,
                endpoint_url=clean_url,
            )
        )
    return configs


@asynccontextmanager
async def app_lifespan(app: FastAPI):
    """
    应用生命周期管理。

    启动阶段：
    1. 初始化 MCPManager；
    2. 启动 AgentRuntime。

    关闭阶段：
    1. 停止 AgentRuntime；
    2. 停止 MCPManager。
    """
    logger.info("🚀 [Main] AICHAN 生命周期启动中...")

    server_configs = build_mcp_server_configs(settings.mcp_server_endpoints)
    mcp_manager = MCPManager(
        server_configs=server_configs,
    )
    retry_seconds = max(0.2, float(settings.mcp_connect_retry_seconds))
    while True:
        try:
            await mcp_manager.start()
            break
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning(
                "⚠️ [Main] MCPHub 连接失败，将在 {:.1f}s 后重试，error='{}: {}'",
                retry_seconds,
                exc.__class__.__name__,
                exc,
            )
            await asyncio.sleep(retry_seconds)

    agent_runtime = AgentRuntime(
        llm_factory=build_llm_client,
        mcp_manager=mcp_manager,
    )
    await agent_runtime.start()

    app.state.mcp_manager = mcp_manager
    app.state.agent_runtime = agent_runtime

    try:
        yield
    finally:
        logger.info("🛑 [Main] AICHAN 生命周期关闭中")
        await agent_runtime.stop()
        await mcp_manager.stop()
        logger.info("✅ [Main] AICHAN 已停止")


def create_app() -> FastAPI:
    """
    创建 AICHAN 大脑应用。

    路由构成：
    - `/health`：基础健康检查。
    """
    app = FastAPI(
        title="AICHAN",
        version="1.0.0",
        lifespan=app_lifespan,
    )

    @app.get("/health")
    async def health() -> dict[str, Any]:
        """
        健康检查端点。

        除基础存活状态外，还会返回 MCP 连接数量、工具数量以及最近唤醒快照，
        便于运维快速判断系统当前是否具备完整工作能力。
        """
        mcp_manager: MCPManager | None = getattr(app.state, "mcp_manager", None)
        mcp_tool_count = 0
        mcp_server_count = 0
        wakeup_event_is_set = False
        last_wakeup: dict[str, Any] | None = None
        if mcp_manager is not None:
            mcp_server_count = mcp_manager.get_connected_server_count()
            mcp_tool_count = len(await mcp_manager.get_all_tools(refresh=False))
            wakeup_event_is_set = mcp_manager.get_wakeup_event().is_set()
            last_wakeup = mcp_manager.get_last_wakeup_snapshot()

        return {
            "ok": True,
            "service": "aichan_brain",
            "mcp_server_count": mcp_server_count,
            "mcp_tool_count": mcp_tool_count,
            "wakeup_event_is_set": wakeup_event_is_set,
            "last_wakeup": last_wakeup,
        }

    return app


app = create_app()


def main() -> None:
    """直接启动 AICHAN 大脑服务。"""
    logger.info("🚀 [Main] AICHAN Brain 启动中，监听 0.0.0.0:8000")
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info",
        access_log=True,
    )


if __name__ == "__main__":
    main()
