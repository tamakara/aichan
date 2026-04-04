from __future__ import annotations

import sys
from pathlib import Path

from langchain_core.messages import AIMessage

# 让测试在未安装 workspace 包时可导入本地源码。
CURRENT_DIR = Path(__file__).resolve()
AGENT_SRC = CURRENT_DIR.parents[1] / "src"
CORE_SRC = CURRENT_DIR.parents[2] / "core" / "src"
MCP_HUB_SRC = CURRENT_DIR.parents[2] / "mcp_hub" / "src"
for path in (AGENT_SRC, CORE_SRC, MCP_HUB_SRC):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from agent.wakeup_runtime import WakeUpAgentRuntime  # noqa: E402


def test_collect_send_tool_calls_filters_correctly() -> None:
    messages = [
        AIMessage(
            content="thinking",
            tool_calls=[
                {"name": "cli_mcp__fetch_unread_messages", "args": {}, "id": "t1"},
                {"name": "cli_mcp__send_cli_message", "args": {"text": "hi"}, "id": "t2"},
            ],
        ),
        AIMessage(
            content="thinking2",
            tool_calls=[
                {"name": "send_qq_message", "args": {"text": "hi2"}, "id": "t3"},
            ],
        ),
    ]

    send_calls = WakeUpAgentRuntime._collect_send_tool_calls(messages)  # noqa: SLF001
    assert send_calls == ["cli_mcp__send_cli_message", "send_qq_message"]


def test_first_step_fetch_detection() -> None:
    assert WakeUpAgentRuntime._is_first_step_fetch(  # noqa: SLF001
        ["cli_mcp__fetch_unread_messages"]
    )
    assert not WakeUpAgentRuntime._is_first_step_fetch(  # noqa: SLF001
        ["cli_mcp__send_cli_message"]
    )
