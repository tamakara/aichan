from __future__ import annotations

import os

"""
CLI MCP Server 运行时配置。

说明：
1. 所有配置均支持通过环境变量覆写，便于本地开发与容器部署统一；
2. 配置集中放在单独模块，避免散落在业务代码里导致维护成本上升。
"""

# 服务监听地址。容器内通常使用 0.0.0.0，本地默认 localhost。
CLI_SERVER_HOST = os.getenv("CLI_SERVER_HOST", "localhost")
# 服务监听端口。
CLI_SERVER_PORT = int(os.getenv("CLI_SERVER_PORT", "9000"))
# Uvicorn Keep-Alive 超时时间，适当缩短可减少空闲连接占用。
CLI_SERVER_TIMEOUT_KEEP_ALIVE_SECONDS = 1
# 优雅停机等待时间，确保连接在短时间内可被正确关闭。
CLI_SERVER_TIMEOUT_GRACEFUL_SHUTDOWN_SECONDS = 2
# SSE 长轮询等待超时，用于定期返回 keep-alive 心跳。
CLI_SERVER_SSE_WAIT_TIMEOUT_SECONDS = 1.0
