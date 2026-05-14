FROM python:3.12-slim

LABEL io.docker.server.metadata='{"name":"qq-adapter-service","description":"Expose QQ message history as MCP tools.","command":["qq-adapter-mcp"]}'

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV UV_SYSTEM_PYTHON=1

COPY --from=ghcr.io/astral-sh/uv:0.7.2 /uv /usr/local/bin/uv

WORKDIR /app

COPY pyproject.toml ./
COPY config.yml ./qq-adapter-service/config.yml
COPY src ./src

RUN uv pip install --system .

EXPOSE 8010

CMD ["qq-adapter-mcp"]
