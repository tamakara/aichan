from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # 统一由环境变量提供运行参数，避免在代码中保留配置回退语义导致多真相。
    host: str
    port: int
    log_level: str

    downstream_ws_url: str
    downstream_ws_token: str
    downstream_ws_open_timeout_seconds: float
    downstream_ws_reconnect_interval_seconds: float
    onebot_ws_action_timeout_seconds: float

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    # 进程内配置视为常量，缓存后可避免重复解析与校验开销。
    return Settings()
