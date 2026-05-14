from dataclasses import dataclass
from functools import lru_cache

from ..config import get_settings as get_adapter_settings


@dataclass(frozen=True)
class Settings:
    base_url: str
    timeout_seconds: float
    log_level: str


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    adapter_settings = get_adapter_settings().mcp
    return Settings(
        base_url=adapter_settings.base_url,
        timeout_seconds=adapter_settings.timeout_seconds,
        log_level=adapter_settings.log_level,
    )
