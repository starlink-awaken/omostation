---
schema_version: governance-waiver-evidence/v1
status: active
owner: human-principal
lifecycle: history
created: 2026-09-11
last-reviewed: 2026-09-11
value_indicator_policy: false
title: Claims Authority Bridge WP1 1.7.0 Wave D evidence binding
type: doc
---

# Claims Authority Bridge WP1 1.7.0 Wave D Evidence Binding

## Human authority and exact scope

Current Principal authorization, verbatim:

> 给你全权授权，推进目标规划落地吧

Interpreted for this transaction as reversible repository-only authorization to
replace the accepted Spec/Ledger binding of `BET-Y1Q4-T10-145` with version
`1.7.0` (Wave D two evidence paths only). Constitutional boundaries remain: OMO
sole control plane; no Orca/Multica/Ruflo writers; no shared Workspace writes;
`value_indicator_policy=false`; operational/value stay `NOT_PROVEN`.

`AGCP_REQUIREMENT_ITERATION_GATE=0` was supplied only to the fresh unbound
`governance-state-mutation` start
`20260911T131500Z-governance-state-mutation-20f21b4a`.

Lane declaration: `AGENT_WORKFLOW_ALLOWED_LANES=docs,docs_data,governance_state`.

Tracked paths only:

1. `docs/superpowers/specs/2026-09-10-claims-authority-bridge-wp1-shadow-design.md`
2. `docs/plans/3y-bet-ledger.yaml`
3. this waiver

## Predecessor proof

- Wave C merge `74f72d5c5` (#3581), source `aec9b3087`, run
  `20260911T125855Z-bet-execution-5f594d01` ok; omo pin
  `83c27519bf0b574beb192d37a0245d221806d4c2`
- Spec 1.6.0 binding #3580; Waves B4–A previously closed

## 1.7.0 successor authority

- Spec version: `1.7.0`
- Spec SHA-256: `ad0a40bb9fddcab5b4eb8acb54ad524ccb934280b09a4eb48d74bfeadce58db2`
- WorkPacket: `sha256:abc012a6ddfedd39d4e93c0c6d44e37908d5c681dc05486dd5502416043f258e`
- Write surfaces:

```text
.omo/_knowledge/retros/BET-Y1Q4-T10-145.md
.omo/_truth/governance-evidence/claims-authority-bridge-wp1-shadow-graduation.json
```

- Rejects 1.6.0 WorkPacket `sha256:cfbfccdadefa05b5882316748a892a79b44a1b3ace44dcfe98c6e90d94ba05e8`
- BET remains `candidate`; before full 24h window, only non-terminal shadow report
  (`done=false`) is authorized
- Host activation (Task 16) is NOT authorized by this binding alone

## Clone

- `/Users/xiamingxing/agents/grok-agent-os-recovery/attempts/claims-wp1-v170-binding-20260911-01/ws`
- Binding run: `20260911T131500Z-governance-state-mutation-20f21b4a`
