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
        message_dict: dict[str, object] = {"role": role, "content": content}
        if role == "assistant" and tool_calls is not None:
            message_dict["tool_calls"] = tool_calls
        if role == "tool" and tool_call_id is not None:
            message_dict["tool_call_id"] = tool_call_id

        self._messages.append(cast(Message, message_dict))

    def get_messages(self) -> List[Message]:
        return self._messages
