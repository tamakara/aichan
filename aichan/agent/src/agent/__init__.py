"""
agent 包导出入口。

该包封装了“唤醒 -> 推理 -> 工具执行 -> 规则审计”的运行时闭环，
对外只暴露 `AgentRuntime`，隐藏内部图执行与调度实现细节。
"""

from agent.agent_runtime import AgentRuntime

__all__ = ["AgentRuntime"]
