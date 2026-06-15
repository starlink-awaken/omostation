FROM python:3.13-slim

WORKDIR /app

COPY pyproject.toml .
RUN pip install uv && uv sync --no-dev

COPY src/ src/

EXPOSE 8080

CMD ["python", "-m", "ecos.cli.dashboard"]
