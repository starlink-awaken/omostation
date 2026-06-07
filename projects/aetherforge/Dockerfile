FROM python:3.12-slim

WORKDIR /app

# Install uv for fast dependency resolution
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Copy workspace
COPY pyproject.toml README.md ./
COPY src/ src/
COPY packages/ packages/

# Install dependencies
RUN uv sync --no-dev

# Expose MCP SSE port
EXPOSE 8000

# Start unified MCP server
CMD ["uv", "run", "aetherforge-mcp"]
