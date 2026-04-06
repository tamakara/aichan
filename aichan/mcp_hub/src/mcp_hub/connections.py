from __future__ import annotations

from contextlib import AsyncExitStack

from core.logger import logger
from mcp.client.streamable_http import streamable_http_client

from .models import MCPServerConfig
from .session import AichanClientSession, WakeupHandler, bind_wakeup_notification_handler


class MCPConnectionPool:
    """
    管理 MCP 多服务连接生命周期。

    职责边界：
    1. 按配置建立会话连接；
    2. 在连接成功后注册唤醒通知处理器；
    3. 统一管理连接资源释放；
    4. 任一服务失败即终止启动（全部服务均为强依赖）。
    """

    def __init__(self, server_configs: list[MCPServerConfig]) -> None:
        # 启动时的目标服务配置（按顺序连接，便于日志定位）。
        self._server_configs = server_configs

        # 已建立连接的会话映射：server_name -> session。
        self._sessions: dict[str, AichanClientSession] = {}

        # 统一管理所有异步上下文，stop 时一次性释放。
        self._exit_stack: AsyncExitStack | None = None

    @property
    def sessions(self) -> dict[str, AichanClientSession]:
        """返回当前会话映射（由上层只读使用）。"""
        return self._sessions

    def get_connected_server_count(self) -> int:
        """返回已连接服务数量，供 health 与启动日志使用。"""
        return len(self._sessions)

    async def start(self, wakeup_handler: WakeupHandler) -> None:
        """
        建立全部 MCP 服务连接。

        连接策略：
        - 任一服务失败：立即抛错并终止启动。
        """
        if self._exit_stack is not None:
            raise RuntimeError("MCPConnectionPool 已启动，不能重复启动")

        # 初始化全局资源栈，后续每个连接成功后都会挂载到该栈上。
        self._exit_stack = AsyncExitStack()
        connected_count = 0
        logger.info("🚀 [MCPHub] 启动连接管理，目标服务数={}", len(self._server_configs))

        try:
            for config in self._server_configs:
                try:
                    # 尝试连接单个服务并注册唤醒处理器。
                    session = await self._connect_single_server(
                        config=config,
                        wakeup_handler=wakeup_handler,
                    )
                    # 连接成功后写入会话映射。
                    self._sessions[config.name] = session
                    connected_count += 1
                    logger.info(
                        "✅ [MCPHub] 服务连接成功，name='{}'，url='{}'",
                        config.name,
                        config.endpoint_url,
                    )
                except Exception as exc:
                    raise RuntimeError(
                        f"MCP 服务连接失败：name='{config.name}', url='{config.endpoint_url}'"
                    ) from exc

            if connected_count == 0:
                raise RuntimeError("未连接到任何 MCP 服务，无法启动 MCPManager")
        except Exception:
            # 任一异常触发统一回滚，确保不会遗留半初始化连接。
            await self.stop()
            raise

    async def stop(self) -> None:
        """释放全部连接资源并清空会话状态。"""
        exit_stack = self._exit_stack

        # 先切断外部可见状态，避免 stop 过程中被再次读取。
        self._sessions = {}
        self._exit_stack = None

        if exit_stack is not None:
            try:
                # 统一关闭所有连接上下文。
                await exit_stack.aclose()
            except Exception as exc:
                # 关闭阶段异常只做调试日志，不阻断停止流程。
                logger.debug(
                    "♻️ [MCPHub] 忽略停止阶段连接清理异常: {}: {}",
                    exc.__class__.__name__,
                    exc,
                )

    async def _connect_single_server(
        self,
        *,
        config: MCPServerConfig,
        wakeup_handler: WakeupHandler,
    ) -> AichanClientSession:
        """
        连接单个 MCP 服务，并将资源挂接到全局 ExitStack。

        关键点：
        - 使用临时 ExitStack 避免半初始化资源泄露；
        - 仅当初始化全部成功后，才转移到全局资源栈。
        """
        if self._exit_stack is None:
            raise RuntimeError("MCPConnectionPool 尚未初始化 ExitStack")

        # 先在临时栈里完成初始化，成功后再挂到全局 ExitStack，
        # 避免初始化失败时触发跨任务的 cancel scope 退出异常。
        temp_stack = AsyncExitStack()
        try:
            read_stream, write_stream, _ = await temp_stack.enter_async_context(
                streamable_http_client(config.endpoint_url)
            )
            session = await temp_stack.enter_async_context(
                AichanClientSession(
                    read_stream,
                    write_stream,
                )
            )
            bind_wakeup_notification_handler(
                session=session,
                server_name=config.name,
                handler=wakeup_handler,
            )
            # 必须在 initialize 后才能安全使用会话。
            await session.initialize()
        except BaseException as exc:
            try:
                # 初始化失败时立即清理临时资源，避免连接泄露。
                await temp_stack.aclose()
            except BaseException as close_exc:
                # 清理阶段异常仅记日志，不覆盖主异常信息。
                logger.debug(
                    "♻️ [MCPHub] 忽略连接失败后的清理异常，url='{}'，error='{}: {}'",
                    config.endpoint_url,
                    close_exc.__class__.__name__,
                    close_exc,
                )
            if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                # 进程级终止信号必须原样抛出。
                raise
            raise RuntimeError(
                f"MCP 会话初始化失败：url='{config.endpoint_url}'"
            ) from exc

        # 仅在全部初始化成功后，把临时资源栈转移到全局资源栈。
        persisted_stack = temp_stack.pop_all()
        self._exit_stack.push_async_callback(persisted_stack.aclose)
        return session
