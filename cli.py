from __future__ import annotations

from core.entities import AgentSignal, ChannelMessage
from core.logger import logger
from nexus.hub import NexusHub
from plugins.base import ChannelPlugin


def list_channel_messages(channel: ChannelPlugin, since_id: int) -> list[ChannelMessage]:
    return channel.list_messages(since_id=since_id)


def send_channel_message(channel: ChannelPlugin, role: str, content: str) -> None:
    channel.send_message(role=role, content=content)


def print_intro(channel_name: str) -> None:
    line = "=" * 64
    print(line)
    print("AIChan CLI")
    print(f"通道    : {channel_name}")
    print("提示    : 输入消息后回车发送，按 Ctrl+C 退出")
    print(line)


def print_channel_message(message: ChannelMessage) -> None:
    if message.role == "user":
        return

    speaker = "AIChan" if message.role == "assistant" else "System"
    content = message.content.strip()
    if not content:
        print(f"{speaker} > （空消息）")
    elif "\n" not in content:
        print(f"{speaker} > {content}")
    else:
        print(f"{speaker} >")
        for line in content.splitlines():
            print(f"  {line}")


def flush_channel_updates(
    channel: ChannelPlugin,
    since_id: int,
    show_empty: bool = False,
) -> tuple[int, int]:
    updates = list_channel_messages(channel=channel, since_id=since_id)
    if not updates:
        if show_empty:
            print("AIChan > （无新增消息）")
        return since_id, 0

    newest_id = since_id
    printed_count = 0
    for message in updates:
        newest_id = max(newest_id, message.message_id)
        if message.role != "user":
            print_channel_message(message)
            printed_count += 1

    return newest_id, printed_count


def run_cli_loop(hub: NexusHub, channel: ChannelPlugin) -> None:
    print_intro(channel_name=channel.name)
    last_seen_id = 0

    while True:
        last_seen_id, _ = flush_channel_updates(channel=channel, since_id=last_seen_id)
        try:
            text = input("\n你 > ").strip()
        except KeyboardInterrupt:
            print("\n\n已退出 AIChan CLI。")
            break
        except EOFError:
            print("\n\n输入流已结束，AIChan CLI 已退出。")
            break

        if not text:
            print("AIChan > 请输入内容后再发送。")
            continue

        try:
            send_channel_message(channel=channel, role="user", content=text)
            hub.push_signal(AgentSignal(channel=channel.name))
            print("AIChan > 已入队，处理中（可继续输入）")
            last_seen_id, printed_count = flush_channel_updates(
                channel=channel,
                since_id=last_seen_id,
            )
            if printed_count == 0:
                print("AIChan > （暂无新回复）")
        except KeyboardInterrupt:
            print("\n\n推理已中断，AIChan CLI 已退出。")
            break
        except Exception as exc:
            logger.exception("聊天处理失败：{}", exc)
            print(f"AIChan > 处理失败：{exc}")
