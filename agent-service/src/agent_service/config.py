from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # 默认值统一收口在仓库根目录 .env.example，避免代码与部署配置出现双重真相。
    model_name: str
    openai_api_key: str
    openai_base_url: str
    mcp_gateway_sse_url: str = "http://localhost:9000/sse"
    mcp_gateway_auth_token: str
    host: str = "localhost"
    port: int = 8000
    log_level: str

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="ignore"
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    # 设置在进程生命周期内固定，缓存后可避免重复解析环境变量与重复校验。
    return Settings()  # type: ignore
