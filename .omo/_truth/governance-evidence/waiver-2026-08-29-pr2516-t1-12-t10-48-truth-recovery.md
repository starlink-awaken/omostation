---
lifecycle: entry
owner: auto-fix-loop
last_updated: 2026-08-29
---
# PR #2516 T1-12/T10-48 Truth Recovery Waiver

Date: 2026-08-29

## Exact User Waiver

本次 #2516 post-merge T1-12/T10-48 truth recovery 跳过 workflow start，允许使用 AGCP_REQUIREMENT_ITERATION_GATE=0；仅限 docs/plans/3y-bet-ledger.yaml 只将 BET-Y1Q3-T10-48 与 BET-Y1Q3-T1-12 两个完整条目恢复为 merge parent d2b749bc9096b18c2847f4783ed826155b31bdaf 的真值（T10-48=done 且保留其完成证据；T1-12=candidate、无 done_at、engineering=IN_PROGRESS、operational/value=NOT_PROVEN、overall=evaluating，并恢复 #2516 删除的既有字段），.omo/_knowledge/retros/BET-Y1Q3-T1-12.md 仅删除 #2516 新增的孤立 `|||||||` 标记及虚假正向 canary 段，以及 .omo/_truth/governance-evidence/waiver-2026-08-29-pr2516-t1-12-t10-48-truth-recovery.md 记录本句；不得修改其他 BET、Spec、accepted_specifications、实现代码、测试、registry、gitlink、branch protection、运行态或用户配置；从最新 main 建唯一 truth-recovery PR，ledger lint、必要 CI 与 post-merge Governance Check 全绿后退役 clone。

## Execution Scope

- Workflow run: none; user explicitly waived workflow start for this recovery.
- Gate bypass: `AGCP_REQUIREMENT_ITERATION_GATE=0` authorized only for staging/commit of this bounded recovery.
- Merge parent truth source: `d2b749bc9096b18c2847f4783ed826155b31bdaf`.
- Current main at start: `origin/main=dc4f0598e2582f430c68c3952bbe38b02b244c76`.
- Current clone HEAD at start: `dc4f0598e2582f430c68c3952bbe38b02b244c76`.

## Concurrent Satisfaction Disposition

`BET-Y1Q3-T10-48` was already correctly `done` on latest main with newer valid receipts from PRs #2530/#2534. This recovery did not rewrite the `BET-Y1Q3-T10-48` ledger bytes.

## Execution Note

The merge-parent T1-12 block carried duplicate `evidence`, `workflow`, and `write_surfaces` keys. This follow-up canonicalizes those duplicate keys into one `evidence` mapping containing E0 through E9 and one effective `workflow`/`write_surfaces` block, preserving the later full parent semantics without adding authorized surfaces or changing the completion matrix.

## Authorized Surfaces

- `docs/plans/3y-bet-ledger.yaml`
- `.omo/_knowledge/retros/BET-Y1Q3-T1-12.md`
- `.omo/_truth/governance-evidence/waiver-2026-08-29-pr2516-t1-12-t10-48-truth-recovery.md`

## Forbidden Surfaces

No changes are authorized to any other BET, Spec, `accepted_specifications`, implementation code, tests, registry, gitlink, branch protection, runtime state, or user configuration.
