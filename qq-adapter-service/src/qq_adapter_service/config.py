from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping

import yaml

CONFIG_PATH = Path.cwd() / "qq-adapter-service" / "config.yml"


@dataclass(frozen=True)
class ServerSettings:
    host: str
    port: int
    log_level: str


@dataclass(frozen=True)
class AdapterSettings:
    downstream_ws_url: str
    downstream_ws_token: str
    downstream_ws_open_timeout_seconds: float
    downstream_ws_reconnect_interval_seconds: float
    onebot_ws_action_timeout_seconds: float


@dataclass(frozen=True)
class McpSettings:
    base_url: str
    timeout_seconds: float
    log_level: str


@dataclass(frozen=True)
class Settings:
    server: ServerSettings
    adapter: AdapterSettings
    mcp: McpSettings


def _load_config() -> dict[str, Any]:
    # QQ 适配器运行态只认服务目录内 YAML，避免同一字段被容器环境变量悄悄覆盖。
    try:
        payload = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"配置文件不存在: {CONFIG_PATH}") from exc
    except yaml.YAMLError as exc:
        raise ValueError(f"配置文件格式错误: {CONFIG_PATH}") from exc

    if payload is None:
        return {}
    if not isinstance(payload, dict):
        raise ValueError(f"配置文件顶层必须是 mapping: {CONFIG_PATH}")
    return payload


def _section(data: Mapping[str, Any], name: str) -> Mapping[str, Any]:
    value = data.get(name)
    if not isinstance(value, dict):
        raise ValueError(f"配置缺少 `{name}` 节点: {CONFIG_PATH}")
    return value


def _require_str(section: Mapping[str, Any], key: str) -> str:
    value = section.get(key)
    if not isinstance(value, str):
        raise ValueError(f"配置项 `{key}` 必须是字符串: {CONFIG_PATH}")
    return value


def _require_int(section: Mapping[str, Any], key: str) -> int:
    value = section.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"配置项 `{key}` 必须是整数: {CONFIG_PATH}")
    return value


def _require_float(section: Mapping[str, Any], key: str) -> float:
    value = section.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"配置项 `{key}` 必须是数字: {CONFIG_PATH}")
    return float(value)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    data = _load_config()
    server = _section(data, "server")
    adapter = _section(data, "adapter")
    mcp = _section(data, "mcp")

    return Settings(
        server=ServerSettings(
            host=_require_str(server, "host"),
            port=_require_int(server, "port"),
            log_level=_require_str(server, "log_level"),
        ),
        adapter=AdapterSettings(
            downstream_ws_url=_require_str(adapter, "downstream_ws_url"),
            downstream_ws_token=_require_str(adapter, "downstream_ws_token"),
            downstream_ws_open_timeout_seconds=_require_float(
                adapter, "downstream_ws_open_timeout_seconds"
            ),
            downstream_ws_reconnect_interval_seconds=_require_float(
                adapter, "downstream_ws_reconnect_interval_seconds"
            ),
            onebot_ws_action_timeout_seconds=_require_float(
                adapter, "onebot_ws_action_timeout_seconds"
            ),
        ),
        mcp=McpSettings(
            base_url=_require_str(mcp, "base_url"),
            timeout_seconds=_require_float(mcp, "timeout_seconds"),
            log_level=_require_str(mcp, "log_level"),
        ),
    )
