# hub-service

`hub-service` 是 AICHAN 的提醒中枢，负责接收 `qq-adapter-service` 推送的 QQ 私聊提醒，触发 `agent-service` 生成回复，并将回复回写到 `qq-adapter-service`。

## 设计目标

- 中枢编排：集中管理“提醒 -> agent -> 回写 QQ”主链路。
- 私聊优先：首版仅处理私聊提醒，群聊事件统一忽略。
- 轻量状态：提醒以内存按用户分桶管理，不引入持久化依赖。

## 路由契约

- `GET /healthz`
  - 返回：`{"status":"ok"}`

- `WS /qq/events`
  - 入参：`qq-adapter-service` 转发的过滤事件 JSON。
  - 处理：
    - 仅处理 `message_type=private`。
    - 记录提醒到内存（按 `user_id` 分桶）。
    - 调用 `agent-service /chat`，将提醒内容作为 `user_message`。
    - 将 agent 回复通过 `qq-adapter-service /api/v1/message/send` 回写 QQ。
  - 当前策略：失败仅记录日志，不做重试；当下游返回非 2xx 时，日志会包含下游响应体以便快速定位根因。

## 下游依赖接口

- `agent-service`
  - `POST /chat`
  - request: `{"session_id":"private_xxx","user_message":"..."}`
  - response: `{"reply":"..."}`

- `qq-adapter-service`
  - `POST /api/v1/message/send`
  - request: `{"session_id":"private_xxx","content":"..."}`
  - response: `{"ok":true,"data":{...}}`

## 配置文件

配置文件路径：`hub-service/config.yml`

```yaml
server:
  host: 0.0.0.0
  port: 8020
  log_level: debug

hub:
  agent_url: http://agent-service:8000
  qq_adapter_url: http://qq-adapter-service:8010
```

## 启动

在仓库根目录执行：

```bash
uv run --package hub-service hub-service
```

Docker Compose 启动：

```bash
docker compose up -d --build hub-service
```

## 容器构建稳定性

- Dockerfile 改为在基础镜像内通过 `pip install uv==0.7.2` 安装 uv，避免依赖 `ghcr.io` 元数据拉取失败。
- `hub-service/Dockerfile` 已设置 `UV_HTTP_TIMEOUT=180` 与 `UV_HTTP_RETRIES=8`，降低网络抖动导致的依赖下载超时失败概率。
- `uv pip install --system .` 使用 3 次重试策略，针对 `uv_build` 元数据拉取偶发超时可自动恢复。
