# Minerva Docker Image
# docker build -t minerva -f docker/Dockerfile .

FROM python:3.12-slim

LABEL org.opencontainers.image.title="Minerva Deep Research"
LABEL org.opencontainers.image.description="Local-first deep research system"
LABEL org.opencontainers.image.version="0.11.0"

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Minerva and dependencies
COPY pyproject.toml README.md ./
COPY src/ ./src/
RUN pip install --no-cache-dir -e .

# Default: web server
EXPOSE 8765
HEALTHCHECK --interval=15s --timeout=5s --retries=3 \
    CMD curl -f http://localhost:8765/health || exit 1

CMD ["minerva", "web"]
