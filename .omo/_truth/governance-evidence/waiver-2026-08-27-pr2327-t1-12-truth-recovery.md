---
lifecycle: contract
owner: xiamingxing
last_updated: 2026-08-27
review-state: user-authorized
title: #2327 T1-12 premature done/value truth recovery waiver
type: doc
---

# #2327 T1-12 premature done/value truth recovery waiver

```text
waiver: user-explicit
when: 2026-08-28 Asia/Shanghai (2026-08-27 UTC evidence date)
who: xiamingxing
scope: docs/plans/3y-bet-ledger.yaml::BET-Y1Q3-T1-12 status/done_at/value.status/overall_state; this waiver evidence file
reason: PR #2327 promoted T1-12 to done and value accepted even though the BET non-goals exclude Human Verdict and principal-bound decision_outcome, and the user had explicitly required candidate / blocked / NOT_PROVEN.
risk: This truth-only repair skips workflow start and intentionally preserves every completion evidence ref/digest and both engineering and operational axes.
gate_bypass: 1
no-run-id: true
```

## User authorization

The user explicitly approved the immediately preceding exact recovery scopes with:

> 我给你完整授权，你继续推进吧。

The bounded T1-12 scope approved by that response is:

> 本次 #2327 post-merge BET-Y1Q3-T1-12 premature done/value truth recovery 跳过 workflow start，允许使用 AGCP_REQUIREMENT_ITERATION_GATE=0；仅限 docs/plans/3y-bet-ledger.yaml 中 BET-Y1Q3-T1-12 将 status: done 恢复为 candidate、删除 done_at、将 completion_evidence.axes.value.status: ACCEPTED 恢复为 NOT_PROVEN、将 completion_evidence.overall_state: outcome_accepted 恢复为 blocked，以及 .omo/_truth/governance-evidence/waiver-2026-08-27-pr2327-t1-12-truth-recovery.md 记录本句；不得修改任何 completion evidence ref/digest、engineering/operational axis、accepted Spec、human attestation、其他 BET、retro、实现代码、测试、gitlink、运行态或用户配置；从最新 main 建唯一 truth-recovery PR，ledger lint、必要 CI 与 post-merge Governance Check 全绿后清理 clone。

## Recovery boundary

- Root base: `9e9f042fb6345361cf2f09c906a6174c486c0eeb`
- Allowed ledger fields: `status`, `done_at`, `completion_evidence.axes.value.status`, `completion_evidence.overall_state`
- Preserved byte-for-byte: all completion evidence refs/digests, engineering axis, operational axis, accepted Spec, human attestation, every other BET and all #2371 frontmatter/convergence changes, retro, implementation, tests, gitlinks, runtime, and user configuration
- No completion or value claim is created by this repair.
