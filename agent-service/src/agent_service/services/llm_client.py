from typing import List, cast

from openai import OpenAI
from openai import APIStatusError

from ..logger import get_logger, log_error, log_exception
from .types import Message, LlmResponse, ToolCall


class LlmClient:
    def __init__(self, model_name: str, api_key: str, base_url: str):
        self._logger = get_logger("llm_client")
        self._model_name = model_name
        self._client = OpenAI(api_key=api_key, base_url=base_url)

    def generate(
        self,
        messages: List[Message],
        tools_schema: List,
        temperature: float = 0.7,
    ) -> LlmResponse:
        try:
            request_payload = {
                "messages": messages,
                "model": self._model_name,
                "temperature": temperature,
            }
            # 部分 OpenAI 兼容网关在 tools 为空时会拒绝 tool_choice 字段，
            # 这里按是否存在工具动态下发参数，避免无工具场景触发 400。
            if tools_schema:
                request_payload["tool_choice"] = "auto"
                request_payload["tools"] = tools_schema

            response = self._client.chat.completions.create(**request_payload)

            content = response.choices[0].message.content or ""
            tool_calls = cast(
                List[ToolCall], response.choices[0].message.tool_calls or []
            )
            finish_reason = response.choices[0].finish_reason

            return LlmResponse(
                content=content, tool_calls=tool_calls, finish_reason=finish_reason
            )
        except APIStatusError as e:
            log_error(
                self._logger,
                "llm.request_failed",
                status_code=e.status_code,
                model=self._model_name,
                detail=e.response.text if e.response is not None else str(e),
            )
            raise RuntimeError(
                f"LLM 请求失败: status={e.status_code}, detail={e.response.text if e.response is not None else e}"
            )
        except Exception as e:
            log_exception(
                self._logger,
                "llm.request_failed",
                model=self._model_name,
                error=e,
            )
            raise RuntimeError(f"LLM 请求失败: {e}")
