# qq-adapter-service

`qq-adapter-service` 是 AICHAN 的 QQ 协议过滤、桥接与 MCP 工具网关，负责：
- 在 OneBot v11 与下游 WebSocket 模块之间做实时双向转发。
- 把 QQ 历史消息查询能力暴露为 MCP 工具，供 MCP Gateway/agent 调用。

## 设计目标

- 无状态过滤：仅做协议清洗与路由，不存储会话业务状态。
- 单连接语义：NapCat 仅通过一条反向 WebSocket 与网关互通事件和动作。
- 低耦合桥接：下游模块通过独立 WebSocket 接收过滤事件，不感知 NapCat 协议细节。

## 通信拓扑

- NapCat -> `qq-adapter-service`：反向 WebSocket，地址 `ws://qq-adapter-service:8010/napcat/ws`
- `qq-adapter-service` -> `hub-service`：主动 WebSocket Client，地址由 `adapter.downstream_ws_url` 指定

## 路由契约

- `GET /healthz`
  - 返回：`{"status":"ok"}`

- `WS /napcat/ws`
  - NapCat 连接入口。
  - 入站事件处理：仅接收文本消息；当前仅私聊会进入下游链路，群聊事件统一忽略；移除 CQ 码并转为纯文本后转发到下游 WebSocket。
  - 出站动作处理：`/api/v1/message/send` 与 `/api/v1/user/{user_id}/info` 会通过该连接发送 OneBot action，并等待 `echo` 对应响应。

- `POST /api/v1/message/send`
  - 入参：`{ "session_id": "group_123|private_456", "content": "..." }`
  - 行为：转换为 OneBot action，通过当前 NapCat WebSocket 连接下发。

- `GET /api/v1/user/{user_id}/info`
  - 入参：`user_id=qq_123456`
  - 行为：转换为 `get_stranger_info` action，通过当前 NapCat WebSocket 连接下发。

- `GET /api/v1/message/history`
  - 入参：
    - `session_id=group_123|private_456`
    - `limit=1..50`
    - `before_message_id` 可选
  - 行为：
    - `group_*` -> `get_group_msg_history`
    - `private_*` -> `get_friend_msg_history`
    - 返回 `messages` 与 `next_before_message_id`

## MCP 工具契约

- 工具名：`qq_get_message_history`
  - 参数：
    - `session_id`：`group_123` 或 `private_456`
    - `limit`：`1..50`，默认 `20`
    - `before_message_id`：可选，正整数
  - 行为：
    - 工具参数校验通过后，调用本服务 HTTP 接口 `GET /api/v1/message/history`
    - 返回 MCP `tool result` 的 JSON 字符串，字段固定为：
      - `session_id`
      - `messages`
      - `next_before_message_id`（无更多记录时为 `null`）

## ID 映射规则

- 群会话：`group_id <-> session_id=group_{group_id}`
- 私聊会话：`user_id <-> session_id=private_{user_id}`
- 用户画像：`user_id <-> user_id=qq_{user_id}`

## 下游事件负载

转发到下游 WebSocket 的 JSON 字段：`session_id`、`user_id`、`content`、`source`、`message_type`、`raw_event`。

## 配置文件

配置文件路径：`qq-adapter-service/config.yml`

配置约束（与当前代码一致）：

- 仅从本服务目录内的 `config.yml` 读取运行配置。
- 不读取 `.env`、`.env.example`，也不支持任何环境变量别名。
- 修改接口地址、端口、超时等参数时，只更新 `qq-adapter-service/config.yml`。
- 在 Docker Compose 中通过只读挂载该配置文件，保证容器与本地运行共享同一配置语义。
- 配置加载阶段使用 Pydantic 严格校验：字段类型不匹配、缺失字段或出现未声明字段都会直接报错并阻断启动。

```yaml
server:
  host: 0.0.0.0
  port: 8010
  log_level: debug

adapter:
  downstream_ws_url: ws://hub-service:8020/qq/events
  downstream_ws_token: ""
  downstream_ws_open_timeout_seconds: 5
  downstream_ws_reconnect_interval_seconds: 3
  onebot_ws_action_timeout_seconds: 5

mcp:
  base_url: http://qq-adapter-service:8010
  timeout_seconds: 5
  log_level: debug
```

消息历史查询仅在 NapCat WebSocket 已连接时可用。

## 启动

在仓库根目录执行：

```bash
uv run --package qq-adapter-service qq-adapter-service
```

MCP stdio 入口（供 MCP Gateway 通过 `docker://` 拉起）：

```bash
uv run --package qq-adapter-service qq-adapter-mcp
```

Docker Compose 启动：

```bash
docker compose up -d --build qq-adapter-service
```

## 容器构建稳定性

- Dockerfile 改为在基础镜像内通过 `pip install uv==0.7.2` 安装 uv，避免依赖 `ghcr.io` 元数据拉取失败。
- `qq-adapter-service/Dockerfile` 已设置 `UV_HTTP_TIMEOUT=180` 与 `UV_HTTP_RETRIES=8`，降低网络抖动导致的依赖下载超时失败概率。
- `uv pip install --system .` 使用 3 次重试策略，针对 `uv_build` 元数据拉取偶发超时可自动恢复。

## MCP Gateway 接入

- Gateway 服务参数中增加 `docker://qq-adapter-service:latest`。
- `qq-adapter-service` 容器镜像默认入口为 `qq-adapter-mcp`（stdio MCP server）。
- Compose 中通过 `command: ["qq-adapter-service"]` 显式覆盖，保证业务 HTTP 服务与 MCP 工具容器职责分离。

## NapCat 手动对接

NapCat 作为外部服务独立部署，本项目不负责其容器、账号数据目录与配置文件管理。

## 验证步骤

1. 健康检查：

```bash
curl http://localhost:8010/healthz
```

2. 登录外部 NapCat WebUI，在网络配置中手工新建 `WebSocket Client`：
   - `name`: `aichan-adapter-rws`
   - `url`: `ws://qq-adapter-service:8010/napcat/ws`
   - `messagePostFormat`: `array`
   - `enable`: `true`

3. 向机器人发送私聊消息，检查 `hub-service` 日志是否出现提醒处理记录与回写日志。
