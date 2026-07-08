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
| 3:00 | m4-health | `bin/m4-health-score.py --emit` | 60s |
| 4:00 | bootloader | `bin/omostation-bootloader.py audit` | 60s |
| 5:00 | debt-closed | `bin/debt-closed-per-feature.py` | 60s |
| 5:30 | submodule-bump | `bin/submodule-bump-check.py` | 30s |
| 6:00 | brief-gen | `bin/generate-brief.py --write` | 60s |
| 6:30 | port-governance | `bin/decks/port-governance-deck.py` | 120s |

## 2. 输出

```
runtime/omo/_delivery/foundry/
├── {timestamp}-{run_id}.yaml          # 完整 run record
├── metrics-{date}.jsonl               # 统一 metrics
├── FAIL-{run-id}.yaml                 # fail record
└── port-governance-{ts}.yaml          # port deck 输出
```

## 3. 排查

- **deck fail**: 查看对应 stdout/stderr; 重试用 `uv run python bin/knowledge-foundry-cron.py`
- **port-governance fail**: 运行 `uv run --with pyyaml python bin/decks/port-governance-deck.py` 查看详情
- **cc-switch fail**: 环境凭证问题, 不影响 code health

## 4. 相关

- `bin/knowledge-foundry-cron.py` — 主 cron 脚本
- `bin/decks/port-governance-deck.py` — v2 新增 deck
- `docs/operations/knowledge-foundry-monitor.md` — cockpit 面板文档
