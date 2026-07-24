---
title: Phase 45 W1-W3 re-verify — 7 acceptance endpoints (STRAT-P80 T1.2)
date: 2026-07-24
type: audit
front: T1.2
---

# Phase 45 re-verify (7 endpoints)

## SSOT

- plan: `.omo/_knowledge/decisions/phase45-plan.md` §验收标准
- historical closeout: `.omo/_knowledge/audits/2026-06-14-p45-w1-w2-w3-closeout.md`

## Endpoint matrix (remeasured 2026-07-24; bos_stdio corrected)

| # | Endpoint | Result | Evidence | Residual |
|---|----------|--------|----------|----------|
| 1 | `health_scan.ticks_ok` | **GREEN** | cron_service scheduler ticks (`projects/runtime/.../scheduler.py`); health SSOT present | — |
| 2 | `cron.tick_timeout_seconds: 30` | **NEEDS-HUMAN** | Found `TICK_INTERVAL` default 15 (`config.py`); **no** explicit `tick_timeout_seconds=30` | `needs-human-p80-phase45-tick-timeout.yaml` |
| 3 | `debt.auto_seeded_last_7d` | **GREEN** | debt items mtime within 7d + auto-seed code hit | — |
| 4 | `agora_gateway.health_check: live` | **NEEDS-HUMAN** | `:9000/health` **down**; agora runs MCP/SSE; Minerva `:8765` is **not** agora; W2.1 PID tests remain | `needs-human-p80-phase45-agora-health.yaml` |
| 5 | `debt_adjusted.computed: live` | **GREEN** | `system.yaml` debt_adjusted_* fields present | — |
| 6 | `task_files: < 200` | **NEEDS-HUMAN** | recursive `.omo/tasks/**/*.yaml` = **477** | `needs-human-p80-phase45-task-entropy.yaml` |
| 7 | `bos_stdio_ratio: < 65%` | **NEEDS-HUMAN** | Live `bos-services.yaml`: **169** services; stdio-ish (`stdio`+`mcp_stdio`)=**117**; **ratio=117/169≈0.692 ≥ 0.65** | `needs-human-p80-phase45-bos-stdio.yaml` |

### bos_stdio_ratio recompute (authoritative)

```text
n_services = 169
class_counts = {stdio:80, mcp_stdio:37, internal:22, inline:27, mcp_proxy:2, http:1}
stdio_ish = 80+37 = 117
ratio = 117/169 ≈ 0.6923  → FAILS plan threshold < 0.65
```

Earlier GREEN claim used a wrong denominator (208 nested transport walks). **Retracted.**

## Summary

- **GREEN: 3/7** (ticks_ok, debt auto-seed, debt_adjusted)
- **NEEDS-HUMAN: 4/7** (tick timeout, agora /health, task entropy, bos_stdio_ratio)
- Does **not** claim full Phase45 plan green
- W2.1 PID probe fallback path exists in agora tests when HTTP health unavailable

## Capture

- `phase45-seven-endpoints.json` (corrected)
- `bos-stdio-recompute.json`
