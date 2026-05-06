# AIChan

基于 `uv workspace` 的多包项目，当前包含 `agent-service`、`qq-adapter-service` 与 `hub-service` 三个核心服务。

## 目录结构

```text
.
├─ pyproject.toml
├─ uv.lock
├─ .env.example
├─ docker-compose.yml
├─ docs/
│  ├─ agent-service.md
│  ├─ qq-adapter-service.md
│  └─ hub-service.md
├─ agent-service/
│  ├─ pyproject.toml
│  ├─ Dockerfile
│  └─ src/agent_service
├─ hub-service/
│  ├─ pyproject.toml
│  ├─ Dockerfile
│  └─ src/hub_service
└─ qq-adapter-service/
   ├─ pyproject.toml
   ├─ Dockerfile
   └─ src/qq_adapter_service
```

## 环境变量

默认值统一定义在根目录 `.env.example`，代码和 `docker-compose.yml` 不内置兼容回退。

## 本地运行（uv）

1. 安装依赖（根目录）：

```bash
uv sync --all-packages
```

2. 复制环境变量文件并填写：

```bash
cp .env.example .env
```

3. 按服务分别启动：

```bash
uv run --package agent-service agent-service
uv run --package qq-adapter-service qq-adapter-service
uv run --package hub-service hub-service
```

## Docker Compose 部署（推荐）

```bash
docker compose up -d --build
```

## 子模块文档

- `docs/agent-service.md`
- `docs/qq-adapter-service.md`
- `docs/hub-service.md`
