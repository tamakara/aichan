import json

from ..logger import (
    elapsed_ms,
    get_logger,
    log_exception,
    log_info,
    start_timer,
)
from .llm_client import LlmClient
from .mcp_gateway import McpGateway
from .types.session import Session


class AgentCore:
    def __init__(
        self,
        llm_client: LlmClient,
        mcp_gateway: McpGateway,
        max_turns: int,
    ):
        self._logger = get_logger("agent_core")
        self._llm_client = llm_client
        self._mcp_gateway = mcp_gateway
        self._max_turns = max_turns

    def run(self, session: Session, user_message: str) -> str:
        run_started_at = start_timer()
        session_id = session.get_session_id()
        log_info(
            self._logger,
            "agent_core.run_started",
            session_id=session_id,
            max_turns=self._max_turns,
            user_message_len=len(user_message),
        )
        session.add_message(role="user", content=user_message)

        for turn_idx in range(self._max_turns):
            turn_no = turn_idx + 1
            turn_started_at = start_timer()
            llm_response = self._llm_client.generate(
                messages=session.get_messages(),
                tools_schema=self._mcp_gateway.get_tools_schema(),
            )
            log_info(
                self._logger,
                "agent_core.llm_responded",
                session_id=session_id,
                turn=turn_no,
                finish_reason=llm_response.finish_reason,
                elapsed_ms=elapsed_ms(turn_started_at),
            )
            session.add_message(
                role="assistant",
                content=llm_response.content,
                tool_calls=llm_response.tool_calls,
            )

            if llm_response.finish_reason != "tool_calls":
                if llm_response.finish_reason == "stop":
                    log_info(
                        self._logger,
                        "agent_core.run_completed",
                        session_id=session_id,
                        turn=turn_no,
                        elapsed_ms=elapsed_ms(run_started_at),
                    )
                    return llm_response.content
                raise RuntimeError(
                    f"LLM response ended with unexpected reason: {llm_response.finish_reason}"
                )

            for tool_call in llm_response.tool_calls:
                tool_call_id = tool_call.id
                tool_name = tool_call.function.name
                tool_args_str = tool_call.function.arguments
                tool_started_at = start_timer()

                try:
                    tool_args = (
                        json.loads(tool_args_str)
                        if isinstance(tool_args_str, str)
                        else tool_args_str
                    )
                    tool_call_result = self._mcp_gateway.call_tool(
                        tool_name=tool_name, tool_args=tool_args
                    )
                    log_info(
                        self._logger,
                        "agent_core.tool_called",
                        session_id=session_id,
                        turn=turn_no,
                        tool_name=tool_name,
                        status="ok",
                        elapsed_ms=elapsed_ms(tool_started_at),
                    )
                except Exception as e:
                    log_exception(
                        self._logger,
                        "agent_core.tool_called",
                        session_id=session_id,
                        turn=turn_no,
                        tool_name=tool_name,
                        status="failed",
                        elapsed_ms=elapsed_ms(tool_started_at),
                    )
                    tool_call_result = json.dumps(
                        {"error": f"tool `{tool_name}` failed: {e}"},
                        ensure_ascii=False,
                    )

                session.add_message(
                    role="tool", content=tool_call_result, tool_call_id=tool_call_id
                )

        raise RuntimeError(
            f"Agent failed to complete the task within {self._max_turns} turns of interaction."
        )
