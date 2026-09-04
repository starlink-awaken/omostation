---
schema_version: governance-waiver-evidence/v1
owner: human-principal
lifecycle: history
created: 2026-08-30
last_updated: 2026-08-30
expires_when: combined truth-recovery PR merges or closes
value_indicator_policy: false
title: T1-12 Post-2691 Truth Recovery and Helper Scope Waiver
type: doc
---

# T1-12 Post-#2691 Truth Recovery and Helper Scope Waiver

## Latest Human approval message

```text
批准 T6-15 post-#2676 truth recovery proposal 第4节原文；同时批准 T1-12 bounded stdio MCP load helper scope amendment proposal 第7节原文。
```

Only the T1-12 half of the approval is exercised here. The T6-15 authorization
is not used, analyzed, or implemented by this recovery.

## Human authorization — proposal section 7, verbatim

```text
本次 BET-Y1Q3-T1-12 post-#2691 truth recovery 与 `WP-T1-12-P0-EXACT-MCP-LOAD` helper scope amendment 自举跳过 workflow start，允许使用 `AGCP_REQUIREMENT_ITERATION_GATE=0`；仅限 `docs/plans/3y-bet-ledger.yaml` 将 BET-Y1Q3-T1-12 的完整条目恢复为 #2691 merge parent `30daa7869c31cae1cb584e444cf05442e3aa7e14` 的真值，并仅在该条目的顶层 `write_surfaces` 追加 `lib/capability_mcp_server_load.py`，以及 `.omo/_truth/governance-evidence/waiver-2026-08-30-t1-12-post2691-truth-recovery-helper-scope.md` 记录本句与 fixed-ref 证据；不得修改其他 BET、accepted Spec、capability requirements、goal、done_when、既有 evidence、verify、dependency、circuit breaker、subtraction、实现代码、测试、registry、gitlink、branch protection、运行态或用户配置，不得使用 `bos-service:bos://system/omo/debt` canary、#2692 的 `executed=false` static ready receipt 或 #2574 前的 attestation 证明当前 T1 operational/value；从最新 main 建唯一 combined recovery PR，结果必须为 T1 candidate、无 done_at、engineering IN_PROGRESS、operational/value NOT_PROVEN、overall evaluating、workflow/underlying_workflow 与全部既有字段恢复且顶层 write surfaces 仅由82增至83，ledger lint、必要 CI 与 post-merge Governance Check 全绿后退役 amendment clone，再从新 main 建 fresh T1 implementation workflow，先以独立 child-first slice forward-fix OMO pre-spawn exact admission 并在 child CI 后更新 root pointer，再完成 root-only helper 八路径实现；helper 必须保持 capability-sync 1500 行硬门、无 `tools/call`、无 caller command/fallback、无第二 registry/dispatcher，真实 native canary 通过前不得 promotion，T6/T4 写面保持隔离。
```

## Fixed evidence and exact scope

- Execution baseline and `origin/main`: `371a4d44d599eaf55e0a773c303bbd7a1446336c`.
- Immutable #2691 merge parent: `30daa7869c31cae1cb584e444cf05442e3aa7e14`.
- This recovery changes exactly `docs/plans/3y-bet-ledger.yaml` and this
  waiver file.
- The ledger action is limited to restoring the complete
  `BET-Y1Q3-T1-12` object from the immutable parent plus the single unique
  top-level `write_surfaces` entry `lib/capability_mcp_server_load.py`.

## Resulting bounded truth

The recovered T1-12 state is `candidate`, has no `done_at`, retains
`workflow: bet-execution` and
`underlying_workflow: cognitive-governance-delivery`, and records engineering
`IN_PROGRESS`, operational/value `NOT_PROVEN`, and overall `evaluating`.
All non-write-surface T1 values remain those of the immutable parent; its 82
unique write surfaces become exactly 83 with the helper addition.

## Explicitly prohibited

- Any other BET, accepted Spec, capability requirement, goal, `done_when`,
  existing evidence, verification command, dependency, circuit breaker, or
  subtraction change.
- Implementation code, tests, registry, gitlink, branch protection, runtime,
  or user-configuration changes; no T6 or T4 write surface is authorized.
- Any implementation, runtime canary, MCP tool call, BOS change, completion,
  operational promotion, value promotion, or reuse of the closed workflow.
- Treating closed PR #2692 or its `executed=false` static receipt as completion
  evidence. It provides no MCP initialize, tools/list, teardown, frozen
  material verification, or cleanup proof.
- Treating `bos-service:bos://system/omo/debt` or an attestation predating
  #2574 as proof of current T1 operational or value evidence.

## Residual controls

This bootstrap skips workflow start only for the exact two-path recovery and
uses `AGCP_REQUIREMENT_ITERATION_GATE=0`. Normal isolated-clone provenance,
deterministic ledger parsing, diff hygiene, review, PR, CI, and post-merge
Governance Check remain required. No implementation/runtime/value promotion is
authorized by this waiver.
