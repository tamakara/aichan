# AIChan

AIChan 当前采用 **MCPHub + AgentRuntime** 的动态架构：

- 大脑通过 `MCPHub` 连接一个或多个 MCP Server，并动态发现可调用工具；
- 通道 MCP Server 在收到人类消息后仅发送 `aichan/wakeup` 自定义唤醒通知；
- 大脑侧 `AgentRuntime` 被唤醒后，先调用 `fetch_unread_messages` 拉取未读，再通过 `send_*` 工具动作回复。
- 只要 MCP endpoint 发送 `aichan/wakeup`，Hub 就会触发全局唤醒事件（不做 channel/reason 过滤）。

> 本仓库已完成对旧静态插件模式的硬切换，不保留兼容链路。

## 核心组件

1. `aichan/mcp_hub`
   - `MCPManager`：统一管理 MCP Server 生命周期；
   - 动态发现 `mcp.types.Tool` 并包装为 LangChain `StructuredTool`。
2. `aichan/agent`
   - 基于 LangGraph 执行唤醒后的 Tool-as-Action 推理闭环。
3. `mcp_servers/cli`
   - CLI MCP Server，提供 `/mcp`（Streamable HTTP MCP 端点）与 `/v1/messages`、`/v1/events`（通道 API），并实现 `fetch_unread_messages` + `aichan/wakeup`。

## 快速开始

### 1. 安装依赖

```bash
cd aichan
uv sync
```

### 2. 配置环境变量

必须提供：

- `LLM_API_KEY`
- `LLM_BASE_URL`
- `LLM_MODEL_NAME`
- `LLM_TEMPERATURE`

可选：

- `MCP_SERVER_ENDPOINTS`（逗号分隔 MCP Streamable HTTP 端点）
  - 单端点：`http://localhost:9000/mcp`
  - 多端点：`http://localhost:9000/mcp,http://localhost:9100/mcp`
- `CLI_SERVER_HOST` / `CLI_SERVER_PORT`

### 3. 启动大脑

```bash
cd aichan
uv run python main.py
```

### 4. 启动 CLI MCP Server

```bash
cd mcp_servers
uv sync
uv run --package cli-mcp-server python -m cli.server
```

## 关键 API

- CLI 通道消息接口：
  - `GET /v1/messages?after_id=0`
  - `POST /v1/messages`
  - `GET /v1/events?after_id=0`
- MCP Streamable HTTP 端点：
  - `GET /mcp`
  - `POST /mcp`
  - `DELETE /mcp`

## 目录结构

```text
.
├─ aichan
│  ├─ main.py
│  ├─ mcp_hub
│  ├─ agent
│  ├─ core
│  └─ memory
├─ mcp_servers
│  └─ cli
└─ docs
```
