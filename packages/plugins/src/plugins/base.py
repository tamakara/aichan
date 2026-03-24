from __future__ import annotations

from abc import ABC, abstractmethod

from langchain_core.tools import StructuredTool

class BasePlugin(ABC):
    """
    AIChan 插件系统的核心基类。
    基于“控制反转(Pull)”与“多模态工具”架构设计：
    无论是主动操作（如写本地文件）还是被动感知（如拉取 QQ 未读消息），
    统统封装为单一的 Tool 暴露给大模型。
    """

    def __init__(self, name: str, description: str) -> None:
        # name 作为注册表中的唯一能力标识
        self.name = name
        self.description = description

    @abstractmethod
    def get_tool(self) -> StructuredTool:
        """
        返回该插件对外暴露的唯一多模态工具（Fat Tool）。
        
        返回值通常是被 @tool 装饰过的 Python 函数对象。
        大模型将通过传入不同的 action 参数（如 action="read" / action="write"）
        来决定调用该插件的哪种具体能力。
        """
        pass