---
lifecycle: entry
owner: auto-fix-loop
last_updated: 2026-08-30
---
# AGCP_REQUIREMENT_ITERATION_GATE Waiver — fix-adr-link-validator

Date: 2026-08-30

## Exact User Waiver

本次 fix-adr-link-validator (worktree=`work/fix-adr-link-validator`) 跳过 workflow start claim 的 BET scope 强校验，允许使用 `AGCP_REQUIREMENT_ITERATION_GATE=0`；仅限修复 `bin/gac/adr-link-validator.py` 中 repo-root relative link 解析缺陷：原代码仅按 `(f.parent / target).resolve()` 解析，导致指向 `.agents/skills/omlxc-compute-fabric/SKILL.md` 的 repo-root relative link 被误判为 broken（实际文件存在于 repo root）。修复方法：先尝试 `REPO_ROOT / target`，失败再 fallback 到 `f.parent / target`，保持向后兼容 ADR-local path。以及本 waiver 文件记录本身；不得修改其他 validator 逻辑、其他 ADR、其他 BET、registry、gitlink、branch protection、运行态或用户配置；从最新 main 建唯一 fix-validator PR，CI 全绿后退役 worktree。

## Execution Scope

- Workflow run: none; user explicitly waived scope-strict claim for this bounded fix.
- Gate bypass: `AGCP_REQUIREMENT_ITERATION_GATE=0` authorized only for staging/commit of these 2 specific surface updates.
- Base: `omostation-root/main=78fb360d4` (latest main at start).
- Worktree branch: `work/fix-adr-link-validator` (created via `gac-worktree.sh claim`).

## Authorized Surfaces

- `bin/gac/adr-link-validator.py` (repo-root fallback addition only)
- `.omo/_truth/governance-evidence/waiver-2026-08-30-fix-adr-link-validator.md` (this file)

## Forbidden Surfaces

No changes are authorized to any other script, BET, Spec, `accepted_specifications`, runtime state, registry, branch protection, or user configuration.

## Validation Evidence

Before commit:
- `uv run --with pyyaml python3 bin/gac/adr-link-validator.py`: **PASS** — All 408 ADR links valid (was: FAIL 1 broken link).
- `python3 bin/gac/maturity-scorecard.py --skip-observable --json`: overall **7.8 → 8.2** (+0.4); traceable 6 → **8** (+2).
- `python3 bin/gac/drift-sweep.py --json`: still 16/16 pass (regression-free).