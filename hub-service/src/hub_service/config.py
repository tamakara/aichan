from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # 统一走环境变量，避免代码默认值与部署配置产生双重真相。
    hub_host: str = Field(alias="HUB_HOST")
    hub_port: int = Field(alias="HUB_PORT")
    hub_log_level: str = Field(alias="HUB_LOG_LEVEL")

    hub_agent_service_url: str = Field(alias="HUB_AGENT_SERVICE_URL")
    hub_qq_adapter_api_url: str = Field(alias="HUB_QQ_ADAPTER_API_URL")
    hub_agent_max_turns: int = Field(alias="HUB_AGENT_MAX_TURNS")
    hub_http_timeout_seconds: float = Field(alias="HUB_HTTP_TIMEOUT_SECONDS")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    # 配置在进程内视为常量，缓存可减少重复解析开销。
    return Settings()
