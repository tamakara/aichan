from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping

import yaml

CONFIG_PATH = Path.cwd() / "hub-service" / "config.yml"


@dataclass(frozen=True)
class ServerSettings:
    host: str
    port: int
    log_level: str


@dataclass(frozen=True)
class HubSettings:
    agent_url: str
    qq_adapter_url: str
    max_turns: int


@dataclass(frozen=True)
class Settings:
    server: ServerSettings
    hub: HubSettings


def _load_config() -> dict[str, Any]:
    # 中枢配置只允许来自服务目录内的 YAML，避免启动参数和部署环境各自维护一套真相。
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


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    data = _load_config()
    server = _section(data, "server")
    hub = _section(data, "hub")

    return Settings(
        server=ServerSettings(
            host=_require_str(server, "host"),
            port=_require_int(server, "port"),
            log_level=_require_str(server, "log_level"),
        ),
        hub=HubSettings(
            agent_url=_require_str(hub, "agent_url"),
            qq_adapter_url=_require_str(hub, "qq_adapter_url"),
            max_turns=_require_int(hub, "max_turns"),
        ),
    )
