from __future__ import annotations

import asyncio
from typing import cast

from langchain_core.tools import StructuredTool, tool

from core.logger import logger
from nexus.hub import nexus_hub
from plugins.base import BasePlugin


class CLIChannelPlugin(BasePlugin):
    """CLI 双工插件：既可采集终端输入，也可作为终端输出工具。"""

    def __init__(self, name: str = "cli") -> None:
        super().__init__(name=name, description="CLI交互通道")
        self._is_listening = False

    async def start_listening(self) -> None:
        """
        作为生产者持续监听终端输入，并将信号推入 Nexus 队列。
        """
        self._is_listening = True
        logger.info("⌨️ [CLI] 输入监听已启动，直接在终端输入内容并回车发送。")

        while self._is_listening:
            try:
                raw_input = await asyncio.to_thread(input, "You> ")
            except (EOFError, KeyboardInterrupt):
                self._is_listening = False
                logger.info("🛑 [CLI] 输入监听已停止。")
                break

            content = raw_input.strip()
            if not content:
                continue

            await nexus_hub.push_signal(
                source=self.name,
                content=content,
                metadata={"channel": self.name},
            )

    def stop_listening(self) -> None:
        """停止 CLI 输入监听。"""
        self._is_listening = False

    def get_tool(self) -> StructuredTool:
        """
        作为消费者能力向大脑暴露终端操作工具。
        """

        @tool(f"{self.name}_terminal_io")
        def cli_terminal_io(action: str, content: str) -> str:
            """执行 CLI 终端动作。action 目前仅支持 print。"""
            if action != "print":
                return "unsupported action"

            print(f"AIChan> {content}")
            return "ok"

        return cast(StructuredTool, cli_terminal_io)
