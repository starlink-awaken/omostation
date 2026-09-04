---
lifecycle: plan
owner: engineering-team
last_updated: 2026-08-05
related:
  - ./memory-os-phase6-retro.md
  - ./memory-os-phase10-retro.md
  - ./minerva-local.md
  - ../../.omo/_knowledge/decisions/0372-memory-os-control-plane.md
  - ../../.omo/standards/memory-os-ops.md
title: Memory OS — 本机 Neo4j 启动
type: doc
---

# Memory OS — 本机 Neo4j 启动

> Phase 6–10：`NEO4J_URI` 门控写 + 读 + **as_of** 双时态过滤。未设置 URI 时仅 TemporalShadow，不写图、recall 不 fan-out neo4j。

## 一键（推荐）

```bash
# 1) 环境（cockpit / agent shell）
source bin/memory-os-env.sh             # 或 eval "$(bin/memory-os-env.sh --export)"
# 2) 图库
bash bin/memory-os-neo4j-up.sh          # Docker/podman 优先，失败则 brew
bash bin/memory-os-neo4j-up.sh status
bash bin/memory-os-neo4j-up.sh stop
# 3) 治理面检查 + 冒烟
make memory-os-check
make memory-os-smoke                    # status + write + recall + as_of
# 4) CLI 帮助 / 状态 / 工作台
cockpit help                            # 与 discover 同源命令地图
cockpit discover
cockpit status                          # 工作台含 Memory OS 健康行
cockpit memory
cockpit memory status --json
```

环境加载顺序（**进程非空 env 最高**）：  
example → cockpit `.env` → `config/memory-os.env`（后写覆盖）；再恢复进程预设。

成功后图库脚本也会打印：

```bash
export NEO4J_URI=bolt://localhost:7687 NEO4J_USER=neo4j NEO4J_PASSWORD=changeme
```

## 路径 A：Docker（MOS 专用 compose）

```bash
docker compose -f projects/knowledge/kairon/packages/mos/docker-compose.yml up -d
docker exec mos-neo4j cypher-shell -u neo4j -p changeme 'RETURN 1'
```

也可与 minerva 共用：

```bash
cd projects/knowledge/kairon/packages/minerva/docker
docker compose --profile full up -d neo4j
```

- Browser: http://localhost:7474 · Bolt: `bolt://localhost:7687` · 密码默认 `changeme`

若 Docker Desktop 报 `meta.db: input/output error` / blob I/O：

1. 完全退出 Docker Desktop 再开  
2. 仍失败 → Settings → Troubleshoot → Clean / Purge data  
3. **Podman 替代**（本机可建 `podman machine init mos-neo4j` applehv）：  
   `export DOCKER_HOST=unix://$(podman machine inspect mos-neo4j --format '{{.ConnectionInfo.PodmanSocket.Path}}' 2>/dev/null || true)`  
   再 `docker compose -f projects/knowledge/kairon/packages/mos/docker-compose.yml up -d`  
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
# Phase 10 optional live backends (default off)
# export MOS_LIVE_KOS=1
# export MOS_LIVE_GBRAIN=1
# export KOS_API_URL=http://localhost:8766
```

完整模板：`docs/operations/memory-os.env.example` → 拷到 `config/memory-os.env`。

## 冒烟（写 + 召回 + as_of）

```bash
source bin/memory-os-env.sh
make memory-os-check                    # light gate（无 Neo4j 也可过）
cockpit memory status --json
# 期望: neo4j_configured/available/recall=true, neo4j_as_of=true, version=0.10.0

cockpit memory write --type semantic --content "Carol founded NeoSoft" \
  --subject Carol --predicate founded --object NeoSoft --json

cockpit memory recall "Carol founded" --intent temporal_fact --json
# 期望 hits 含 neo4j / Carol

# bi-temporal（P10）
cockpit memory recall "Carol" --intent temporal_fact --as-of 2020-01-01T00:00:00Z --json

make memory-os-smoke                    # status + write + recall + as_of 一键
```

## as_of 对照（演示种子）

写入两段**同一主体、不同世界时间窗**的事实，再按 `as_of` 对照召回：

```bash
source bin/memory-os-env.sh
make memory-os-asof-seed                # 或: bash bin/memory-os-asof-seed.sh
# 默认主体 AliceDemo:
#   2019–2021 works_at OldCo
#   2021–     works_at NewCo

# 期望对照（intent=temporal_fact；有 Neo4j 时走图，否则 TemporalShadow）:
cockpit memory recall AliceDemo --intent temporal_fact --as-of 2020-06-01T00:00:00Z --json
# → 命中 OldCo（valid_to=2021 之前）

cockpit memory recall AliceDemo --intent temporal_fact --as-of 2023-01-01T00:00:00Z --json
# → 命中 NewCo

cockpit memory recall AliceDemo --intent temporal_fact --json
# → 当前态（省略 as_of = invalidated_at IS NULL）
```

手动等价写入：

```bash
cockpit memory write --type semantic --content "AliceDemo works_at OldCo" \
  --subject AliceDemo --predicate works_at --object OldCo \
  --valid-from 2019-01-01T00:00:00Z --valid-to 2021-01-01T00:00:00Z --json

cockpit memory write --type semantic --content "AliceDemo works_at NewCo" \
  --subject AliceDemo --predicate works_at --object NewCo \
  --valid-from 2021-01-01T00:00:00Z --json
```

BOS / MCP：`cockpit bos resolve bos://memory/mos/status` · invoke `bos://memory/mos/recall` with kwargs `{query, intent?, as_of?}`。

可选 dependency：`mos[neo4j]` / `mos[graph]`（`neo4j>=5.14`）。
