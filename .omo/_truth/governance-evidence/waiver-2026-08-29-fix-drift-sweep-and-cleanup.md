---
lifecycle: entry
owner: auto-fix-loop
last_updated: 2026-08-29
---
# AGCP_REQUIREMENT_ITERATION_GATE Waiver — fix-drift-sweep-and-cleanup

Date: 2026-08-29

## Exact User Waiver

本次 fix-drift-sweep-and-cleanup (worktree=`work/fix-drift-sweep-and-cleanup`) 跳过 workflow start claim 的 BET scope 强校验，允许使用 `AGCP_REQUIREMENT_ITERATION_GATE=0`；仅限修复以下 4 项 drift 问题：(1) `bin/gac/drift-sweep.py:41` 引用已退役的 `bin/gac/mof-capabilities-drift-check.py` → 改回 `bin/mof/check-mof-capabilities-drift.py` (当前实际路径)；(2) `bin/gac/maturity-scorecard.py:96` 的 `drift-sweep` timeout=60 太短，drift-sweep 实际跑 134s → 调到 180s；(3) `.agents/skills/spine-value-pipeline/SKILL.md:37` 引用不存在的 `bin/memory/diff_engine.py` → 仅保留 `bos://memory/mos/diff` 描述；(4) `.omo/state/system.yaml` health_score_evidence 因 scorecard 提升 7.0→8.2 自动从 94.0 跳到 100.0（无需手动改）；以及本 waiver 文件记录本身；不得修改其他 BET、Spec、accepted_specifications、实现代码、测试、registry、gitlink、branch protection、运行态或用户配置；从最新 main 建唯一 fix-drift PR，CI 全绿后退役 worktree。

## Execution Scope

- Workflow run: none; user explicitly waived scope-strict claim for this bounded fix.
- Gate bypass: `AGCP_REQUIREMENT_ITERATION_GATE=0` authorized only for staging/commit of these 4 specific surface updates.
- Base: `omostation-root/main=78b30b71f` (latest main).
- Worktree branch: `work/fix-drift-sweep-and-cleanup` (already created via `gac-worktree.sh claim`).

## Authorized Surfaces

- `bin/gac/drift-sweep.py` (line 41 path fix only)
- `bin/gac/maturity-scorecard.py` (line 96 timeout fix only)
- `.agents/skills/spine-value-pipeline/SKILL.md` (line 37 dangling reference only)
- `.omo/state/system.yaml` (auto-updated by evidence-smoke; no manual edit)
- `.omo/_truth/governance-evidence/waiver-2026-08-29-fix-drift-sweep-and-cleanup.md` (this file)

## Forbidden Surfaces

No changes are authorized to any other script, BET, Spec, `accepted_specifications`, runtime state, registry, branch protection, or user configuration.

## Validation Evidence

Before commit:
- `python3 bin/gac/drift-sweep.py --json`: 16/16 checks pass (was: 14 pass / 1 fail / 1 skip).
- `python3 bin/gac/maturity-scorecard.py --skip-observable --json`: overall 7.0 → **8.2** (+1.2); optimizable 5 → **9** (+4).
- `python3 bin/ssot/script-registry.py validate`: 530 scripts registered, VALIDATION PASSED.