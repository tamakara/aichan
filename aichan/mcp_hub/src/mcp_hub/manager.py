from __future__ import annotations

import asyncio
from typing import Any

from langchain_core.tools import StructuredTool

from core.logger import logger
from .connections import MCPConnectionPool
from .models import MCPServerConfig, WakeupSignal
from .tool_catalog import MCPToolCatalog
from .tool_executor import MCPToolExecutor
from .wakeup import WakeupEventBus


class MCPManager:
    """
    MCP 多服务连接管理器。

    设计目标：
    1. 统一维护 MCP 会话生命周期；
    2. 动态发现并包装工具；
    3. 以 MCP Custom Notification 触发全局唤醒 Event。
    """

    def __init__(
        self,
        server_configs: list[MCPServerConfig],
    ) -> None:
        # 连接池：负责会话生命周期与资源管理。
        self._connections = MCPConnectionPool(server_configs)

        # 唤醒总线：负责 event 置位与最近唤醒快照。
        self._wakeup_bus = WakeupEventBus()

        # 工具执行器：负责原始工具调用与结果解析。
        self._tool_executor = MCPToolExecutor(
            sessions_provider=lambda: self._connections.sessions
        )

        # 工具目录：负责 list_tools 聚合、路由与包装工具快照。
        self._tool_catalog = MCPToolCatalog(
            tool_caller=self._tool_executor.call_tool,
        )

        # 管理器生命周期状态位。
        self._started = False

    async def start(self) -> None:
        """启动管理器并建立 MCP 会话。"""
        if self._started:
            logger.warning("♻️ [MCPHub] MCPManager 已启动，忽略重复调用")
            return

        try:
            # 先建立全部连接，再刷新工具快照。
            await self._connections.start(self._wakeup_bus.handle_wakeup_notification)
            await self._tool_catalog.refresh(self._connections.sessions)
            self._started = True
            logger.info(
                "🧠 [MCPHub] MCPManager 启动完成，连接服务数={}，工具数={}",
                self._connections.get_connected_server_count(),
                len(self._tool_catalog.get_tools()),
            )
        except Exception:
            # 启动阶段任意异常都做统一回滚，避免半启动状态。
            await self.stop()
            raise

    async def stop(self) -> None:
        """关闭管理器并释放连接资源。"""
        # 先切换状态，避免外部继续调用。
        self._started = False

        # 清空工具快照，防止停止后误用旧工具。
        self._tool_catalog.clear()

        # 重置唤醒状态，避免残留旧 event/signal。
        self._wakeup_bus.reset()

        # 释放全部会话连接资源。
        await self._connections.stop()
        logger.info("🛑 [MCPHub] MCPManager 连接资源已释放")

    async def get_all_tools(self, refresh: bool = True) -> list[StructuredTool]:
        """获取所有包装后的工具列表。"""
        self._ensure_started()
        if refresh:
            # 按需刷新工具目录，确保调用端拿到最新快照。
            await self._tool_catalog.refresh(self._connections.sessions)
        return self._tool_catalog.get_tools()

    def get_wakeup_event(self) -> asyncio.Event:
        """返回全局唤醒事件。"""
        self._ensure_started()
        return self._wakeup_bus.get_event()

    async def wait_for_wakeup(self) -> None:
        """等待一条 MCP 唤醒通知。"""
        self._ensure_started()
        await self._wakeup_bus.wait()

    def clear_wakeup_event(self) -> None:
        """清理唤醒事件标记。"""
        self._ensure_started()
        self._wakeup_bus.clear()

    def get_last_wakeup_signal(self) -> WakeupSignal | None:
        """返回最近一次唤醒信号。"""
        self._ensure_started()
        return self._wakeup_bus.get_last_signal()

    def get_last_wakeup_snapshot(self) -> dict[str, Any] | None:
        """返回最近一次唤醒信号快照（用于健康检查等观测）。"""
        self._ensure_started()
        return self._wakeup_bus.get_last_snapshot()

    async def call_tool(
        self,
        server_name: str,
        tool_name: str,
        arguments: dict[str, Any] | None,
    ) -> str:
        """
        调用指定 MCP 原始工具并返回解析后的字符串结果。

        参数：
        - server_name: MCP 服务别名；
        - tool_name: 服务内原始工具名；
        - arguments: 工具调用参数。
        """
        self._ensure_started()
        # 具体调用逻辑下沉到执行器，管理器只做编排转发。
        return await self._tool_executor.call_tool(
            server_name=server_name,
            tool_name=tool_name,
            arguments=arguments,
        )

    async def call_wrapped_tool(
        self,
        wrapped_name: str,
        arguments: dict[str, Any],
    ) -> str:
        """按包装后工具名调用 MCP 工具。"""
        self._ensure_started()

        # 先做包装名 -> 原始路由解析。
        route = self._tool_catalog.resolve_route(wrapped_name)
        if route is None:
            raise ValueError(f"未知包装工具：{wrapped_name}")

        # 再复用统一 call_tool 执行链路。
        return await self.call_tool(
            server_name=route.server_name,
            tool_name=route.source_tool_name,
            arguments=arguments,
        )

    def get_connected_server_count(self) -> int:
        """返回当前已连接的 MCP 服务数量。"""
        return self._connections.get_connected_server_count()

    def _ensure_started(self) -> None:
        """统一启动态断言，避免在未启动时访问运行资源。"""
        if not self._started:
            raise RuntimeError("MCPManager 尚未启动，请先调用 await start()")
