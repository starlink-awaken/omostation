---
lifecycle: history
owner: engineering-team
last_updated: 2026-08-05
related:
  - ./memory-os-phase7-retro.md
  - ./memory-os-neo4j-local.md
  - ./memory-os.env.example
  - ../../.omo/standards/memory-os-ops.md
  - ../../.omo/_knowledge/decisions/0372-memory-os-control-plane.md
title: Memory OS Phase 8 — 剩余工作收口（配置 / 文档 / 治理）
type: doc
---

# Memory OS Phase 8 — 剩余工作收口（配置 / 文档 / 治理）

## 交付

| 项 | 结果 |
|----|------|
| 环境注入 | `bin/memory-os-env.sh` + `cockpit.web.memory_env`（dashboard / cmd_dashboard / api_memory） |
| 环境模板 | `docs/operations/memory-os.env.example` · cockpit `.env.example` 含 NEO4J_* |
| 端口 SSOT | `protocols/port-registry.yaml` · 7474 HTTP · 7687 Bolt |
| 运维契约 | `.omo/standards/memory-os-ops.md` |
| 治理检查 | `bin/gac/check-memory-os-surfaces.py` · `make memory-os-check` |
| Registry | memory-os.yaml phase8 + env_defaults + neo4j adapter 状态 |

## 操作

```bash
source bin/memory-os-env.sh
bash bin/memory-os-neo4j-up.sh
make memory-os-check
# cockpit dashboard 子进程自动带上 NEO4J_* → /api/memory 与 /memory 面板可见图
```

## 三端接线（后续补齐）

| 入口 | 状态 |
|------|------|
| `cockpit memory …` | ✅ CLI 一等子命令 |
| `/api/memory/*` · `/memory` | ✅ HTTP/UI |
| `bos://memory/mos/*`（含 knowledge-ref） | ✅ Agora BOS stdio + `--with neo4j` |
| Agora MCP lifespan env | ✅ `_load_memory_os_env` |

## 诚实边界

- `config/memory-os.env` 在 gitignore 的 `config/` 下，仅本机；仓内只有 example  
- 图库进程（brew/docker）仍需 `memory-os-neo4j-up.sh` 单独启动  
- 未宣称 graphiti-core / Mem0 生产闭环
