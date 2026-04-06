"""
AIChan 终端客户端入口。

模块职责：
1. 维护终端输入输出与富文本展示；
2. 通过 HTTP 与 CLI Gateway 进行消息收发；
3. 通过 SSE 在后台持续拉取并展示增量消息；
4. 负责本地消息状态去重与断点续传游标维护。
"""

from __future__ import annotations

import argparse
import html
import threading
import time
from urllib.parse import urlencode

import httpx
from httpx_sse import connect_sse
from pydantic import BaseModel

from prompt_toolkit import PromptSession
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.patch_stdout import patch_stdout
from prompt_toolkit.shortcuts import print_formatted_text
from prompt_toolkit.styles import Style

# ==========================================
# ⚙️ 全局默认配置常量
# ==========================================
DEFAULT_SERVER_URL = "http://localhost:9000"

# 网络请求超时时间（秒）
DEFAULT_HTTP_TIMEOUT = 5.0
# SSE 长连接保持超时时间（秒）
DEFAULT_SSE_TIMEOUT = 30.0
# 服务不可用时，重试连接的等待间隔（秒）
DEFAULT_CONNECT_RETRY_DELAY = 3.0
# SSE 意外断线后，重新发起连接的等待间隔（秒）
DEFAULT_SSE_RECONNECT_DELAY = 1.0


# ==========================================
# 📦 数据模型
# ==========================================
class ChatMessage(BaseModel):
    """
    统一的聊天消息数据结构。
    使用 Pydantic 提供严格的类型校验和 JSON 序列化能力。
    """

    id: int
    sender: str
    text: str
    created_at: str


# ==========================================
# 🧠 本地状态管理
# ==========================================
class MessageState:
    """
    客户端本地的消息状态管理器。
    负责消息去重、排序，并记录当前已同步的最后一条消息 ID。
    由于会被主线程（发送消息）和后台线程（接收 SSE）同时访问，加入了线程锁保障安全。
    """

    def __init__(self) -> None:
        self._messages: list[ChatMessage] = []
        self._known_ids: set[int] = set()
        self._last_seen_id = 0
        self._lock = threading.Lock()

    @property
    def last_seen_id(self) -> int:
        """获取当前已知的最新消息 ID，用于断点续传"""
        with self._lock:
            return self._last_seen_id

    def merge_new_messages(self, incoming: list[ChatMessage]) -> list[ChatMessage]:
        """
        合并新到达的消息，自动过滤重复项，并更新 last_seen_id。
        返回真正属于“新增”的消息列表，供 UI 层渲染。
        """
        new_messages: list[ChatMessage] = []
        with self._lock:
            for message in incoming:
                if message.id in self._known_ids:
                    continue
                self._messages.append(message)
                self._known_ids.add(message.id)
                self._last_seen_id = max(self._last_seen_id, message.id)
                new_messages.append(message)
        return new_messages


# ==========================================
# 🌐 网关通信层
# ==========================================
class GatewayClient:
    """
    负责与 CLI Gateway 进行 HTTP 通信的封装客户端。
    统一处理 URL 拼接、超时和状态码校验。
    """

    def __init__(
        self, server_url: str, timeout_seconds: float = DEFAULT_HTTP_TIMEOUT
    ) -> None:
        # 去除 URL 尾部的斜杠，防止路径拼接时出现双斜杠
        self.server_url = server_url.rstrip("/")
        # 复用 httpx Client 提升连接池性能
        self.client = httpx.Client(base_url=self.server_url, timeout=timeout_seconds)

    def check_health(self) -> bool:
        """检查网关服务是否可用"""
        try:
            return self.client.get("/health").json().get("ok") is True
        except Exception:
            return False

    def fetch_messages(self, after_id: int = 0) -> list[ChatMessage]:
        """全量拉取历史消息（通常在客户端刚启动时调用）"""
        resp = self.client.get("/v1/messages", params={"after_id": after_id})
        resp.raise_for_status()
        return [ChatMessage.model_validate(item) for item in resp.json()]

    def send_message(self, sender: str, text: str) -> ChatMessage:
        """向网关发送一条新消息"""
        resp = self.client.post("/v1/messages", json={"sender": sender, "text": text})
        resp.raise_for_status()
        return ChatMessage.model_validate(resp.json())


