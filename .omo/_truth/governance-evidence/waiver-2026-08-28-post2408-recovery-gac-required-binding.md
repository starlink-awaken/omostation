---
schema_version: governance-waiver-evidence/v1
owner: human-principal
lifecycle: contract
last_updated: 2026-08-28
created: 2026-08-28
expires_when: accepted binding PR merges or closes
value_indicator_policy: false
title: Post-2408 Recovery Accepted Binding Bootstrap Waiver
type: doc
lifecycle: history
last_updated: 2026-08-28
---

# Post-2408 Recovery Accepted Binding Bootstrap Waiver

## User authorization

```text
waiver: user-explicit
when: 2026-08-28T07:59:14Z
who: xiamingxing
quote: "本次 Post-2408 Main Recovery 与 Required GaC Gate accepted binding 自举跳过 workflow start，允许使用 AGCP_REQUIREMENT_ITERATION_GATE=0；仅限 docs/superpowers/specs/2026-08-28-post2408-main-recovery-and-required-gac-gate-design.md 将 status: draft 改为 accepted、bet_id: unbound 改为 BET-Y1Q3-T6-15，docs/plans/3y-bet-ledger.yaml 仅新增 BET-Y1Q3-T6-15 candidate、唯一 accepted_specifications binding 及初始 completion matrix（engineering=NOT_STARTED、operational/value=NOT_PROVEN、overall=evaluating、value_indicator_policy=false），以及 .omo/_truth/governance-evidence/waiver-2026-08-28-post2408-recovery-gac-required-binding.md 记录本句；不得修改其他 BET、既有 completion/value evidence、实现代码、测试、CI、branch protection、gitlink 或运行态；binding PR 合并且检查通过后允许进入 writing-plans，但不得直接实施。"
scope: docs/superpowers/specs/2026-08-28-post2408-main-recovery-and-required-gac-gate-design.md::frontmatter; docs/plans/3y-bet-ledger.yaml::BET-Y1Q3-T6-15; .omo/_truth/governance-evidence/waiver-2026-08-28-post2408-recovery-gac-required-binding.md
reason: agent-workflow start requires an existing accepted Spec and BET, while this PR creates their first exact binding
risk: only declarative candidate state is added; no implementation or runtime authority is granted
residual: writing-plans may start after merge, but implementation still requires normal workflow start and exact claims
gate_bypass: 1
no-run-id: true
```

## Exact allowed changes

- Set the accepted Spec frontmatter to `status: accepted` and `bet_id: BET-Y1Q3-T6-15`.
- Add exactly one candidate `BET-Y1Q3-T6-15` with one accepted-Spec binding and an initial empty completion matrix.
- Record this waiver in this file.

## Explicitly prohibited

- changing any pre-existing BET, completion evidence, value evidence or status;
- implementation code, tests, CI, branch protection, gitlinks, services, databases or runtime state;
- starting writing-plans before this binding merges and passes checks;
- starting implementation under this bootstrap waiver;
- claiming R1, H1, R2, Product P0 or principal-bound value complete.

## Residual governance requirement

The bootstrap commits may set `AGCP_REQUIREMENT_ITERATION_GATE=0` only while staging, committing and verifying the
three authorized paths. After merge, writing-plans must consume the exact accepted Spec bytes and the generated
`WP-BET-Y1Q3-T6-15`; every implementation, canary, live protection mutation, host migration and closeout must use
normal Agent Workflow start/claim/verify/closeout. Value remains `NOT_PROVEN`.
