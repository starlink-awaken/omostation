---
schema_version: governance-waiver-evidence/v1
owner: human-principal
lifecycle: contract
last_updated: 2026-08-29
created: 2026-08-29
expires_when: amendment PR merges or closes
value_indicator_policy: false
title: T6-15 Guarded-Update Contract Amendment Waiver
type: doc
---

# T6-15 Guarded-Update Contract Amendment Waiver

## Latest Human approval message

```text
批准[路线评审 v2 第9节的 T6-15 Task 4B 精确授权原文](/Users/xiamingxing/Documents/学习进化/基建架构/2026-08-30-蓝图愿景路线与多Agent多仓收敛评审-v2.md)；同时批准[T4-04 amendment proposal 第11节建议批准原文](/Users/xiamingxing/Documents/学习进化/基建架构/2026-08-30-t4-04-personal-episode-authority-amendment-proposal.md)。
```

## Human authorization

```text
本次 BET-Y1Q3-T6-15 guarded double-read accepted-Spec amendment 允许使用 AGCP_REQUIREMENT_ITERATION_GATE=0；仅限 `docs/superpowers/specs/2026-08-28-post2408-main-recovery-and-required-gac-gate-design.md` 将 `spec_version: 1.0.0` 更新为 `1.0.1` 并仅把 H1c 的 `CAS/compare-and-swap` 语义替换为 guarded double-read read-modify-write（GET A→validate/hash→GET B→digest equality→一次 `required_status_checks` subresource PATCH→GET C verify，明确保留 GET-B/PATCH residual race、第二Human gate、receipt和context-only rollback），`docs/plans/3y-bet-ledger.yaml` 仅同步 BET-Y1Q3-T6-15 的 goal、H1c done_when、circuit_breaker及唯一 accepted_specifications version/digest，以及 `.omo/_truth/governance-evidence/waiver-2026-08-28-t6-15-guarded-update-amendment.md` 原文记录本句；不得修改 BET status、completion/value evidence、其他BET、实现代码、测试、CI、branch protection、gitlink、运行态或用户配置；从执行时最新main建立唯一amendment PR，正式workflow绑定旧Spec 1.0.0并精确claim三路径，commit后独立verify并以blocked closeout释放全部locks，必要检查与独立review通过后合并并退役clone；当前三项required contexts保持ADOPT，原始H1c mutation provenance继续UNPROVABLE，不得追认、补造或重复执行历史receipt/live PATCH。
```

## Exact allowed changes

- Update the accepted Spec version and guarded double-read H1c wording.
- Update only BET-Y1Q3-T6-15 goal, H1c `done_when`, `circuit_breaker`, and its accepted-Spec version/digest binding.
- Record this authorization in this waiver.

## Explicitly prohibited

- changing BET status, completion evidence, value evidence, other BETs or any implementation wording outside the named T6-15 fields;
- implementation code, tests, CI, branch protection, gitlinks, runtime state or user configuration;
- re-acknowledging, fabricating or repeating historical H1c receipts or live PATCH effects;
- closing the existing workflow as successful; it must remain available for blocked closeout after the amendment commit.

## Residual governance requirement

This waiver permits `AGCP_REQUIREMENT_ITERATION_GATE=0` only for the exact three-path amendment commit and its independent verification. The amended Spec digest must be recalculated from final bytes; the next H1c workflow must bind Spec `1.0.1` from merged main, while implementation, live branch-protection mutation and runtime observation remain separately governed and value remains `NOT_PROVEN`.
