---
lifecycle: contract
owner: runtime-team
last_updated: 2026-07-31
review-state: metadata-only
metadata-migrated-at: 2026-07-31
title: Knowledge Foundry — 运营 SOP (P79 Phase 5)
type: doc
---
# Knowledge Foundry — 运营 SOP (P79 Phase 5)

> **Status**: ACTIVE · **Owner**: governance-team · **Last updated**: 2026-07-08

## 0. 概述

Foundry = omostation 治理 cron 系统，每 6h 自动执行 10 个 deck，输出到 `runtime/omo/_delivery/foundry/`。

## 1. 10-deck 编排

| 时间 | Deck | 命令 | 超时 |
|------|------|------|:----:|
| 0:00 | omo-sync | `omo state sync --dry-run --json` | 120s |
| 0:30 | agent-compliance | `agent-workflow.py compliance --json` | 60s |
| 1:00 | p74-silent | `agent-workflow.py compliance --json` (P74 drill) | 60s |
| 2:00 | mof-drift | `bin/mof-drift` | 120s |
| 3:00 | m4-health | `bin/mof/m4-health-score.py --emit` | 60s |
| 4:00 | bootloader | `bin/gac/omostation-bootloader.py audit` | 60s |
| 5:00 | debt-closed | `bin/gac/debt-closed-per-feature.py` | 60s |
| 5:30 | submodule-bump | `bin/ssot/submodule-bump-check.py` | 30s |
| 6:00 | brief-gen | `bin/mof/generate-brief.py --write` | 60s |
| 6:30 | port-governance | `bin/_archive/2026-08-conv3/port-governance-deck.py` | 120s |
| 6:45 | memory-os-consolidate | `bin/_archive/2026-08-conv3/memory-os-consolidate-deck.py` (default dry-run; `MOS_CONSOLIDATE_LIVE=1` for live) | 900s |

## 2. 输出

```
runtime/omo/_delivery/foundry/
├── {timestamp}-{run_id}.yaml          # 完整 run record
├── metrics-{date}.jsonl               # 统一 metrics
├── FAIL-{run-id}.yaml                 # fail record
└── port-governance-{ts}.yaml          # port deck 输出
```

## 3. 排查

- **deck fail**: 查看对应 stdout/stderr; 重试用 `uv run python bin/gac/knowledge-foundry-cron.py`
- **port-governance fail**: 运行 `uv run --with pyyaml python bin/_archive/2026-08-conv3/port-governance-deck.py` 查看详情
- **cc-switch fail**: 环境凭证问题, 不影响 code health

## 4. 相关

- `bin/gac/knowledge-foundry-cron.py` — 主 cron 脚本
- `bin/_archive/2026-08-conv3/port-governance-deck.py` — v2 新增 deck
- `docs/operations/knowledge-foundry-monitor.md` — cockpit 面板文档

---

## 5. 知识处理全链路架构（PR #740 起生效，ADR-0294）

> **Last updated**: 2026-08-01 · **Ref**: `.omo/_knowledge/decisions/0294-knowledge-gateway-decoupling-and-event-pipeline.md`

### 5.1 全链路数据流

```
用户或 Agent
    │
    ▼  POST /api/knowledge/put
╔═══════════════════════════╗
║  cockpit api_knowledge    ║  ← L3 服务层
║  (network-first resolver) ║
╚═══════════╦═══════════════╝
            │  1. 写入 data/cards/{slug}.md
            │  2. 非阻塞 publish_event → card_updated
            ▼
╔═══════════════════════════════════════╗
║  Agora EventBus                       ║  ← I0 网关层
║  bos://memory/events/card_updated     ║  ← 规范域 (ADR-0372 / api_knowledge)
║  bos://brain/events/card_updated      ║  ← 遗留 dual-accept (ADR-0294)
╚═══════════════════╦═══════════════════╝
            │  推送/回调 (dual-subscribe)
            ▼
╔═══════════════════════════╗
║  KnowledgeIndexer         ║  ← L3 消费者（cockpit 内）
║  (knowledge_indexer.py)   ║
║  + KOS / LanceDB          ║
╚═══════════════════════════╝
            │
            ▼  向量化 & 索引写入
    GET /api/knowledge/search
    └─ 网络解析 → Agora /bos/resolve → 召回
```

### 5.2 关键配置

| 环境变量 | 默认值 | 说明 |
|:---|:---|:---|
| `AGORA_HTTP_ENDPOINT` | `http://127.0.0.1:7422` | Agora 网关地址 |
| `KNOWLEDGE_CARDS_DIR` | `WORKSPACE_ROOT/data/cards` | 卡片存储目录 |

### 5.3 运维排查（知识处理链路）

| 症状 | 排查步骤 |
|:---|:---|
| `/api/knowledge/search` 返回空结果 | 1. 检查 Agora 是否在 `:7422` 在线；2. 检查 `data/cards/` 是否有 Markdown 文件；3. 看 Indexer 日志是否有 `card_updated` 消费记录 |
| PUT 后搜索没有立即更新 | 1. 检查 `agora-events.json` 中是否有 `card_updated` 事件记录；2. 确认 `KnowledgeIndexer` 已启动订阅 |
| `test_put_emits_card_updated_event` 失败 | httpx Mock 路径验证，检查 `_AGORA_HTTP_ENDPOINT` 是否被测试环境覆盖 |
| Agora 离线时 `/search` 是否受影响 | 不受影响 — 触发兼容降级路径（进程内 `cockpit.adapters.agora`），有 2s 超时保护 |

### 5.4 接口契约摘要

- **Producer (canonical)**: `publish_event` → `bos://memory/events/card_updated`（`api_knowledge` PUT）
- **Consumer (dual-accept)**: `KnowledgeIndexer` 订阅 `memory` + `brain` 两 URI（ADR-0372 D5）
- **完整契约**: ADR-0294 + ADR-0372 · registry `memory-os.yaml::event_migration`
