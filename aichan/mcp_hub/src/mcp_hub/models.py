from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True, slots=True)
class MCPServerConfig:
    """
    MCP Server 连接配置。

    字段说明：
    - name: 服务别名，用于工具名前缀与日志定位。
    - endpoint_url: MCP Streamable HTTP 端点地址。
    - required: 是否为强依赖。强依赖连接失败会中断启动。
    """

    name: str
    endpoint_url: str
    required: bool = True

    def __post_init__(self) -> None:
        clean_name = self.name.strip()
        clean_url = self.endpoint_url.strip()
        if not clean_name:
            raise ValueError("MCPServerConfig.name 不能为空")
        if not clean_url:
            raise ValueError("MCPServerConfig.endpoint_url 不能为空")

        # dataclass(frozen=True) 场景下需要使用 object.__setattr__ 回填清洗后的值。
        object.__setattr__(self, "name", clean_name)
        object.__setattr__(self, "endpoint_url", clean_url)


@dataclass(frozen=True, slots=True)
class WakeupSignal:
    """
    MCP 通知转换后的统一唤醒信号。

    字段说明：
    - server_name: 来源 MCP Server 别名；
    - channel: 通道名；
    - reason: 唤醒原因（当前约定为 new_message）；
    - received_at: Hub 接收事件的 UTC ISO 时间；
    - raw_params: 原始通知参数，便于排障审计。
    """

    server_name: str
    channel: str
    reason: str
    received_at: str
    raw_params: dict[str, Any]

    @classmethod
    def build(
        cls,
        *,
        server_name: str,
        channel: str,
        reason: str,
        raw_params: dict[str, Any],
    ) -> "WakeupSignal":
        """创建包含当前 UTC 时间戳的 WakeupSignal。"""
        return cls(
            server_name=server_name,
            channel=channel,
            reason=reason,
            received_at=datetime.now(timezone.utc).isoformat(),
            raw_params=raw_params,
        )
