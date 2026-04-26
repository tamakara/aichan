# agent-service 子项目（FastAPI + uv + Docker）

## 运行前配置

必需环境变量：

- `LLM_API_KEY`
- `LLM_BASE_URL`
- `MCP_SSE_URL`

可选环境变量见 `.env.example`。

## 使用 uv 本地启动

在 `agent-service` 目录下执行：

```bash
uv run agent-service
```

## API

- `GET /healthz`：健康检查
- `POST /chat`：发起会话
- `DELETE /session`：清理当前会话

`POST /chat` 示例：

```json
{
  "user_input": "你好",
  "max_turns": 10
}
```

## Docker 部署

在 `agent-service` 目录下执行：

```bash
docker build -t agent-service-api:latest .
```

```bash
docker run --rm -p 8000:8000 \
  -e LLM_API_KEY=your_key \
  -e LLM_BASE_URL=https://api.openai.com/v1 \
  -e MCP_SSE_URL=http://your-mcp-gateway/sse \
  agent-service-api:latest
```

或使用 `docker compose`：

```bash
cp .env.example .env
docker compose up -d --build
```
