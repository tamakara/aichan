from __future__ import annotations

import json
import re
from collections.abc import Awaitable, Callable
from typing import Any

import mcp.types as mcp_types
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field, create_model

# 工具执行器约定：
# - 入参：工具参数字典；
# - 出参：最终可读字符串（供 Agent 直接消费）。
AsyncToolExecutor = Callable[[dict[str, Any]], Awaitable[str]]


def build_mcp_structured_tool(
    *,
    wrapped_name: str,
    server_name: str,
    source_tool: mcp_types.Tool,
    async_executor: AsyncToolExecutor,
) -> StructuredTool:
    """
    将 MCP Tool 元数据包装成 LangChain StructuredTool。

    包装后的工具为异步执行形态，供 Agent 的 async 链路使用。

    参数说明：
    - wrapped_name: 对外暴露的包装工具名（server__tool）；
    - server_name: 仅用于补充描述和日志可观测性；
    - source_tool: MCP 原始工具定义；
    - async_executor: 实际调用逻辑，由外层注入。
    """
    # 基于 MCP 提供的 JSON Schema 生成入参模型。
    args_schema = build_args_schema(
        tool_name=wrapped_name,
        input_schema=source_tool.inputSchema,
    )
    # 描述里附带来源信息，便于排查工具归属。
    description = _build_tool_description(
        server_name=server_name,
        source_tool=source_tool,
    )

    async def _async_tool_callable(**kwargs: Any) -> str:
        # LangChain 以 kwargs 形式传参，这里统一转回 dict。
        return await async_executor(kwargs)

    # 仅注册 coroutine，保持全异步调用链。
    return StructuredTool.from_function(
        name=wrapped_name,
        description=description,
        args_schema=args_schema,
        coroutine=_async_tool_callable,
    )


def build_args_schema(
    *,
    tool_name: str,
    input_schema: dict[str, Any] | None,
) -> type[BaseModel]:
    """
    基于 MCP Tool 的 JSON Schema 动态构建 Pydantic 参数模型。

    约束策略：
    - 仅处理对象型 schema；
    - 非法 Python 字段名直接跳过；
    - 未识别类型回退为 Any。
    """
    # 不是对象字典时，退化为“无参数模型”。
    if not isinstance(input_schema, dict):
        return _create_empty_args_model(tool_name)

    # JSON Schema 仅接受 properties 字段作为参数源。
    properties = input_schema.get("properties")
    if not isinstance(properties, dict):
        return _create_empty_args_model(tool_name)

    # required 仅在 list 形态下生效，其他形态视为“全部可选”。
    raw_required = input_schema.get("required")
    required_fields = set(raw_required) if isinstance(raw_required, list) else set()
    model_fields: dict[str, tuple[Any, Any]] = {}

    for raw_field_name, raw_field_schema in properties.items():
        # 统一字段名清洗，避免空格/类型问题。
        field_name = str(raw_field_name).strip()
        if not _is_valid_python_field_name(field_name):
            # 非法字段名直接忽略，避免污染 Pydantic 模型。
            continue

        # 非 dict 形态字段定义降级为空定义，类型映射后会退化为 Any。
        field_schema = raw_field_schema if isinstance(raw_field_schema, dict) else {}
        field_type = json_schema_type_to_python(field_schema)
        field_description = field_schema.get("description")
        description_value = (
            str(field_description)
            if isinstance(field_description, str) and field_description.strip()
            else None
        )

        if field_name in required_fields:
            # 必填参数使用 `default=...` 表达必须传入。
            model_fields[field_name] = (
                field_type,
                Field(default=..., description=description_value),
            )
        else:
            # 非必填参数统一允许 None，减少模型校验误报。
            model_fields[field_name] = (
                field_type | None,
                Field(default=None, description=description_value),
            )

    if not model_fields:
        # 所有字段都被过滤后，同样退化为无参数模型。
        return _create_empty_args_model(tool_name)

    model_name = f"{_to_model_name(tool_name)}Args"
    # 动态创建专属模型，便于工具级别校验和提示。
    return create_model(model_name, **model_fields)


