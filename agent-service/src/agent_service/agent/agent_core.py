import json

from .llm_client import LlmClient
from .messages_list import MessageList
from .mcp_gateway import McpGateway


class AgentCore:
    def __init__(
        self,
        llm_client: LlmClient,
        messages_list: MessageList,
        mcp_gateway: McpGateway,
    ):
        self._llm_client = llm_client
        self._messages_list = messages_list
        self._mcp_gateway = mcp_gateway

    def chat(self, user_message: str, max_turns: int = 10) -> str:
        self._messages_list.add_message(role="user", content=user_message)

        for _ in range(max_turns):
            llm_response = self._llm_client.generate(
                messages=self._messages_list.get_messages(),
                tools_schema=self._mcp_gateway.get_tools_schema(),
            )
            self._messages_list.add_message(
                role="assistant",
                content=llm_response.content,
                tool_calls=llm_response.tool_calls,
            )

            if llm_response.finish_reason != "tool_calls":
                if llm_response.finish_reason == "stop":
                    return llm_response.content
                raise RuntimeError(
                    f"LLM response ended with unexpected reason: {llm_response.finish_reason}"
                )

            for tool_call in llm_response.tool_calls:
                tool_call_id = tool_call.id
                tool_name = tool_call.function.name
                tool_args_str = tool_call.function.arguments

                try:
                    tool_args = (
                        json.loads(tool_args_str)
                        if isinstance(tool_args_str, str)
                        else tool_args_str
                    )
                    tool_call_result = self._mcp_gateway.call_tool(
                        tool_name=tool_name, tool_args=tool_args
                    )
                except Exception as e:
                    tool_call_result = json.dumps(
                        {"error": f"tool `{tool_name}` failed: {e}"},
                        ensure_ascii=False,
                    )

                self._messages_list.add_message(
                    role="tool", content=tool_call_result, tool_call_id=tool_call_id
                )

        raise RuntimeError(
            f"Agent failed to complete the task within {max_turns} turns of interaction."
        )
