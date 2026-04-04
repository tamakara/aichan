from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

# 让测试在未安装包的情况下可直接导入本地源码。
CURRENT_DIR = Path(__file__).resolve()
CLI_SRC_ROOT = CURRENT_DIR.parents[1] / "src"
if str(CLI_SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(CLI_SRC_ROOT))

from cli.message_store import AsyncChatStore  # noqa: E402


@pytest.mark.asyncio
async def test_fetch_unread_messages_only_contains_user_messages() -> None:
    store = AsyncChatStore(default_channel="cli")

    await store.send_message(sender="user", text=" 你好 ")
    await store.send_message(sender="ai", text="你好，我看见你了")

    unread = await store.fetch_unread_messages()
    assert len(unread) == 1
    assert unread[0].channel == "cli"
    assert unread[0].sender == "user"
    assert unread[0].text == "你好"
    assert unread[0].message_id == 1

    drained_again = await store.fetch_unread_messages()
    assert drained_again == []


@pytest.mark.asyncio
async def test_fetch_unread_messages_drain_is_atomic_under_concurrency() -> None:
    store = AsyncChatStore(default_channel="cli")
    total = 50

    async def _send(index: int) -> None:
        await store.send_message(sender="user", text=f"msg-{index}")

    await asyncio.gather(*(_send(index) for index in range(total)))

    drained = await store.fetch_unread_messages()
    drained_ids = sorted(item.message_id for item in drained)
    assert len(drained) == total
    assert drained_ids == list(range(1, total + 1))

    assert await store.fetch_unread_messages() == []
