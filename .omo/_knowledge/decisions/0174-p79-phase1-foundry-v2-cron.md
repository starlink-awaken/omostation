---
status: ACCEPTED
lifecycle: decision
owner: governance-team
last-reviewed: 2026-07-08
related:
  - STRAT-P79-strategic-roadmap.md
  - 0173-p78-phase2-baseline-foundry-v2.md
  - ../../../../../bin/knowledge-foundry-cron.py
  - ../../../../../bin/decks/port-governance-deck.py
  - ../../../../../docs/operations/knowledge-foundry-monitor.md
supersedes: []
---

# ADR-0174: P79 Phase 1 — Foundry v2 cron 集成 (10-deck)

> **For agentic workers**: 本 ADR 是 ACCEPTED 状态 (2026-07-08), P79 STRAT § 2 Phase 1 收口.

## 0. TL;DR

| 交付 | 状态 | 关键产物 |
|------|:---:|---------|
| **10-deck cron 编排** | ✅ | `knowledge-foundry-cron.py`: 6:30 port-governance 加入 |
| **port-governance deck** | ✅ | `bin/decks/port-governance-deck.py` (4 checks) |
| **dry-run 更新** | ✅ | 列 10 deck 而非 9 |
| **cron docstring** | ✅ | schedule 表含 6:30 entry |
| **foundry monitor** | ✅ | docs/operations/knowledge-foundry-monitor.md |
| **catalog 65 原则** | ✅ | P79-1..5 新原则 |

## 1. 决策

### 1.1 WHY

P79 STRAT Phase 1 入口: port-governance deck 已创建但未加入 cron 编排.
Foundry v2 的"第 10 deck"有检测能力但无自动化 — 跟没做一样.

### 1.2 WHAT

`knowledge-foundry-cron.py`:
- schedule 新增 `6:30 port-governance`
- main() 新增 `run_tool("6:30-port-governance", ...)` 调用
- dry-run 消息更新为 10 deck

### 1.3 schedule

```
0:00  omo-sync
0:30  agent-compliance
1:00  p74-silent
2:00  mof-drift
3:00  m4-health-score
4:00  bootloader
5:00  debt-closed
5:30  submodule-bump
6:00  brief-gen
6:30  port-governance  ← NEW (Foundry v2)
```

## 2. 沉淀原则

| # | 原则 | 含义 |
|---|------|------|
| P79-1 (沿用) | **baseline-replay-after-phase** | 每 phase 收口后重放 governance baseline |
| P79-2 (沿用) | **bin-config-ssot-alignment** | bin/config 端口引用必须与 port-registry 一致 |
| P79-3 (沿用) | **foundry-deck-per-governance-axis** | 每治理轴对应一个 foundry deck |
| P79-4 (沿用) | **catalog-health-metric** | 原则数和 GaC 规则数作为 foundry metrics |
| P79-5 (沿用) | **zero-planned-tasks** | 治理收口目标: planned tasks 清零 |

> 注: P79-1..5 已在 ADR-0173 沉淀, 本 phase 沿用.
