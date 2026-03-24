from __future__ import annotations

from core.entities import UserMessage
from plugins.base import BasePlugin


class CLIChannelPlugin(BasePlugin):
    """CLI 通道插件：负责请求载荷与标准消息之间的转换。"""

    def __init__(self, name: str = "cli") -> None:
        super().__init__(name=name, description="CLI交互通道")

    def to_user_message(self, payload: dict) -> UserMessage:
        """把通道载荷标准化为 UserMessage。"""
        content = str(payload.get("content", "")).strip()
        if not content:
            raise ValueError("content 不能为空")
        return UserMessage(content=content)

    def from_ai_response(self, content: str) -> dict:
        """把模型文本包装为通道响应结构。"""
        return {"reply": content}


