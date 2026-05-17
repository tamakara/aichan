import json
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, AsyncIterator, Dict, List

import anyio
import mcp.types as mcp_types
from mcp.client.session import ClientSession
from mcp.client.sse import sse_client

from ..logger import elapsed_ms, get_logger, log_info, log_warning, start_timer


@dataclass(frozen=True)
class McpToolBinding:
    remote_name: str
    description: str
    input_schema: Dict[str, Any]


class McpGateway:
    # 当前只针对已观测到的兼容性报错做最小修复：
    # OpenAI 兼容网关在 tools schema 中不接受 propertyNames。
    _UNSUPPORTED_SCHEMA_KEYS = {"propertyNames"}

    def __init__(self, sse_url: str, auth_token: str | None = None):
        self._logger = get_logger("mcp_gateway")
        self._sse_url = sse_url
        self._auth_token = auth_token
        self._mcp_tools: Dict[str, McpToolBinding] = {}
        self._tools_schema: List[Dict[str, Any]] = []

    def register_mcp_server(self) -> None:
        started_at = start_timer()
        try:
            remote_tools = anyio.run(self._list_mcp_tools_async)
        except Exception as exc:
            raise RuntimeError("连接 MCP SSE 服务失败") from exc

        # 启动阶段把远端工具元数据固化为本地映射，后续只按名称检索，避免每轮请求都拉取工具列表。
        for remote_tool in remote_tools:
            self._mcp_tools[remote_tool.name] = McpToolBinding(
                remote_name=remote_tool.name,
                description=remote_tool.description or "MCP tool from SSE Gateway",
                input_schema=self._normalize_schema(
                    schema=remote_tool.inputSchema,
                    tool_name=remote_tool.name,
                ),
            )
        self._refresh_tools_schema()
        log_info(
            self._logger,
            "mcp.registered",
            tool_count=len(remote_tools),
            elapsed_ms=elapsed_ms(started_at),
        )

    def get_tools_schema(self) -> List[Dict[str, Any]]:
        return self._tools_schema

    def call_tool(self, tool_name: str, tool_args: Dict[str, Any]) -> str:
        started_at = start_timer()
        binding = self._mcp_tools.get(tool_name)
        if binding is None:
            raise KeyError(f"未找到工具: {tool_name}")
        if not isinstance(tool_args, dict):
            raise TypeError(f"工具参数必须是 dict，当前为: {type(tool_args)}")

        try:
            result = anyio.run(
                self._call_mcp_tool_async, binding.remote_name, tool_args
            )
        except Exception as exc:
            raise RuntimeError(f"调用 MCP SSE 工具失败: {exc}") from exc

        log_info(
            self._logger,
            "mcp.tool_called",
            tool_name=tool_name,
            elapsed_ms=elapsed_ms(started_at),
        )

        return json.dumps(
            result.model_dump(by_alias=True, mode="json", exclude_none=True),
            ensure_ascii=False,
        )

    def _refresh_tools_schema(self) -> None:
        self._tools_schema = [
            {
                "type": "function",
                "function": {
                    "name": name,
                    "description": binding.description,
                    "parameters": binding.input_schema,
                },
            }
            for name, binding in self._mcp_tools.items()
        ]

    async def _list_mcp_tools_async(self) -> List[mcp_types.Tool]:
        async with self._mcp_session() as session:
            result = await session.list_tools()
            return result.tools

    async def _call_mcp_tool_async(
        self, remote_tool_name: str, tool_args: Dict[str, Any]
    ) -> mcp_types.CallToolResult:
        async with self._mcp_session() as session:
            return await session.call_tool(name=remote_tool_name, arguments=tool_args)

    @asynccontextmanager
    async def _mcp_session(self) -> AsyncIterator[ClientSession]:
        headers = (
            {"Authorization": f"Bearer {self._auth_token}"}
            if self._auth_token
            else None
        )
        async with sse_client(self._sse_url, headers=headers) as streams:
            read_stream, write_stream = streams
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize() 
                yield session

    def _normalize_schema(self, schema: Any, tool_name: str) -> Dict[str, Any]:
        if not isinstance(schema, dict):
            return {"type": "object", "properties": {}}

        out = dict(schema)
        if "type" not in out:
            out["type"] = "object"
        if out["type"] == "object" and "properties" not in out:
            out["properties"] = {}

        cleaned, removed_keys = self._sanitize_schema_node(out)
        if removed_keys:
            log_warning(
                self._logger,
                "mcp.schema_sanitized",
                tool_name=tool_name,
                removed_keys=",".join(sorted(set(removed_keys))),
            )

        return cleaned

    def _sanitize_schema_node(self, node: Any) -> tuple[Any, list[str]]:
        removed_keys: list[str] = []

        if isinstance(node, dict):
            cleaned: Dict[str, Any] = {}
            for key, value in node.items():
                if key in self._UNSUPPORTED_SCHEMA_KEYS:
                    removed_keys.append(key)
                    continue

                cleaned_value, child_removed = self._sanitize_schema_node(value)
                cleaned[key] = cleaned_value
                removed_keys.extend(child_removed)

            return cleaned, removed_keys

        if isinstance(node, list):
            cleaned_list: list[Any] = []
            for item in node:
                cleaned_item, child_removed = self._sanitize_schema_node(item)
                cleaned_list.append(cleaned_item)
                removed_keys.extend(child_removed)

            return cleaned_list, removed_keys

        return node, removed_keys
