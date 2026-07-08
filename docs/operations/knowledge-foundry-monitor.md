---
status: draft
lifecycle: operations
owner: governance-team
last-reviewed: 2026-07-07
related:
  - ../../../.omo/_knowledge/decisions/0160-p76-phase6-foundry-runtime.md
  - ../../../.omo/_knowledge/decisions/0159-p76-phase5-foundry.md
  - ../../../docs/architecture/knowledge-foundry-cron.md
---

# Knowledge Foundry Monitor (cockpit L3 出口) — P76 Phase 6

> **For agentic workers**: 本文档是 DRAFT, 是 P76 Phase 6 真正集成的 cockpit 面板文档。
> 数据由 `bin/knowledge-foundry-cron.py` 写入 `runtime/omo/_delivery/foundry/` 派生面 (gitignored)。
> 来源命令: `cockpit governance evolution foundry --json` (Phase 7 实施)

## 0. 总览 — 单页 dashboard

```
┌──────────────────────────────────────────────────────────────────────┐
│          KNOWLEDGE FOUNDRY MONITOR (cockpit L3 出口)              │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  Last run:    2026-07-07T03:30Z (run_id=e2d8f6c1)                  │
│  Last cycle:  6h ✓                                                      │
│  Cycle count: 237 (since 2026-04-01)                                  │
│  Health:      9/9 ok (100%) ✅                                         │
│                                                                      │
│  Deck timings (last cycle):                                          │
│   0:00 omo-sync          ████░░░░░░░░░░░░░░  8.3s / 30s                │
│   0:30 agent-compliance  ██░░░░░░░░░░░░░░░░  2.1s / 60s                │
│   1:00 p74-silent        ███░░░░░░░░░░░░░░░  1.8s / 30s                │
│   2:00 mof-drift         ████████░░░░░░░░░░  42.0s / 120s             │
│   3:00 m4-health-score   ██░░░░░░░░░░░░░░░░  3.2s / 60s                │
│   4:00 bootloader        █████████░░░░░░░░░  47.5s / 60s               │
│   5:00 debt-closed       █░░░░░░░░░░░░░░░░░  0.4s / 60s                │
│   5:30 submodule-bump    ██░░░░░░░░░░░░░░░░  1.6s / 30s                │
│   6:00 brief-gen         █░░░░░░░░░░░░░░░░░  0.2s / 60s                │
│   +v2  port-governance   P78: hardcoded + catalog health              │
│                                                                      │
│  Trigger conditions (last 7 days):                                   │
│   ⬆ gac_local_gate FAIL: 2 → 0 (P76 phase 1+2 修复)                │
│   ⬆ submodule stale:   5+ → 0 (P76 phase 4 修复)                    │
│   ⬆ LAYER violations:  ?  → 9 (P76 phase 2 真证据)                 │
│   ─ debt-closed ratio: 0.688 维持 (≥ 0.5 threshold)                │
│   ⬆ governance score:   100 A+ 维持                                  │
│                                                                      │
│  Failures (last 30 days): 0                                          │
│  Re-runs scheduled: 0                                                │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

## 1. 字段含义

| 字段 | 含义 |
|------|------|
| `Last run` | 最近一次 9-deck 编排完成的 run_id 与 UTC timestamp |
| `Last cycle` | 距上次成功跑的间隔, 6h 应有 4 次/天 |
| `Cycle count` | 自 foundry 启动以来跑的次数 |
| `Health` | 9-deck 中 ok 数 / 9, threshold=80% (7/9) |
| `Deck timings` | 各 deck 实际耗时 / soft quota |
| `Trigger conditions` | Foundry 检测触发的具体发现 (附带修复证据) |
| `Failures` | (run fail 重跑后) 30 天累计 |
| `Re-runs scheduled` | 下一次重跑时间 |

## 2. 数据来源

```bash
# Foundry 写 ledger (派生面, 不入仓)
ls runtime/omo/_delivery/foundry/ | wc -l  # 总 cycle 数
tail -1 runtime/omo/_delivery/foundry/<latest>.yaml  # 最新一次 9-deck 结果

# Cockpit 拉取 (Phase 7 实施)
cockpit governance evolution foundry status --json
```

## 3. 阈值策略 (与 GaC 同步)

| 指标 | threshold | action |
|------|-----------|--------|
| Health ≥ 80% | 7/9 ok | 维持; 100% gold |
| Health 50-80% | 5-6/9 ok | 警示; bootloader 自动产 ADR draft |
| Health < 50% | 0-4/9 ok | hard 报警; agent must run closeout |
| Cycle missed > 1 | > 6h 间隔 | radar_cron 后端问题; 重新调度 |
| Failure retry | 1 次后仍 fail | 写 FAIL-<run-id>.yaml |

## 4. 与 P74 workflow solidification 的关系

- **P74**: 检测 silent workflow (≥1 周无 register 事件), 触发 ADR draft
- **P76 Phase 6**: 监控 9-deck 全 6h 跑, 任何一个 fail 都跳到 P74 自检机制

两者形成 **双循环雷达**:
1. P74 radar_cron 每 6h → foundry scan
2. P76 foundry scan → P74 silent detector → ADR draft

## 5. 关联

- ADR-0160 (本 phase 主 ADR)
- docs/architecture/knowledge-foundry-cron.md (Phase 5 雏形)
- bin/knowledge-foundry-cron.py (实施)
- CR-FOUNDRY-MONITOR 规则 (162 rules)

---

*最后更新: 2026-07-07 · P76 Phase 6 cockpit 监控面板 · DRAFT*
