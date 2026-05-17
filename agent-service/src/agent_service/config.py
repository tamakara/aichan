from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping

import yaml
from pydantic import BaseModel, ConfigDict, StrictInt, StrictStr, ValidationError

CONFIG_PATH = Path.cwd() / "agent-service" / "config.yml"


class ServerSettings(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    host: StrictStr
    port: StrictInt
    log_level: StrictStr


class AgentSettings(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    model: StrictStr
    max_turns: StrictInt
    openai_api_key: StrictStr
    openai_base_url: StrictStr
    mcp_sse_url: StrictStr
    mcp_auth_token: StrictStr


class Settings(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    server: ServerSettings
    agent: AgentSettings


def _load_config() -> dict[str, Any]:
    # 配置只允许从服务自己的 YAML 文件读取，避免运行态再从环境变量分叉出另一套来源。
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


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    data: Mapping[str, Any] = _load_config()
    try:
        # 统一交给 Pydantic 做严格结构校验，避免手写字段检查逻辑散落且难维护。
        return Settings.model_validate(data)
    except ValidationError as exc:
        raise ValueError(f"配置校验失败: {CONFIG_PATH}\n{exc}") from exc