# ==========================================
# 🖥️ 终端 UI 层
# ==========================================
class TerminalUI:
    """
    基于 prompt_toolkit 打造的富文本终端界面。
    处理彩色输出、输入历史记录以及异步日志打印。
    """

    def __init__(self) -> None:
        # 定义终端配色方案
        self._style = Style.from_dict(
            {
                "prompt": "ansicyan bold",
                "ai": "ansimagenta bold",
                "user": "ansigreen bold",
                "system": "ansiyellow bold",
                "error": "ansired bold",
            }
        )
        # 服务器地址输入的会话（不需要历史记录）
        self._server_session = PromptSession(complete_while_typing=False)
        # 聊天输入的会话（支持上下键翻找历史记录）
        self._chat_session = PromptSession(
            history=InMemoryHistory(),
            auto_suggest=AutoSuggestFromHistory(),
            complete_while_typing=False,
            erase_when_done=True,  # 输入完成后自动清空输入框，保持界面整洁
        )

    def print_intro(self, server_url: str) -> None:
        """打印欢迎信息和操作指南"""
        line = "=" * 72
        print_formatted_text(line, style=self._style)
        print_formatted_text(
            HTML("<system>AIChan CLI 客户端</system>"),
            style=self._style,
        )
        print_formatted_text(f"服务地址: {server_url}", style=self._style)
        print_formatted_text(
            "提示    : 输入消息后回车发送，/exit 退出，按 Ctrl+C 退出",
            style=self._style,
        )
        print_formatted_text(line, style=self._style)

    def prompt_server_url(self, default_url: str) -> str:
        """引导用户输入网关地址，并进行基础校验"""
        while True:
            raw = self._server_session.prompt(
                HTML("<prompt>服务地址</prompt> > "),
                default=default_url,
                style=self._style,
            ).strip()
            url = raw or default_url
            if not url.startswith(("http://", "https://")):
                self.print_error(
                    "错误：必须输入完整的 URL 协议（http:// 或 https://）。"
                )
                continue
            return url

    def prompt_user_text(self) -> str:
        """等待用户输入聊天文本"""
        return self._chat_session.prompt(
            HTML("<prompt>user</prompt> > "), style=self._style
        )

    def print_chat_message(self, message: ChatMessage) -> None:
        """格式化打印收发双方的聊天消息，支持多行文本缩进"""
        speaker = "user" if message.sender == "user" else "ai"
        content = message.text.strip() or "（空消息）"
        lines = content.splitlines()

        # 打印首行并带上发送者标签
        print_formatted_text(
            HTML(f"<{speaker}>{speaker}</{speaker}> > {html.escape(lines[0])}"),
            style=self._style,
        )
        # 如果有多行，后续行进行缩进对齐
        for line in lines[1:]:
            print_formatted_text(f"  {line}", style=self._style)

    def print_system(self, text: str) -> None:
        """打印系统提示信息"""
        print_formatted_text(
            HTML(f"<system>system</system> > {html.escape(text)}"), style=self._style
        )

    def print_error(self, text: str) -> None:
        """打印错误警告信息"""
        print_formatted_text(
            HTML(f"<error>error</error> > {html.escape(text)}"), style=self._style
        )


# ==========================================
# ⚙️ 核心业务流程控制
# ==========================================
def wait_for_gateway(client: GatewayClient, ui: TerminalUI, retry_delay: float) -> None:
    """阻塞等待网关服务启动上线"""
    while True:
        if client.check_health():
            ui.print_system("外部聊天服务连接成功。")
            return
        ui.print_error(f"无法连接服务，{retry_delay:g} 秒后重试（Ctrl+C 取消）。")
        time.sleep(retry_delay)


def sync_historical_messages(
    client: GatewayClient, state: MessageState, ui: TerminalUI, retry_delay: float
) -> list[ChatMessage]:
    """启动时同步错过的历史消息"""
    while True:
        try:
            # 根据本地记录的最后 ID 向服务器请求增量消息
            return state.merge_new_messages(
                client.fetch_messages(after_id=state.last_seen_id)
            )
        except (httpx.HTTPError, ValueError) as exc:
            ui.print_error(f"拉取历史消息失败：{exc}，{retry_delay:g} 秒后重试。")
            time.sleep(retry_delay)


