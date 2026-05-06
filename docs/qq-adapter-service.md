# qq-adapter-service

`qq-adapter-service` 是 AICHAN 的 QQ 协议过滤与桥接网关，负责在 OneBot v11 与下游 WebSocket 模块之间做实时双向转发。

## 设计目标

- 无状态过滤：仅做协议清洗与路由，不存储会话业务状态。
- 单连接语义：NapCat 仅通过一条反向 WebSocket 与网关互通事件和动作。
- 低耦合桥接：下游模块通过独立 WebSocket 接收过滤事件，不感知 NapCat 协议细节。

## 通信拓扑

- NapCat -> `qq-adapter-service`：反向 WebSocket，地址 `ws://qq-adapter-service:8010/napcat/ws`
- `qq-adapter-service` -> `hub-service`：主动 WebSocket Client，地址由 `DOWNSTREAM_WS_URL` 指定

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

## ID 映射规则

- 群会话：`group_id <-> session_id=group_{group_id}`
- 私聊会话：`user_id <-> session_id=private_{user_id}`
- 用户画像：`user_id <-> user_id=qq_{user_id}`

## 下游事件负载

转发到下游 WebSocket 的 JSON 字段：`session_id`、`user_id`、`content`、`source`、`message_type`、`raw_event`。

## 环境变量

- `HOST`
- `PORT`
- `LOG_LEVEL`
- `DOWNSTREAM_WS_URL`
- `DOWNSTREAM_WS_TOKEN`
- `DOWNSTREAM_WS_OPEN_TIMEOUT_SECONDS`
- `DOWNSTREAM_WS_RECONNECT_INTERVAL_SECONDS`
- `ONEBOT_WS_ACTION_TIMEOUT_SECONDS`

## 启动

在仓库根目录执行：

```bash
uv run --package qq-adapter-service qq-adapter-service
```

Docker Compose 启动：

```bash
docker compose up -d --build qq-adapter-service
```

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
