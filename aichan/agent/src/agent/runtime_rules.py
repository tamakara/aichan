from __future__ import annotations

import json
import re

from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.tools import BaseTool


class RuntimeRulesAuditor:
    """
    负责 Tool-as-Action 的运行时规则审计。

    审计内容：
    1. 首步必须全量调用 fetch_unread_messages；
    2. 识别 send 工具调用集合；
    3. 提取内心独白文本用于日志。
    """

    _SERVER_SEND_TOOL_PATTERN = re.compile(r".*__send(?:_[A-Za-z0-9_]+)?_message$")
    _PLAIN_SEND_TOOL_PATTERN = re.compile(r"^send(?:_[A-Za-z0-9_]+)?_message$")
    _SERVER_FETCH_TOOL_PATTERN = re.compile(r".*__fetch_unread_messages$")
    _PLAIN_FETCH_TOOL_PATTERN = re.compile(r"^fetch_unread_messages$")

    def collect_required_fetch_tools(self, tools: list[BaseTool]) -> set[str]:
        """从工具列表中提取本轮必须首步调用的 fetch 工具名集合。"""
        required: set[str] = set()
        for tool in tools:
            tool_name = str(getattr(tool, "name", "")).strip()
            if not tool_name:
                continue
            if self._SERVER_FETCH_TOOL_PATTERN.match(tool_name):
                required.add(tool_name)
                continue
            if self._PLAIN_FETCH_TOOL_PATTERN.match(tool_name):
                required.add(tool_name)
        return required

    def ensure_first_step_fetch(
        self,
        *,
        messages: list[BaseMessage],
        required_fetch_tools: set[str],
    ) -> None:
        """
        校验“首步全量 fetch”硬约束。

        失败即抛出 RuntimeError，由上层中断本轮执行。
        """
        if not required_fetch_tools:
            raise RuntimeError("未发现任何 fetch_unread_messages 工具，无法执行唤醒流程")

        first_tool_call_names = self.first_tool_call_names(messages)
        if not first_tool_call_names:
            raise RuntimeError(
                "首次工具调用为空，未满足全量 fetch_unread_messages 约束，"
                f"required={sorted(required_fetch_tools)}"
            )

        # 首条工具调用必须覆盖全部 required_fetch_tools。
        first_tool_call_set = {name for name in first_tool_call_names if name}
        missing_tools = sorted(required_fetch_tools.difference(first_tool_call_set))
        if missing_tools:
            raise RuntimeError(
                "首次工具调用未覆盖全部 fetch_unread_messages 工具，"
                f"missing={missing_tools}, calls={first_tool_call_names}"
            )

    def collect_send_tool_calls(self, messages: list[BaseMessage]) -> list[str]:
        """提取所有 send_message / send_{channel}_message 工具调用名。"""
        send_tools: list[str] = []
        for message in messages:
            if not isinstance(message, AIMessage):
                continue
            for tool_call in message.tool_calls:
                tool_name = str(tool_call.get("name", "")).strip()
                # 支持 server__send_* 与 send_* 两种命名形态。
                if self._SERVER_SEND_TOOL_PATTERN.match(tool_name):
                    send_tools.append(tool_name)
                    continue
                if self._PLAIN_SEND_TOOL_PATTERN.match(tool_name):
                    send_tools.append(tool_name)
        return send_tools

    def first_tool_call_names(self, messages: list[BaseMessage]) -> list[str]:
        """获取第一条带工具调用 AI 消息中的全部工具名。"""
        for message in messages:
            if not isinstance(message, AIMessage):
                continue
            if not message.tool_calls:
                continue
            return [str(tool.get("name", "")).strip() for tool in message.tool_calls]
        return []

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