def start_sse_worker(
    client: GatewayClient,
    state: MessageState,
    ui: TerminalUI,
    stop_event: threading.Event,
    reconnect_delay: float,
    timeout: float,
) -> threading.Thread:
    """启动后台守护线程，通过 SSE 流实时监听新消息"""

    def _listen() -> None:
        last_id = state.last_seen_id
        # 单独为 SSE 创建一个不限制读取超时的 Client，确保连接持久
        with httpx.Client(base_url=client.server_url, timeout=timeout) as hx_client:
            while not stop_event.is_set():
                try:
                    # 连接 SSE 频道，并通过 after_id 实现断点续传
                    with connect_sse(
                        hx_client, "GET", "/v1/events", params={"after_id": last_id}
                    ) as event_source:
                        for sse in event_source.iter_sse():
                            if stop_event.is_set():
                                return

                            # 仅处理名为 "message" 且包含数据的事件
                            if sse.event == "message" and sse.data:
                                try:
                                    msg = ChatMessage.model_validate_json(sse.data)
                                    new_messages = state.merge_new_messages([msg])
                                    for item in new_messages:
                                        ui.print_chat_message(item)
                                        last_id = max(last_id, item.id)
                                except Exception as e:
                                    ui.print_error(f"SSE 消息解析失败: {e}")

                except (httpx.RequestError, TimeoutError) as exc:
                    ui.print_error(f"实时同步断开：{exc}，{reconnect_delay:g} 秒后重连")
                    stop_event.wait(reconnect_delay)

    # 设为 daemon=True 确保主线程退出时，该监听线程自动销毁
    worker = threading.Thread(target=_listen, name="cli-sse-worker", daemon=True)
    worker.start()
    return worker


# ==========================================
# 🚀 应用程序入口
# ==========================================
def parse_args() -> argparse.Namespace:
    """解析命令行参数，提供连接/重连/超时等运行时可调项。"""
    parser = argparse.ArgumentParser(description="AIChan CLI 客户端")
    parser.add_argument(
        "--connect-retry-delay", type=float, default=DEFAULT_CONNECT_RETRY_DELAY
    )
    parser.add_argument(
        "--sse-reconnect-delay", type=float, default=DEFAULT_SSE_RECONNECT_DELAY
    )
    parser.add_argument("--sse-timeout", type=float, default=DEFAULT_SSE_TIMEOUT)
    parser.add_argument("--http-timeout", type=float, default=DEFAULT_HTTP_TIMEOUT)
    return parser.parse_args()


def main() -> None:
    """
    客户端主流程入口。

    执行顺序：
    1. 读取用户输入的网关地址；
    2. 检查并等待网关可用；
    3. 同步历史消息；
    4. 启动 SSE 后台线程并进入交互循环；
    5. 退出时优雅回收后台线程。
    """
    args = parse_args()
    ui = TerminalUI()

    # 1. 引导输入服务器地址
    try:
        server_url = ui.prompt_server_url(default_url=DEFAULT_SERVER_URL)
    except (KeyboardInterrupt, EOFError):
        return

    client = GatewayClient(server_url=server_url, timeout_seconds=args.http_timeout)

    try:
        # 2. 等待网关上线并打印欢迎语
        wait_for_gateway(client, ui, args.connect_retry_delay)
        ui.print_intro(server_url=server_url)

        # 3. 同步历史消息
        state = MessageState()
        for msg in sync_historical_messages(
            client, state, ui, args.connect_retry_delay
        ):
            ui.print_chat_message(msg)

        stop_event = threading.Event()
        sse_worker: threading.Thread | None = None

        # 4. 开启交互主循环
        # patch_stdout 确保后台 SSE 线程打印消息时，不会打断用户正在输入的内容
        with patch_stdout():
            sse_worker = start_sse_worker(
                client,
                state,
                ui,
                stop_event,
                args.sse_reconnect_delay,
                args.sse_timeout,
            )

            while True:
                try:
                    text = ui.prompt_user_text().strip()
                except (KeyboardInterrupt, EOFError):
                    ui.print_system("CLI 客户端已退出。")
                    break

                if not text:
                    continue
                if text in {"/exit", "/quit"}:
                    ui.print_system("CLI 客户端已退出。")
                    break

                # 提交用户的消息到网关
                try:
                    client.send_message(sender="user", text=text)
                except (httpx.HTTPError, ValueError) as exc:
                    ui.print_error(f"发送失败：{exc}")

    except KeyboardInterrupt:
        ui.print_system("已取消，CLI 客户端退出。")
    finally:
        # 优雅停机：通知后台线程停止，并等待其回收
        if "stop_event" in locals():
            stop_event.set()
        if (
            "sse_worker" in locals()
            and sse_worker is not None
            and sse_worker.is_alive()
        ):
            sse_worker.join(timeout=2.0)


if __name__ == "__main__":
    main()
