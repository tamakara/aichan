from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from mcp.client.session import ClientSession

from core.logger import logger

from .tools_wrapper import parse_call_tool_result


class MCPToolExecutor:
    """
    负责执行 MCP 原始工具调用。

    职责边界：
    1. 根据 server_name 选择对应会话；
    2. 调用 `session.call_tool`；
    3. 统一解析返回内容并记录关键日志。
    """

    def __init__(
        self,
        *,
        sessions_provider: Callable[[], Mapping[str, ClientSession]],
    ) -> None:
        # 会话提供器由外部注入，便于解耦连接层与执行层。
        self._sessions_provider = sessions_provider

    async def call_tool(
        self,
        server_name: str,
        tool_name: str,
        arguments: dict[str, Any] | None,
    ) -> str:
        """
        调用指定服务的原始工具并返回文本结果。

        参数：
        - server_name: 服务别名；
        - tool_name: 服务内原始工具名；
        - arguments: 调用参数（允许为空）。
        """
        # 每次调用都从 provider 拉取当前会话快照，确保与连接池状态一致。
        sessions = self._sessions_provider()
        session = sessions.get(server_name)
        if session is None:
            raise ValueError(f"未知 MCP 服务：{server_name}")

        logger.info(
            "⚙️ [MCPHub] 调用 MCP 工具，server='{}'，tool='{}'",
            server_name,
            tool_name,
        )
        result = await session.call_tool(
            tool_name,
            arguments=arguments or None,
        )

        # 将 MCP 原始结构化内容规范化为统一字符串。
        parsed = parse_call_tool_result(result)
        logger.info(
            "✅ [MCPHub] MCP 工具调用完成，server='{}'，tool='{}'，返回长度={}字符",
            server_name,
            tool_name,
            len(parsed),
        )
        return parsed
