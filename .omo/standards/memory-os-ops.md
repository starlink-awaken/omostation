---
status: active
lifecycle: contract
owner: governance-team
last-reviewed: 2026-08-05
related:
  - ../_knowledge/decisions/0372-memory-os-control-plane.md
  - ../_truth/registry/memory-os.yaml
  - ../../docs/operations/memory-os-neo4j-local.md
  - ../../docs/operations/memory-os-epic-retro.md
  - ../../docs/operations/memory-os-phase10-retro.md
  - ../../docs/architecture/memory-os.md
type: ssot
---

# Memory OS 运维契约（Phase 8–9）

## 目的

把 Memory OS 从「代码已合」推进到「进程默认可连图」——声明/执行一致。

## SSOT

| 事实 | 路径 |
|------|------|
| 控制面登记 | `.omo/_truth/registry/memory-os.yaml` |
| RBAC 策略表 | `.omo/_truth/registry/memory-rbac.yaml` |
| 架构 | `docs/architecture/memory-os.md` |
| 史诗复盘 | `docs/operations/memory-os-epic-retro.md` |
| 本机图运维 | `docs/operations/memory-os-neo4j-local.md` |
| 环境模板 | `docs/operations/memory-os.env.example` |
| 端口 | `protocols/port-registry.yaml` · 7474 / 7687 |

## 三端入口（必须对齐）

| 入口 | 调用 |
|------|------|
| Cockpit CLI | `cockpit memory status\|recall\|write\|forget\|consolidate\|knowledge-ref` |
| Cockpit HTTP/UI | `/api/memory/*` · `/memory` |
| BOS / Agora MCP | `bos://memory/mos/{write,recall,status,forget,consolidate,knowledge-ref}`（stdio → mos；MCP lifespan 加载 env） |

## 环境注入（必须）

Agent / cockpit / agora / cron 调用 mos 前：

```bash
source bin/memory-os-env.sh
# 或
eval "$(bin/memory-os-env.sh --export)"
```

Agora MCP 启动时也会 best-effort `_load_memory_os_env()`（不覆盖已有非空 env）。

加载优先级（**进程非空 env 永不覆盖**）：

1. 进程现有 env（最高）  
2. 文件合并（后写覆盖前写）：`memory-os.env.example` → `projects/cockpit/.env` → `config/memory-os.env`  
3. 代码内置默认（仅填空）

因此 **本机 `config/memory-os.env` 可覆盖 example 的 `changeme` 密码**；已 export 的 shell 变量仍优先。

关键变量：`NEO4J_URI` · `NEO4J_USER` · `NEO4J_PASSWORD` · `MOS_RBAC` · `MOS_TEMPORAL`

## 跨进程状态

- FileStore（默认 `runtime/omo/_delivery/foundry/mos-consolidate-*.json` 或 `~/.mos/store.json`）持久化 theta/raw **与** `last_consolidate`
- `cockpit memory status` / `/api/memory/status` 暴露 `consolidate` + `adapters` 诚实字段

## Phase 10 能力加深

| 能力 | 开关 / 用法 |
|------|-------------|
| Neo4j bi-temporal as_of | `cockpit memory recall "…" --as-of 2024-06-01T00:00:00Z`（省略=当前态） |
| as_of 演示种子 | `make memory-os-asof-seed`（AliceDemo OldCo→NewCo；对照 2020 vs 2023） |
| Live KOS 检索 | `MOS_LIVE_KOS=1` + `KOS_API_URL`（默认 `http://localhost:8766`） |
| Live gbrain 检索 | `MOS_LIVE_GBRAIN=1`（需 bun + `projects/knowledge/gbrain`） |
| Live gbrain 双写 | `MOS_LIVE_GBRAIN_WRITE=1`（write 时 best-effort `gbrain put`；失败不阻断 dual-track） |

默认全部 off：无 live 依赖时仍用 FileStore fixture，status.adapters 标明诚实状态。

对照命令（种子后）：

```bash
make memory-os-asof-seed
cockpit memory recall AliceDemo --intent temporal_fact --as-of 2020-06-01T00:00:00Z --json  # OldCo
cockpit memory recall AliceDemo --intent temporal_fact --as-of 2023-01-01T00:00:00Z --json  # NewCo
```

## 图库启动

```bash
bash bin/memory-os-neo4j-up.sh          # Docker/podman → brew
bash bin/memory-os-neo4j-up.sh status
```

## 诚实边界

- 无 `NEO4J_URI` → 不写图、recall 不 fan-out neo4j（status 标明）  
- 不得声称 graphiti-core 生产就绪（Cypher FACT + TemporalShadow）  
- 密码不得写入仓内 SSOT（仅 example 默认 `changeme`）

## 治理检查（light gate · blocking）

```bash
python3 bin/gac/check-memory-os-surfaces.py
make memory-os-check
# CI: gac-gate 中 CR-X4-MEMORY-OS-SURFACE-INTEGRITY + cockpit help/discover SSOT pytest
```

必过：SSOT 文件存在 · env.example 键齐全 · 7474/7687 已注册 · cockpit `.env.example` 含 NEO4J_URI · help_map 含 memory · smoke/asof-seed 脚本存在。  
**无 Neo4j 也可过** light gate；图连通性走 `make memory-os-smoke` / status。

## 冷启动一页纸（operator path）

```bash
# 1) 本机私密 env（gitignore）
cp -n docs/operations/memory-os.env.example config/memory-os.env
# 编辑 NEO4J_PASSWORD 等

# 2) 加载 + 图库
source bin/memory-os-env.sh
bash bin/memory-os-neo4j-up.sh          # 可选；无图时 smoke 仍会跑并标明 degrade

# 3) 发现入口
cockpit help                            # 产品地图（与 discover 同源 help_map）
cockpit discover                        # 精简发现页
cockpit help memory                     # 搜 Memory OS / BOS
cockpit --help                          # 紧凑快速入口（非 70 命令墙）

# 4) 工作台（含 Memory OS 健康行）
cockpit status

# 5) 实路径冒烟
make memory-os-check
make memory-os-smoke
# 或: bash bin/memory-os-smoke.sh

# 6) as_of 对照（可选）
make memory-os-asof-seed

# 7) Agent / 新用户冷启动
cockpit agent-onboard
cockpit quickstart
```
