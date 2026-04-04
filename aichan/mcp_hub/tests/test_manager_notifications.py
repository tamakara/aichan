from __future__ import annotations

import json
import sys
from pathlib import Path

import mcp.types as mcp_types
import pytest

# 让测试在未安装 workspace 包时可导入本地源码。
CURRENT_DIR = Path(__file__).resolve()
MCP_HUB_SRC = CURRENT_DIR.parents[1] / "src"
CORE_SRC = CURRENT_DIR.parents[2] / "core" / "src"
if str(MCP_HUB_SRC) not in sys.path:
    sys.path.insert(0, str(MCP_HUB_SRC))
if str(CORE_SRC) not in sys.path:
    sys.path.insert(0, str(CORE_SRC))

from mcp_hub.manager import MCPManager  # noqa: E402


@pytest.mark.asyncio
async def test_progress_notification_new_message_alert_into_wakeup_queue() -> None:
    manager = MCPManager(server_configs=[])
    notification = mcp_types.ServerNotification(
        mcp_types.ProgressNotification(
            params=mcp_types.ProgressNotificationParams(
                progressToken="new_message_alert",
                progress=1.0,
                message=json.dumps(
                    {
                        "event": "new_message_alert",
                        "channel": "cli",
                        "message_id": 12,
                    },
                    ensure_ascii=False,
                ),
            )
        )
    )

    await manager._handle_server_notification(  # noqa: SLF001
        server_name="cli_mcp",
        notification=notification,
    )
    event = manager._wakeup_queue.get_nowait()  # noqa: SLF001
    assert event.server_name == "cli_mcp"
    assert event.event == "new_message_alert"
    assert event.channel == "cli"
    assert event.message_id == 12


@pytest.mark.asyncio
async def test_non_alert_progress_notification_is_ignored() -> None:
    manager = MCPManager(server_configs=[])
    notification = mcp_types.ServerNotification(
        mcp_types.ProgressNotification(
            params=mcp_types.ProgressNotificationParams(
                progressToken="tool_progress",
                progress=0.5,
                message="{}",
            )
        )
    )

    await manager._handle_server_notification(  # noqa: SLF001
        server_name="cli_mcp",
        notification=notification,
    )
    assert manager._wakeup_queue.empty()  # noqa: SLF001
