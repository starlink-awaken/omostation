---
schema_version: governance-waiver-evidence/v1
status: active
owner: human-principal
lifecycle: history
created: 2026-09-11
last-reviewed: 2026-09-11
value_indicator_policy: false
title: Claims Authority Bridge WP1 1.8.0 verifier interface binding
type: doc
---

# Claims Authority Bridge WP1 1.8.0 Verifier Interface Binding

## Human authority and exact scope

Current Principal authorization, verbatim:

> 给你全权授权，推进目标规划落地吧

Interpreted for this transaction as reversible repository-only authorization to
replace the accepted Spec/Ledger binding of `BET-Y1Q4-T10-145` with version
`1.8.0` (Wave E four `projects/omo` verifier paths only). Constitutional
boundaries remain: OMO sole control plane; no Orca/Multica/Ruflo writers; no
shared Workspace writes; `value_indicator_policy=false`; operational/value stay
`NOT_PROVEN`.

`AGCP_REQUIREMENT_ITERATION_GATE=0` was supplied only to the fresh unbound
`governance-state-mutation` start
`20260911T135228Z-governance-state-mutation-9517ac75`.

Lane declaration: `AGENT_WORKFLOW_ALLOWED_LANES=docs,docs_data,governance_state`.

Tracked paths only:

1. `docs/superpowers/specs/2026-09-10-claims-authority-bridge-wp1-shadow-design.md`
2. `docs/plans/3y-bet-ledger.yaml`
3. this waiver

## Predecessor proof

- Wave D non-terminal report #3584 merge `8c728c892`
- Spec 1.7.0 binding #3583 merge `0d0d456c5`
- graduation JSON on main: `done=false`, `decision=NOT_READY`, window `NOT_STARTED`

## Why 1.8.0

Task 16 host activation is blocked until principal-decision and stopped-process
verifiers are named and closure-bound. Version 1.8.0 authorizes only that Wave E
implementation surface set. It does **not** authorize host activation, 24h clock
start, gitlink bump, or graduation `done`.

## 1.8.0 successor authority

- Spec version: `1.8.0`
- Spec SHA-256: `659e293c3ed4cc98a3e8dc5da1e02c27ee3db4c39eb5e543078b3a8e115f74e3`
- WorkPacket: `sha256:309f9af75d11d814de01f7beffbcde76cfc6c09e81b841f69586948e97529fec`
- Write surfaces:

```text
projects/omo/src/omo/workflow/claims_authority.py
projects/omo/src/omo/workflow/claims_verifiers.py
projects/omo/tests/test_claims_verifiers.py
projects/omo/tests/test_workflow_claims_authority_bridge.py
```

- Rejects 1.7.0 WorkPacket `sha256:abc012a6ddfedd39d4e93c0c6d44e37908d5c681dc05486dd5502416043f258e`
- BET remains `candidate`

## Clone

- `/Users/xiamingxing/agents/grok-agent-os-recovery/attempts/claims-wp1-v180-binding-20260911-01/ws`
- Binding run: `20260911T135228Z-governance-state-mutation-9517ac75`
