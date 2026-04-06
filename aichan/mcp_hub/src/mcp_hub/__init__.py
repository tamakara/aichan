"""
MCP Hub 包导出入口。

外部模块通常只需要导入：
1. `MCPManager` 作为统一连接与工具编排入口；
2. `MCPServerConfig` 用于声明服务连接配置；
3. `WakeupSignal` 用于读取最近一次唤醒上下文。
"""

from .manager import MCPManager
from .models import MCPServerConfig, WakeupSignal

__all__ = [
    "MCPManager",
    "MCPServerConfig",
    "WakeupSignal",
]
