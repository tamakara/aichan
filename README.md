# AIChan

基于 `uv workspace` 的多包项目，当前包含 `agent-service`、`adapter-service` 与 `hub-service` 三个核心服务。

## 目录结构

```text
.
├─ pyproject.toml
├─ uv.lock
├─ docker-compose.yml
├─ docs/
│  ├─ agent-service.md
│  ├─ adapter-service.md
│  └─ hub-service.md
├─ agent-service/
│  ├─ pyproject.toml
│  ├─ config.yml
│  ├─ Dockerfile
│  └─ src/agent_service
├─ hub-service/
│  ├─ pyproject.toml
│  ├─ config.yml
│  ├─ Dockerfile
│  └─ src/hub_service
└─ adapter-service/
   ├─ pyproject.toml
   ├─ config.yml
   ├─ Dockerfile
   └─ src/adapter_service
```

## 配置

每个服务都只读取各自目录下的 `config.yml`，代码和 `docker-compose.yml` 不再读取环境变量。

## 本地运行（uv）

1. 安装依赖（根目录）：

```bash
uv sync --all-packages
```

2. 按服务分别启动：

```bash
uv run --package agent-service agent-service
uv run --package adapter-service adapter-service
uv run --package hub-service hub-service
```

## Docker Compose 部署（推荐）

```bash
docker compose up -d --build
```

## 子模块文档

- `docs/aichan.md`
- `docs/agent-service.md`
- `docs/adapter-service.md`
- `docs/hub-service.md`
