from __future__ import annotations

import json
from typing import Annotated, Callable, TypedDict

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.tools import BaseTool
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

from core.logger import logger, render_panel


class RuntimeState(TypedDict):
    """
    AgentRuntime 图状态。

    字段说明：
    - messages: 对话消息轨迹，随图节点推进持续追加。
    """

    messages: Annotated[list[BaseMessage], add_messages]


class ReasoningGraphRunner:
    """
    负责构建并执行 reason -> tools -> reason 图流程。

    该类只做图层职责，不处理唤醒循环与规则审计。
    """

    def __init__(self, *, llm_factory: Callable[[], BaseChatModel]) -> None:
        # LLM 工厂由外层注入，便于切换模型实现。
        self._llm_factory = llm_factory

    async def run_cycle(
        self,
        *,
        tools: list[BaseTool],
        prompt_messages: list[BaseMessage],
    ) -> list[BaseMessage]:
        """执行一轮图推理并返回最终消息轨迹。"""
        # 每轮都基于当前工具快照重建图，避免工具绑定过期。
        graph = self._build_graph(tools=tools)
        final_state: dict[str, list[BaseMessage]] | None = None

        # astream 会输出过程状态；最后一次即最终状态。
        async for state in graph.astream({"messages": prompt_messages}, stream_mode="values"):
            final_state = state

        if final_state is None:
            raise RuntimeError("推理流程未产出任何状态")
        return final_state["messages"]

    def _build_graph(self, tools: list[BaseTool]):
        """构建 reason -> tools -> reason 循环图。"""
        llm = self._llm_factory()
        llm_with_tools = llm.bind_tools(tools) if tools else llm
        workflow = StateGraph(RuntimeState)

        async def reason_node(state: RuntimeState):
            # 输出完整输入上下文，便于调试模型决策链。
            logger.info(
                "🧾 [AgentRuntime] LLM 输入:\n{}",
                render_panel(_render_full_prompt(state["messages"])),
            )
            response = await llm_with_tools.ainvoke(state["messages"])
            if isinstance(response, AIMessage) and response.tool_calls:
                # 若模型请求工具，记录具体工具名。
                called_tools = [
                    str(item.get("name", "<unknown_tool>"))
                    for item in response.tool_calls
                ]
                logger.info("🛠 [AgentRuntime] LLM 请求工具: {}", ", ".join(called_tools))
            return {"messages": [response]}

        def route(state: RuntimeState):
            # 若最后消息含 tool_calls，则流向 tools 节点继续循环；否则结束。
            last_message = state["messages"][-1]
            if isinstance(last_message, AIMessage) and last_message.tool_calls:
                return "tools"
            return END

        workflow.add_node("reason", reason_node)
        workflow.set_entry_point("reason")
        workflow.add_conditional_edges("reason", route)
        workflow.add_node("tools", ToolNode(tools))
        workflow.add_edge("tools", "reason")
        return workflow.compile()


def _serialize_message_content(content: object) -> str:
    """将消息内容稳定序列化为日志文本。"""
    if isinstance(content, str):
        return content

    try:
        return json.dumps(content, ensure_ascii=False, indent=2)
    except TypeError:
        # 不能 JSON 化时回退 repr，保证日志不会失败。
        return repr(content)


def _render_full_prompt(messages: list[BaseMessage]) -> str:
    """渲染完整 prompt 文本，便于审计输入与工具请求。"""
    sections: list[str] = []
    for index, message in enumerate(messages, start=1):
        header = f"[{index}] role={message.type}"
        if message.id:
            header = f"{header} id={message.id}"

        section = f"{header}\n{_serialize_message_content(message.content)}"
        if isinstance(message, AIMessage) and message.tool_calls:
            # 带工具调用的 AI 消息追加 tool_calls 结构体明细。
            section = (
                f"{section}\n\n[tool_calls]\n"
                f"{json.dumps(message.tool_calls, ensure_ascii=False, indent=2)}"
            )
        sections.append(section)

    return "\n\n".join(sections)
