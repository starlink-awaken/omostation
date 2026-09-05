---
status: active
lifecycle: entry
owner: auto-fix-loop
last-reviewed: 2026-08-30
type: ssot
---
# AGCP_REQUIREMENT_ITERATION_GATE Waiver — fix-observable-compass-radar

Date: 2026-08-30

## Exact User Waiver

本次 fix-observable-compass-radar (worktree=`work/fix-observable-compass-radar`) 跳过 workflow start claim 的 BET scope 强校验，允许使用 `AGCP_REQUIREMENT_ITERATION_GATE=0`；仅限修复 `bin/gac/maturity-scorecard.py::score_observable` 的 timeout 过短问题：原默认 120s 远短于 `bin/compass_radar.py --dry-run` 实际耗时 ~178s，导致 observable 维度永远被误判为"output unclear"（score=7），而 compass_radar 实际已输出 `maturity_score: 8.2/10.0` 字符串（满足 has_maturity 条件，应得 score=10）。修复方法：score_observable 的 `run()` 显式传 `timeout=300`。以及本 waiver 文件记录本身；不得修改其他 score_* 维度、其他文件、其他 BET、registry、gitlink、branch protection、运行态或用户配置；从最新 main 建唯一 fix-observable PR，CI 全绿后退役 worktree。

## Execution Scope

- Workflow run: none; user explicitly waived scope-strict claim for this bounded fix.
- Gate bypass: `AGCP_REQUIREMENT_ITERATION_GATE=0` authorized only for staging/commit of these 2 specific surface updates.
- Base: `omostation-root/main=ee103c8cc` (latest main at start).
- Worktree branch: `work/fix-observable-compass-radar` (created via `gac-worktree.sh claim`).

## Authorized Surfaces

- `bin/gac/maturity-scorecard.py` (line 52 `score_observable` timeout addition only)
- `.omo/_truth/governance-evidence/waiver-2026-08-30-fix-observable-compass-radar.md` (this file)

## Forbidden Surfaces

No changes are authorized to any other script, BET, Spec, `accepted_specifications`, runtime state, registry, branch protection, or user configuration.

## Validation Evidence

Before commit:
- `bin/gac/maturity-scorecard.py --json` (full): overall **8.0 → 8.5** (+0.5); observable **7 → 10** (+3).
- `bin/compass_radar.py --dry-run` real runtime: ~178s (was being killed by 120s scorecard timeout).
- `bin/gac/drift-sweep.py --json`: still 16/16 pass (regression-free).