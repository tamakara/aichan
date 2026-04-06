from __future__ import annotations

import json

from langchain_core.messages import AIMessage, BaseMessage


class RuntimeRulesAuditor:
    """
    负责运行时消息轨迹提取。

    职责边界：
    1. 提取本轮工具调用名称；
    2. 提取最终内心独白用于日志。
    """

    def collect_all_tool_calls(self, messages: list[BaseMessage]) -> list[str]:
        """提取本轮所有工具调用名称（按出现顺序）。"""
        called_tools: list[str] = []
        for message in messages:
            if not isinstance(message, AIMessage):
                continue
            for tool_call in message.tool_calls:
                tool_name = str(tool_call.get("name", "")).strip()
                if not tool_name:
                    continue
                called_tools.append(tool_name)
        return called_tools

    def extract_inner_monologue(self, messages: list[BaseMessage]) -> str:
        """提取最终 AI 文本输出作为内心独白。"""
        for message in reversed(messages):
            if not isinstance(message, AIMessage):
                continue
            if message.tool_calls:
                # 含工具调用的 AI 消息不是最终自然语言输出，跳过。
                continue
            content = message.content
            if isinstance(content, str) and content.strip():
                return content.strip()
            return self._serialize_message_content(content)
        return "[empty inner monologue]"

    @staticmethod
    def _serialize_message_content(content: object) -> str:
        """将消息内容稳定序列化为日志文本。"""
        if isinstance(content, str):
            return content

        try:
            return json.dumps(content, ensure_ascii=False, indent=2)
        except TypeError:
            return repr(content)
