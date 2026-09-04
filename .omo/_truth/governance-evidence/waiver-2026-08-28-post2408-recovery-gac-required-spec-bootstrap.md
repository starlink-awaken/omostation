---
schema_version: governance-waiver-evidence/v1
owner: human-principal
lifecycle: contract
last_updated: 2026-08-28
created: 2026-08-28
expires_when: bootstrap PR merges or closes
value_indicator_policy: false
title: Post-2408 Recovery and Required GaC Gate Spec Bootstrap Waiv
type: doc
lifecycle: history
last_updated: 2026-08-28
---

# Post-2408 Recovery and Required GaC Gate Spec Bootstrap Waiver

## User authorization

```text
waiver: user-explicit
when: 2026-08-28T06:40:23Z
who: xiamingxing
quote: "本次 Post-2408 Main Recovery 与 Required GaC Gate 设计文档自举跳过 workflow start，允许使用 AGCP_REQUIREMENT_ITERATION_GATE=0；仅限 docs/superpowers/specs/2026-08-28-post2408-main-recovery-and-required-gac-gate-design.md 以 status: draft、bet_id: unbound 写入，以及 .omo/_truth/governance-evidence/waiver-2026-08-28-post2408-recovery-gac-required-spec-bootstrap.md 记录本句；不得修改 ledger、BET、completion/value evidence、实现代码、测试、CI、branch protection、gitlink 或运行态；书面 Spec 经我复核前不得转 accepted、建立 binding 或进入 writing-plans。"
scope: docs/superpowers/specs/2026-08-28-post2408-main-recovery-and-required-gac-gate-design.md; .omo/_truth/governance-evidence/waiver-2026-08-28-post2408-recovery-gac-required-spec-bootstrap.md
reason: agent-workflow start fail-closed with missing_bet_id, while the human requires written draft review before accepted binding
risk: the draft is not an admission contract and cannot authorize implementation
residual: a separately authorized binding PR and normal workflow are required after written review
gate_bypass: 1
no-run-id: true
```

This waiver authorizes only a one-time draft-Spec bootstrap. It does not authorize an accepted Spec, BET binding,
writing-plans or implementation.

## Exact allowed paths

- `docs/superpowers/specs/2026-08-28-post2408-main-recovery-and-required-gac-gate-design.md`
- `.omo/_truth/governance-evidence/waiver-2026-08-28-post2408-recovery-gac-required-spec-bootstrap.md`

## Explicitly prohibited

- `docs/plans/3y-bet-ledger.yaml`, any BET status, accepted binding, completion evidence or value evidence;
- implementation code, tests, generated projections, script registry, governance baseline or ADR contents;
- `.github/workflows/**`, CI surfaces, hooks or live branch protection;
- gitlinks, submodule contents, services, processes, databases, schedules, timers or user configuration;
- starting Product P0 Wave A or claiming R1, H1, R2, Product P0, governance health or principal-bound value complete.

## Residual governance requirement

The bootstrap commits may set `AGCP_REQUIREMENT_ITERATION_GATE=0` only for staging, commit and exact verification of
the two allowed paths. The Spec must remain `status: draft` and `bet_id: unbound`. After the written Spec is reviewed,
a separately authorized binding PR must synchronously set accepted frontmatter, select one candidate BET, calculate
the exact digest and write the unique accepted-Spec binding. Only then may writing-plans begin. Every implementation,
test, CI change, live protection mutation, closeout and runtime observation must use normal Agent Workflow
start/claim/verify/closeout and independent delivery clones.
