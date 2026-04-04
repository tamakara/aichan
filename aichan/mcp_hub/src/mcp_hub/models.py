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
    - sse_url: MCP SSE 隧道地址。
    - required: 是否为强依赖。强依赖连接失败会中断启动。
    """

    name: str
    sse_url: str
    required: bool = True

    def __post_init__(self) -> None:
        clean_name = self.name.strip()
        clean_url = self.sse_url.strip()
        if not clean_name:
            raise ValueError("MCPServerConfig.name 不能为空")
        if not clean_url:
            raise ValueError("MCPServerConfig.sse_url 不能为空")

        # dataclass(frozen=True) 场景下需要使用 object.__setattr__ 回填清洗后的值。
        object.__setattr__(self, "name", clean_name)
        object.__setattr__(self, "sse_url", clean_url)


@dataclass(frozen=True, slots=True)
class WakeUpEvent:
    """
    MCP 通知转换后的统一唤醒事件。

    字段说明：
    - server_name: 来源 MCP Server 别名；
    - event: 事件名（当前约定为 new_message_alert）；
    - channel: 通道名；
    - message_id: 触发唤醒的消息 ID；
    - received_at: Hub 接收事件的 UTC ISO 时间；
    - raw_payload: 原始通知载荷，便于排障审计。
    """

    server_name: str
    event: str
    channel: str
    message_id: int
    received_at: str
    raw_payload: dict[str, Any]

    @classmethod
    def build(
        cls,
        *,
        server_name: str,
        event: str,
        channel: str,
        message_id: int,
        raw_payload: dict[str, Any],
    ) -> "WakeUpEvent":
        """创建包含当前 UTC 时间戳的 WakeUpEvent。"""
        return cls(
            server_name=server_name,
            event=event,
            channel=channel,
            message_id=message_id,
            received_at=datetime.now(timezone.utc).isoformat(),
            raw_payload=raw_payload,
        )
