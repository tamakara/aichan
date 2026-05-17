# agent-service

`agent-service` 是 AIChan 的 HTTP API 子模块，基于 FastAPI 封装 `AgentCore`。

## 模块结构

- `agent_service/main.py`：模块根目录唯一启动入口。
- `agent_service/logger.py`：全局日志配置与统一 logger 获取入口。
- `agent_service/router/`：仅负责 HTTP 路由与请求/响应 Schema。
- `agent_service/app.py`：负责应用组装编排（AgentCore、依赖注入、FastAPI 应用拼装）。
- `agent_service/agent/`：核心 Agent 逻辑，不直接承担 HTTP 服务装配职责。
- `agent_service/prompts.py`：系统提示词，独立于运行时代码管理。

## API

- `GET /healthz`
- `POST /chat`

`POST /chat` 示例：

```json
{
  "session_id": "private_123",
  "user_message": "你好"
}
```

`max_turns` 由服务配置 `agent-service/config.yml` 中的 `agent.max_turns` 统一控制，不再支持按请求覆盖。

`session_id` 语义：

- 相同 `session_id` 的请求会被串行执行，保证同一会话上下文不会被并发写坏。
- 不同 `session_id` 的请求可并行执行，提升多会话吞吐。

错误诊断：

- `/chat` 处理失败时会输出完整异常栈日志，并携带 `session_id`，用于快速定位会话级故障。

运行日志：

- 运行时已关闭 FastAPI/Uvicorn 框架日志，仅保留 `agent_service.*` 自定义日志，避免框架访问日志干扰诊断。
- 日志输出采用“双轨格式”：前半段是中文可读摘要，后半段保留 `event=... key=value...` 结构化字段，兼顾人工阅读与机器检索。
- 启动阶段会输出 `agent_app.boot/agent_app.ready`，用于确认模型、`max_turns`、MCP 地址与会话并发策略。
- 请求阶段会输出 `agent.chat_received/agent.session_bound/agent.chat_completed/agent.chat_failed`，用于定位会话请求全链路耗时。
- 核心执行会输出 `agent_core.run_started/agent_core.llm_responded/agent_core.tool_called/agent_core.run_completed`，用于观察每轮推理与工具调用行为。
- MCP 网关会输出 `mcp.registered/mcp.tool_called`，用于排查工具注册与调用耗时。
- 工具 schema 会在注册阶段执行兼容性清洗（当前仅移除已观测触发 400 的 `propertyNames` 字段），并输出 `mcp.schema_sanitized` 日志。
- LLM 调用失败时会输出 `llm.request_failed`，并带上游响应体（status/detail），用于快速定位模型兼容性或参数问题。

## 配置文件

配置文件路径：`agent-service/config.yml`

配置约束（与当前代码一致）：

- 仅从本服务目录内的 `config.yml` 读取运行配置。
- 不读取 `.env`、`.env.example`，也不支持任何环境变量别名。
- 修改接口地址、端口、超时等参数时，只更新 `agent-service/config.yml`。
- 在 Docker Compose 中通过只读挂载该配置文件，保证容器与本地运行共享同一配置语义。
- 配置加载阶段使用 Pydantic 严格校验：字段类型不匹配、缺失字段或出现未声明字段都会直接报错并阻断启动。

```yaml
server:
  host: 0.0.0.0
  port: 8000

agent:
  model: gpt-5.5
  max_turns: 10
  openai_api_key: your_openai_api_key
  openai_base_url: https://api.openai.com/v1
  mcp_sse_url: http://mcp-gateway:9000/sse
  mcp_auth_token: ""
```

## 运行

本地运行（在仓库根目录）：

```bash
uv run --package agent-service agent-service
```

若使用本机直连 MCP Gateway，请将 `agent.mcp_sse_url` 改为 `http://localhost:9000/sse`。

容器运行入口：

```bash
agent-service
```

## 容器构建稳定性

- Dockerfile 改为在基础镜像内通过 `pip install uv==0.7.2` 安装 uv，避免依赖 `ghcr.io` 元数据拉取失败。
- `agent-service/Dockerfile` 已设置 `UV_HTTP_TIMEOUT=180` 与 `UV_HTTP_RETRIES=8`，降低网络抖动导致的依赖下载超时失败概率。
- `uv pip install --system .` 使用 3 次重试策略，针对 `uv_build` 元数据拉取偶发超时可自动恢复。