def parse_call_tool_result(result: mcp_types.CallToolResult) -> str:
    """
    解析 MCP call_tool 返回值并输出统一字符串。

    解析规则：
    1. 优先拼接全部 TextContent；
    2. 非文本内容转为可读占位文本；
    3. isError=True 时抛出异常。
    """
    # 文本内容优先：这是最可读、最直接的结果表达。
    text_segments: list[str] = []

    # 非文本内容转占位文本，作为兜底展示。
    fallback_segments: list[str] = []

    for content in result.content:
        if isinstance(content, mcp_types.TextContent):
            text_segments.append(content.text)
            continue
        fallback_segments.append(_render_non_text_content(content))

    # 第一优先级：拼接有效文本段。
    response_text = "\n".join(segment for segment in text_segments if segment.strip())
    if not response_text:
        # 第二优先级：拼接非文本占位段。
        response_text = "\n".join(segment for segment in fallback_segments if segment.strip())

    if not response_text:
        if result.structuredContent is not None:
            # 第三优先级：序列化 structuredContent。
            response_text = json.dumps(result.structuredContent, ensure_ascii=False)
        else:
            # 最后兜底：固定提示语。
            response_text = "[MCP Tool] 未返回可读文本内容。"

    if result.isError:
        # MCP 明确标记错误时，上抛并交给调用方统一处理。
        raise RuntimeError(response_text)

    return response_text


def json_schema_type_to_python(field_schema: dict[str, Any]) -> Any:
    """
    将 JSON Schema 类型映射到 Python 类型。

    注意：
    - 对联合类型（list）仅选择首个非 null 类型；
    - 未知类型统一回退为 Any，保证工具可注册。
    """
    raw_type = field_schema.get("type")

    if isinstance(raw_type, list):
        # 处理如 ["string", "null"] 的联合声明，优先取首个非 null。
        non_null = [item for item in raw_type if item != "null"]
        raw_type = non_null[0] if non_null else "null"

    if raw_type == "string":
        return str
    if raw_type == "integer":
        return int
    if raw_type == "number":
        return float
    if raw_type == "boolean":
        return bool
    if raw_type == "array":
        return list[Any]
    if raw_type == "object":
        return dict[str, Any]
    return Any


def _build_tool_description(*, server_name: str, source_tool: mcp_types.Tool) -> str:
    """构建带来源标识的工具描述文本。"""
    raw_description = source_tool.description or "MCP 动态工具"
    return (
        f"{raw_description}\n\n"
        f"[MCP 来源] server={server_name}, tool={source_tool.name}"
    )


def _render_non_text_content(content: mcp_types.ContentBlock) -> str:
    """把非文本内容渲染为可读占位字符串。"""
    if isinstance(content, mcp_types.ImageContent):
        return f"[image content] mimeType={content.mimeType}"

    if isinstance(content, mcp_types.AudioContent):
        return f"[audio content] mimeType={content.mimeType}"

    if isinstance(content, mcp_types.ResourceLink):
        return f"[resource link] uri={content.uri}"

    if isinstance(content, mcp_types.EmbeddedResource):
        resource = content.resource
        if isinstance(resource, mcp_types.TextResourceContents):
            return f"[embedded text resource] uri={resource.uri}"
        if isinstance(resource, mcp_types.BlobResourceContents):
            return f"[embedded blob resource] uri={resource.uri}, mimeType={resource.mimeType}"
        return "[embedded resource]"

    return "[unknown content block]"


def _is_valid_python_field_name(field_name: str) -> bool:
    """判断字段名是否可作为 Python 标识符。"""
    if not field_name:
        return False
    if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", field_name):
        return False
    return True


def _to_model_name(tool_name: str) -> str:
    """
    将工具名转换为合法且稳定的模型类名。

    规则：
    - 非字母数字下划线字符替换为下划线；
    - 空名回退为 `McpTool`；
    - 数字开头时追加 `Tool_` 前缀；
    - 最终转为 PascalCase。
    """
    clean_name = re.sub(r"[^A-Za-z0-9_]+", "_", tool_name).strip("_")
    if not clean_name:
        clean_name = "McpTool"
    if clean_name[0].isdigit():
        clean_name = f"Tool_{clean_name}"
    return "".join(part.capitalize() for part in clean_name.split("_"))


def _create_empty_args_model(tool_name: str) -> type[BaseModel]:
    """创建“无参数工具”对应的空模型。"""
    model_name = f"{_to_model_name(tool_name)}EmptyArgs"
    return create_model(model_name)
