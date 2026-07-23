# Minerva 本地运行（SearXNG + 研究）

> 配套：`projects/kairon/packages/minerva` · 抓取全景见 [external-ingest-callchain.md](./external-ingest-callchain.md)

## 一键起搜索后端

```bash
cd projects/kairon/packages/minerva/docker
docker compose up -d searxng
# 或双文件任选：docker compose -f docker-compose.yaml up -d searxng

# 健康：根路径 200 即可（镜像无 /health）
curl -sf http://localhost:8080/ >/dev/null && echo searxng_ok
curl -sf "http://localhost:8080/search?q=test&format=json" | head -c 120
```

容器名：`minerva-searxng` · 端口：`8080` · `restart: unless-stopped`（Docker 重启后自动起来）。

## 健康检查

```bash
uv run --directory projects/kairon python -m minerva.cli check
# 期望：Ollama ✅ · SearXNG ✅ · API keys 按本机配置
```

## 快速研究

```bash
uv run --directory projects/kairon python -m minerva.cli research "主题" --level L0
# 或产品入口
uv run --directory projects/cockpit python -m cockpit research "主题"
```

模型名见 `packages/minerva/config/minerva.yaml`（须与本机 `ollama list` 对齐）。

## 可选：Neo4j（L2+ 图）

```bash
cd projects/kairon/packages/minerva/docker
docker compose --profile full up -d neo4j
```

## 故障

| 现象 | 处理 |
|------|------|
| SearXNG unhealthy 但主机 curl / 200 | 镜像无 curl、无 `/health`；compose 已用 `wget --spider /`。重建：`docker compose up -d --force-recreate searxng` |
| Ollama 404 | 配置里的 model tag 本机不存在 → 改 minerva.yaml 或 `ollama pull` |
| 端口 8080 占用 | 改 compose ports 映射，并同步 `minerva.yaml` searxng.base_url |
