from typing import List, cast

from openai import OpenAI

from .types import Message, LlmResponse, ToolCall


class LlmClient:
    def __init__(self, model_name: str, api_key: str, base_url: str):
        self._model_name = model_name
        self._client = OpenAI(api_key=api_key, base_url=base_url)

    def generate(
        self,
        messages: List[Message],
        tools_schema: List,
        temperature: float = 0.7,
    ) -> LlmResponse:
        try:
            response = self._client.chat.completions.create(
                messages=messages,
                model=self._model_name,
                tool_choice="auto",
                tools=tools_schema,
                temperature=temperature,
            )

            content = response.choices[0].message.content or ""
            tool_calls = cast(
                List[ToolCall], response.choices[0].message.tool_calls or []
            )
            finish_reason = response.choices[0].finish_reason

            return LlmResponse(
                content=content, tool_calls=tool_calls, finish_reason=finish_reason
            )
        except Exception as e:
            raise RuntimeError(f"LLM 请求失败: {e}")
