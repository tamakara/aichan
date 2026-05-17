from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping

from pydantic import BaseModel, ConfigDict, StrictInt, StrictStr, ValidationError, field_validator
import yaml

CONFIG_PATH = Path.cwd() / "qq-adapter-service" / "config.yml"


class ServerSettings(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    host: StrictStr
    port: StrictInt
    log_level: StrictStr


class AdapterSettings(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    downstream_ws_url: StrictStr
    downstream_ws_token: StrictStr
    downstream_ws_open_timeout_seconds: float
    downstream_ws_reconnect_interval_seconds: float
    onebot_ws_action_timeout_seconds: float

    @field_validator(
        "downstream_ws_open_timeout_seconds",
        "downstream_ws_reconnect_interval_seconds",
        "onebot_ws_action_timeout_seconds",
        mode="before",
    )
    @classmethod
    def _validate_numeric_timeout(cls, value: Any) -> float:
        # 兼容 YAML 中将超时写成整数的常见写法，同时拒绝 bool/字符串，避免隐式类型漂移。
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError("必须是数字")
        return float(value)


class McpSettings(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    base_url: StrictStr
    timeout_seconds: float
    log_level: StrictStr

    @field_validator("timeout_seconds", mode="before")
    @classmethod
    def _validate_timeout_seconds(cls, value: Any) -> float:
        # MCP 客户端超时必须是数值，允许整数配置但统一转换为 float。
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError("必须是数字")
        return float(value)


class Settings(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

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


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    data: Mapping[str, Any] = _load_config()
    try:
        # 配置结构统一走 Pydantic 校验，保证错误在服务启动时集中失败而非运行期分散暴露。
        return Settings.model_validate(data)
    except ValidationError as exc:
        raise ValueError(f"配置校验失败: {CONFIG_PATH}\n{exc}") from exc
