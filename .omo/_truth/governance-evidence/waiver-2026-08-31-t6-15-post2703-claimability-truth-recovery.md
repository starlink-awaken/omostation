---
schema: workflow-waiver/v1
lifecycle: history
owner: governance-team
created: 2026-08-31
last_updated: 2026-08-31
title: BET-Y1Q3-T6-15 post-2703 claimability truth recovery waiver
type: doc
value_indicator_policy: false
---

# BET-Y1Q3-T6-15 post-#2703 claimability truth recovery waiver

waiver: user-explicit
when: 2026-08-31
who: xiamingxing
quote: "给你全部授权"
approved_package: /Users/xiamingxing/Documents/学习进化/基建架构/2026-08-31-post2796-concurrency-drift-recovery-authorization-package.md
approved_package_sha256: 196807240f6e5b5835f258e64451b968592b20f2a2ed33d8ff8c5237f58678b3
approved_section: 3
gate_bypass: 1
no-run-id: true
value_indicator_policy: false

## Exact authorization

> 本次 #2703 post-merge BET-Y1Q3-T6-15 claimability truth recovery 的 current-main verification amendment 自举跳过 workflow start，允许使用 `AGCP_REQUIREMENT_ITERATION_GATE=0`；执行 fixed ref 为 root main `730f5871f474815343f57f5cf4d245b2d6a34a80` 或经 T6 四路径与规范化 T6 对象逐字段证明的等价后继，恢复真值 ref 仍为 `0244bb49e48a43917b238993fa23125a3c43fe88`，#2703 merge 仍为 `371a4d44d599eaf55e0a773c303bbd7a1446336c`；唯一 recovery PR 仅限四路径：`docs/plans/3y-bet-ledger.yaml` 只将 BET-Y1Q3-T6-15 完整条目恢复为上述 ref 的 candidate、无 done_at、engineering=NOT_STARTED、operational/value=NOT_PROVEN、overall=evaluating、accepted Spec 1.0.1 真值，`docs/reports/2026-08-28-post2408-main-recovery-closeout.md` 只删除 #2703 恢复/新增的 R2b executed 段，`.omo/_knowledge/retros/BET-Y1Q3-T6-15.md` 只删除 #2703 恢复/新增的两段 R2b 收账，以及 `.omo/_truth/governance-evidence/waiver-2026-08-31-t6-15-post2703-claimability-truth-recovery.md` 记录本句、fixed refs、dry-run 与 lint baseline；原第6节其余禁止项、唯一 PR、post-merge Governance Check 与退役要求全部保持不变；仅将“ledger lint 全绿”精确修订为：必须运行完整 `uv run --with pyyaml python bin/plan/bet-ledger.py lint`，T6-15 finding 必须为 0，全部非 T6 finding 必须按完整 ERROR 行排序形成与 accepted base 完全相同的 44 项 multiset，其 SHA-256 必须精确等于 `7f5e459aabe196cd6be91dd3cb8a4332a473ce8284e1953e5abbe6a1a7ca932e`（11 项 `COMPLETION_FILE_DIGEST_MISMATCH`、3 项 `OVERALL_STATE_MISMATCH`、30 项 `SPEC_BINDING_REQUIRED`），不得新增、删除、掩盖、重分类或借本 PR 修复其他 BET；本修订不证明或接受该 baseline；required PR CI、exact-SHA post-merge Governance Check、T6 fixed-ref equality、other-BET object digest equality 与 diff/check 仍须全绿；不得修改其他 BET、Spec、plan、accepted_specifications、实现代码、测试、CI、registry、gitlink、运行态、external evidence 或用户配置。

## Fixed evidence

- execution base: `0801c6fc8c2721edf8c4d6058e99a8cc1a7e6e25`;
- approved equivalent base: `730f5871f474815343f57f5cf4d245b2d6a34a80`;
- recovery truth: `0244bb49e48a43917b238993fa23125a3c43fe88`;
- #2703 merge: `371a4d44d599eaf55e0a773c303bbd7a1446336c`;
- T6 object digest at approved and execution bases:
  `87b0e10404cbb61e83df809ae4bda89dcfbb03c83d0254fb4221d9f82d8a09b8`;
- full lint: 44 non-T6 findings, zero T6 findings, multiset SHA-256
  `7f5e459aabe196cd6be91dd3cb8a4332a473ce8284e1953e5abbe6a1a7ca932e`;
- prior dry-run failure: `BET_STATUS_NOT_STARTABLE` because current T6 status was `done`;
- prior run `20260830T065700Z-bet-execution-962232be` was blocked and had zero live/stale locks.

## Boundaries

This waiver restores claimability only. It does not bind Spec 1.0.2, execute
host operations, write external evidence, prove historical retention/current
recoverability, or promote engineering, operational, or personal value.
