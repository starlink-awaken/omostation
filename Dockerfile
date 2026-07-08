FROM python:3.13-slim

WORKDIR /app

COPY pyproject.toml .
RUN pip install uv && uv sync --no-dev

COPY src/ src/

# ecos dashboard HTTP server 已移除，数据通过 CLI --json 或 cockpit :8090 /api/ecos/status 暴露。
# 本镜像默认执行 dashboard JSON 导出；生产环境建议直接使用 ecos CLI / MCP / cockpit 路由。
CMD ["python", "-m", "ecos.cli.dashboard", "--json"]
