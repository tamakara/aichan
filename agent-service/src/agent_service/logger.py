import logging
from time import perf_counter
from typing import Any


LOGGER_NAME_PREFIX = "agent_service"
EVENT_LABELS = {
    "agent_app.boot": "服务初始化",
    "agent_app.ready": "服务启动完成",
    "agent.chat_received": "收到会话请求",
    "agent.session_bound": "会话上下文绑定完成",
    "agent.chat_completed": "会话处理完成",
    "agent.chat_failed": "会话处理失败",
    "agent_core.run_started": "Agent 执行开始",
    "agent_core.llm_responded": "模型响应返回",
    "agent_core.tool_called": "工具调用完成",
    "agent_core.run_completed": "Agent 执行完成",
    "mcp.registered": "MCP 工具注册完成",
    "mcp.tool_called": "MCP 工具调用完成",
    "mcp.schema_sanitized": "MCP Schema 兼容性清洗",
    "llm.request_failed": "模型请求失败",
}
FIELD_LABELS = {
    "session_id": "会话",
    "turn": "轮次",
    "tool_name": "工具",
    "status": "状态",
    "model": "模型",
    "max_turns": "最大轮次",
    "finish_reason": "结束原因",
    "elapsed_ms": "耗时",
    "reply_len": "回复长度",
    "user_message_len": "用户消息长度",
    "tool_count": "工具数",
    "created_new_session": "新建会话",
    "mcp_sse_url": "MCP地址",
    "removed_keys": "移除字段",
    "status_code": "状态码",
    "detail": "详情",
}
HIGHLIGHT_KEYS = (
    "session_id",
    "turn",
    "tool_name",
    "status",
    "elapsed_ms",
    "finish_reason",
    "status_code",
)


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    _silence_framework_loggers()


def get_logger(component: str) -> logging.Logger:
    return logging.getLogger(f"{LOGGER_NAME_PREFIX}.{component}")


def start_timer() -> float:
    return perf_counter()


def elapsed_ms(started_at: float) -> int:
    return int((perf_counter() - started_at) * 1000)


def log_info(logger: logging.Logger, event: str, **fields: Any) -> None:
    logger.info(_build_log_message(event, fields))


def log_warning(logger: logging.Logger, event: str, **fields: Any) -> None:
    logger.warning(_build_log_message(event, fields))


def log_error(logger: logging.Logger, event: str, **fields: Any) -> None:
    logger.error(_build_log_message(event, fields))


def log_exception(logger: logging.Logger, event: str, **fields: Any) -> None:
    logger.exception(_build_log_message(event, fields))


def _build_log_message(event: str, fields: dict[str, Any]) -> str:
    summary = _build_human_summary(event, fields)
    structured = _build_structured_fields(fields)

    if structured:
        return f"{summary} | event={event} {structured}"
    return f"{summary} | event={event}"


def _build_human_summary(event: str, fields: dict[str, Any]) -> str:
    label = EVENT_LABELS.get(event, event)
    if not fields:
        return label

    highlights: list[str] = []
    for key in HIGHLIGHT_KEYS:
        if key in fields:
            value = fields[key]
            label_text = FIELD_LABELS.get(key, key)
            highlights.append(f"{label_text}={_format_field_value_with_unit(key, value)}")

    if not highlights:
        return label
    return f"{label}（{', '.join(highlights)}）"


def _build_structured_fields(fields: dict[str, Any]) -> str:
    # 保留结构化 key=value，便于 grep/聚合查询；同时在摘要层提供可读语义。
    field_parts = [f"{key}={_format_field_value(value)}" for key, value in fields.items()]
    return " ".join(field_parts)


def _format_field_value(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value).replace("\n", "\\n")


def _format_field_value_with_unit(key: str, value: Any) -> str:
    rendered = _format_field_value(value)
    if key == "elapsed_ms":
        return f"{rendered}ms"
    return rendered


def _silence_framework_loggers() -> None:
    # 运行时日志统一收口到 agent_service.*，屏蔽 FastAPI/Uvicorn 框架噪声避免污染诊断信号。
    framework_loggers = ("uvicorn", "uvicorn.error", "uvicorn.access", "fastapi")
    for logger_name in framework_loggers:
        framework_logger = logging.getLogger(logger_name)
        framework_logger.handlers.clear()
        framework_logger.propagate = False
        framework_logger.setLevel(logging.CRITICAL + 1)
