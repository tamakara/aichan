from __future__ import annotations

from langchain_core.tools import StructuredTool

from plugins.base import BasePlugin


class PluginRegistry:
    """全局插件注册表：统一管理通道能力与工具能力。"""

    _pool: dict[str, BasePlugin] = {}

    @classmethod
    def register(cls, instance: BasePlugin) -> None:
        """注册一个插件能力到总线。"""
        cls._pool[instance.name] = instance

    @classmethod
    def get(cls, name: str) -> BasePlugin | None:
        """按名称获取已注册插件。"""
        return cls._pool.get(name)

    @classmethod
    def all_tools(cls) -> list[StructuredTool]:
        """
        收集所有可供 LLM 绑定的工具能力。

        约定：仅当插件实现了 `to_tool()` 且返回 StructuredTool 时，才视为工具。
        """
        tools: list[StructuredTool] = []
        for plugin in cls._pool.values():
            tool_schema = plugin.get_tool()
            if tool_schema is not None:
                tools.append(tool_schema)
        return tools

    @classmethod
    def clear(cls) -> None:
        """清空注册表，常用于服务重启或单元测试隔离。"""
        cls._pool.clear()


