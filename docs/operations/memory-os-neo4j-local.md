---
status: active
lifecycle: plan
owner: engineering-team
last-reviewed: 2026-08-05
related:
  - ./memory-os-phase6-retro.md
  - ./minerva-local.md
  - ../../.omo/_knowledge/decisions/0372-memory-os-control-plane.md
---

# Memory OS — 本机 Neo4j 启动

> Phase 6–7：`NEO4J_URI` 门控写 + 读。未设置时仅 TemporalShadow，不写图、recall 不 fan-out neo4j。

## 一键（推荐）

```bash
bash bin/memory-os-neo4j-up.sh          # Docker 优先，失败则 brew
bash bin/memory-os-neo4j-up.sh status
bash bin/memory-os-neo4j-up.sh stop
```

成功后脚本会打印：

```bash
export NEO4J_URI=bolt://localhost:7687 NEO4J_USER=neo4j NEO4J_PASSWORD=changeme
```

## 路径 A：Docker（MOS 专用 compose）

```bash
docker compose -f projects/kairon/packages/mos/docker-compose.yml up -d
docker exec mos-neo4j cypher-shell -u neo4j -p changeme 'RETURN 1'
```

也可与 minerva 共用：

```bash
cd projects/kairon/packages/minerva/docker
docker compose --profile full up -d neo4j
```

- Browser: http://localhost:7474 · Bolt: `bolt://localhost:7687` · 密码默认 `changeme`

若 Docker Desktop 报 `meta.db: input/output error` / blob I/O：

1. 完全退出 Docker Desktop 再开  
2. 仍失败 → Settings → Troubleshoot → Clean / Purge data  
3. **Podman 替代**（本机可建 `podman machine init mos-neo4j` applehv）：  
   `export DOCKER_HOST=unix://$(podman machine inspect mos-neo4j --format '{{.ConnectionInfo.PodmanSocket.Path}}' 2>/dev/null || true)`  
   再 `docker compose -f projects/kairon/packages/mos/docker-compose.yml up -d`  
4. 或 `bash bin/memory-os-neo4j-up.sh` 自动 **brew fallback**（2026-08-05 验证可用）

> 2026-08-05 实测：Docker Desktop I/O 损坏；Podman machine 可起，但拉 `neo4j:5-community` 遇 registry i/o timeout → 生产写读用 brew 闭环。

## 路径 B：Homebrew（2026-08-05 本机实测）

```bash
brew install neo4j && brew services start neo4j
# 首次密码 neo4j 须改密（脚本已自动尝试）
```

## 环境变量（MOS / cockpit）

```bash
export NEO4J_URI=bolt://localhost:7687
export NEO4J_USER=neo4j
export NEO4J_PASSWORD=changeme
export MOS_TEMPORAL=1
export MOS_RBAC=1
```

## 冒烟（写 + 召回）

```bash
cd projects/kairon
uv run --package mos --with neo4j python -m mos status
# 期望: neo4j_configured=true, neo4j_available=true, neo4j_recall=true, version>=0.7.0

echo '{"kwargs":{"type":"semantic","content":"Carol founded NeoSoft","subject":"Carol","predicate":"founded","object":"NeoSoft","confidence":0.9}}' \
  | MOS_STDIO=1 uv run --package mos --with neo4j python -m mos write

echo '{"kwargs":{"query":"Carol founded","intent":"temporal_fact","limit":5}}' \
  | MOS_STDIO=1 uv run --package mos --with neo4j python -m mos recall
# 期望 hits 含 neo4j backend / Carol
```

可选 dependency：`mos[neo4j]` / `mos[graph]`（`neo4j>=5.14`）。