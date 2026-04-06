from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import Any

import mcp.types as mcp_types
from langchain_core.tools import StructuredTool
from mcp.client.session import ClientSession

from core.logger import logger

from .tools_wrapper import build_mcp_structured_tool

# MCP 工具调用抽象：
# - 入参：server_name、source_tool_name、arguments；
# - 出参：解析后的字符串结果。
ToolCaller = Callable[[str, str, dict[str, Any] | None], Awaitable[str]]


@dataclass(frozen=True, slots=True)
class WrappedToolRoute:
    """
    包装后工具名到 MCP 原始工具的路由映射。

    示例：
    - wrapped_name: `cli__send_message`
    - server_name: `cli`
    - source_tool_name: `send_message`
    """

    wrapped_name: str
    server_name: str
    source_tool_name: str


class MCPToolCatalog:
    """
    维护 MCP 工具目录快照与包装路由。

    职责边界：
    1. 从各服务会话拉取 `list_tools`；
    2. 生成包装工具名与路由映射；
    3. 构建可直接绑定到 Agent 的 `StructuredTool` 列表；
    4. 提供工具快照读取与按包装名反查能力。
    """

    def __init__(
        self,
        *,
        tool_caller: ToolCaller,
    ) -> None:
        # 统一的工具调用入口（由外部注入，避免目录层直接依赖执行细节）。
        self._tool_caller = tool_caller

        # 当前快照：包装名 -> 原始工具路由。
        self._routes: dict[str, WrappedToolRoute] = {}

        # 当前快照：包装后的 StructuredTool 列表。
        self._wrapped_tools: list[StructuredTool] = []

        # 防止并发 refresh 导致快照互相覆盖。
        self._refresh_lock = asyncio.Lock()

    async def refresh(self, sessions: Mapping[str, ClientSession]) -> None:
        """
        刷新工具快照。

        刷新策略：
        - 全量重建 routes 与 wrapped_tools；
        - 成功后原子替换旧快照；
        - 任一服务失败即抛错中断刷新。
        """
        async with self._refresh_lock:
            wrapped_tools: list[StructuredTool] = []
            routes: dict[str, WrappedToolRoute] = {}

            for server_name, session in sessions.items():
                try:
                    # 从 MCP 服务读取工具清单。
                    listed_tools = await session.list_tools()
                except Exception as exc:
                    raise RuntimeError(
                        f"MCP 服务工具发现失败：server='{server_name}'"
                    ) from exc

                for source_tool in listed_tools.tools:
                    # 按统一命名规则构建包装名。
                    wrapped_name = self._build_wrapped_tool_name(
                        server_name=server_name,
                        source_tool=source_tool,
                    )

                    # 建立包装名到原始工具的反向路由。
                    route = WrappedToolRoute(
                        wrapped_name=wrapped_name,
                        server_name=server_name,
                        source_tool_name=source_tool.name,
                    )
                    routes[wrapped_name] = route

                    # 生成可直接给 Agent 使用的 StructuredTool。
                    wrapped_tools.append(
                        self._build_structured_tool(
                            route=route,
                            source_tool=source_tool,
                        )
                    )

            # 统一替换快照，避免外部读到半成品状态。
            self._routes = routes
            self._wrapped_tools = wrapped_tools
            logger.info("🔍 [MCPHub] 工具快照刷新完成，工具总数={}", len(self._wrapped_tools))

    def get_tools(self) -> list[StructuredTool]:
        """返回工具快照副本，避免外部改写内部列表。"""
        return list(self._wrapped_tools)

    def resolve_route(self, wrapped_name: str) -> WrappedToolRoute | None:
        """按包装工具名解析到原始路由。"""
        return self._routes.get(wrapped_name)

    def clear(self) -> None:
        """清空工具快照，通常在停止阶段调用。"""
        self._routes = {}
        self._wrapped_tools = []

    def _build_structured_tool(
        self,
        *,
        route: WrappedToolRoute,
        source_tool: mcp_types.Tool,
    ) -> StructuredTool:
        """
        将 MCP 原始工具包装为 LangChain StructuredTool。

        这里仅负责“工具定义层”拼装；
        实际调用通过注入的 `self._tool_caller` 完成。
        """

        async def _async_executor(arguments: dict[str, Any]) -> str:
            return await self._tool_caller(
                route.server_name,
                route.source_tool_name,
                arguments,
            )

        return build_mcp_structured_tool(
            wrapped_name=route.wrapped_name,
            server_name=route.server_name,
            source_tool=source_tool,
            async_executor=_async_executor,
        )

    @staticmethod
    def _build_wrapped_tool_name(
        *,
        server_name: str,
        source_tool: mcp_types.Tool,
    ) -> str:
        # 同名工具冲突策略：固定 server_alias__tool_name。
        return f"{server_name}__{source_tool.name}"
