import logging
from time import perf_counter
from typing import Any


LOGGER_NAME_PREFIX = "agent_service"


def configure_logging(log_level: str) -> None:
    level = getattr(logging, log_level.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


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
    if not fields:
        return event

    # 统一在 logger 层做 key=value 序列化，避免业务代码散落字符串拼接细节。
    field_parts = [f"{key}={_format_field_value(value)}" for key, value in fields.items()]
    return f"{event} {' '.join(field_parts)}"


def _format_field_value(value: Any) -> str:
    if value is None:
        return "null"
    return str(value).replace("\n", "\\n")
