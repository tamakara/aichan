"""
项目配置读取模块。

设计目标：
1. 统一从环境变量加载配置，避免散落读取；
2. 使用 pydantic-settings 做类型校验与默认值管理；
3. 通过模块级 `settings` 单例供全局复用。
"""

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    """
    应用全局配置对象。

    所有字段统一从环境变量读取，避免在代码里硬编码敏感参数。
    """

    # 大模型访问配置（必填）
    llm_api_key: SecretStr
    llm_base_url: str
    llm_model_name: str
    llm_temperature: float

    # MCPHub 连接配置（逗号分隔多个 Streamable HTTP 端点）。
    mcp_server_endpoints: str
    # MCP 首次连接失败后的重试间隔（秒）。
    mcp_connect_retry_seconds: float = 2.0

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


# 模块级配置单例：项目其他位置直接 `from core.config import settings` 使用。
settings = AppSettings()
