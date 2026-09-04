---
schema_version: governance-waiver-evidence/v1
owner: human-principal
lifecycle: history
created: 2026-08-30
last_updated: 2026-08-30
expires_when: truth-recovery PR merges or closes
value_indicator_policy: false
title: T6-15 Post-2676 Truth Recovery Waiver
type: doc
---

# T6-15 Post-#2676 Truth Recovery Waiver

## Latest Human approval message

```text
批准 T6-15 post-#2676 truth recovery proposal 第4节原文；同时批准 T1-12 bounded stdio MCP load helper scope amendment proposal 第7节原文。
```

Only the T6-15 half of that approval is exercised by this recovery. The T1-12
authorization is not used, analyzed, or implemented here.

## Human authorization — proposal section 4, verbatim

```text
本次 BET-Y1Q3-T6-15 post-#2676 truth recovery 自举跳过 workflow start，允许使用 `AGCP_REQUIREMENT_ITERATION_GATE=0`；仅限 `docs/plans/3y-bet-ledger.yaml` 将 BET-Y1Q3-T6-15 的完整条目恢复为 #2676 merge parent `0244bb49e48a43917b238993fa23125a3c43fe88` 的真值，`docs/reports/2026-08-28-post2408-main-recovery-closeout.md` 仅删除 #2666 新增的 `R2b host retention — EXECUTED 2026-08-30` 段，`.omo/_knowledge/retros/BET-Y1Q3-T6-15.md` 仅删除 #2666 新增的 `R2b 收账补记 (2026-08-30)` 段，以及 `.omo/_truth/governance-evidence/waiver-2026-08-30-t6-15-post2676-truth-recovery.md` 记录本句；不得修改其他 BET、accepted Spec、实现代码、测试、registry、gitlink、branch protection、运行态或用户配置，不得把 broad backup、Git blob、旧 clone 或重建文件追认为 historical retention；从最新 main 建唯一 truth-recovery PR，ledger lint、必要 CI 与 post-merge Governance Check 全绿后退役 clone，再按已批准的 R2b amendment 第14节从新 main 建 fresh binding workflow，T6 保持 candidate/evaluating、historical retention UNPROVABLE、operational/value NOT_PROVEN，直至 amended current-recoverability 直接证据通过。
```

## Exercised scope

- Restore the complete `BET-Y1Q3-T6-15` ledger entry to immutable parent
  `0244bb49e48a43917b238993fa23125a3c43fe88`.
- Remove only the two #2666 R2b closure addenda named above.
- Record this authorization; no T1-12 authorization is exercised.

## Explicitly prohibited

- Any other BET, accepted Spec, implementation code, test, registry, gitlink,
  branch-protection, runtime, or user-configuration change.
- Treating a broad backup, Git blob, old clone, or reconstructed file as proof
  of historical retention.
- T6 completion or operational/value promotion without fresh direct evidence
  under the amended current-recoverability contract.
