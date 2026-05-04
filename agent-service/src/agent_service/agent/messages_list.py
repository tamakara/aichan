from typing import List, cast

from .types import Message, ToolCall


class MessageList:
    def __init__(self):
        self._messages: List[Message] = []

    def add_message(
        self,
        role: str,
        content: str,
        tool_calls: List[ToolCall] | None = None,
        tool_call_id: str | None = None,
    ) -> None:
        self._messages.append(
            cast(
                Message,
                {
                    "role": role,
                    "content": content,
                    "tool_calls": tool_calls,
                    "tool_call_id": tool_call_id,
                },
            )
        )

    def get_messages(self) -> List[Message]:
        return self._messages
