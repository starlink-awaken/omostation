---
schema_version: governance-waiver-evidence/v1
status: active
owner: human-principal
lifecycle: history
created: 2026-09-11
last-reviewed: 2026-09-11
value_indicator_policy: false
title: Claims Authority Bridge WP1 1.6.0 root pointer binding
type: doc
---

# Claims Authority Bridge WP1 1.6.0 Root Pointer Binding

## Human authority and exact scope

Current Principal authorization, verbatim:

> 给你全权授权，推进目标规划落地吧

Interpreted for this transaction as reversible repository-only authorization to
replace the accepted Spec/Ledger binding of `BET-Y1Q4-T10-145` with version
`1.6.0` (sole write surface `projects/omo` gitlink), then continue Wave C under
the repository submodule-pointer transaction. Constitutional boundaries remain:
OMO sole control plane; no Orca/Multica/Ruflo writers; no shared Workspace
writes; `value_indicator_policy=false`; operational/value stay `NOT_PROVEN`.

`AGCP_REQUIREMENT_ITERATION_GATE=0` was supplied only to the fresh unbound
`governance-state-mutation` start
`20260911T125108Z-governance-state-mutation-e85df4a2`.

The process-local gate declaration is exactly
`AGENT_WORKFLOW_ALLOWED_LANES=docs,docs_data,governance_state`.

Tracked paths only:

1. `docs/superpowers/specs/2026-09-10-claims-authority-bridge-wp1-shadow-design.md`
2. `docs/plans/3y-bet-ledger.yaml`
3. this waiver

## Predecessor proof (B1–B4)

- Wave B4 merge `73978058c` (#3575), source `03b52b1aa`, run
  `20260911T123344Z-bet-execution-1f98e263` ok, locks zero
- Spec 1.5.0 binding #3567 merge `6459af54e`
- Wave B3 #3564 / B2 #3554 / B1 #3535 previously merged
- Wave A child `15ee4ab` remains on authoritative `projects/omo` main ancestry

## 1.6.0 successor authority

- Spec version: `1.6.0`
- Spec SHA-256: `5d1a34964b57e42cbbd5df99edcb789094e408103052eee63d21d02872e83689`
- WorkPacket: `sha256:cfbfccdadefa05b5882316748a892a79b44a1b3ace44dcfe98c6e90d94ba05e8`
- Write surfaces: `projects/omo` only
- Rejects Wave B4 WorkPacket `sha256:4e7b88d23c8a110181b38b15a183c93f01543243b60276b69daaaa89fce0a2d8`
- BET remains `candidate`; operational/value `NOT_PROVEN`

## Clone

- `/Users/xiamingxing/agents/grok-agent-os-recovery/attempts/claims-wp1-v160-binding-20260911-01/ws`
- Binding run: `20260911T125108Z-governance-state-mutation-e85df4a2`

## Stop conditions

Any non-`projects/omo` write surface, source edits in this PR, completion/value
expansion, reuse of 1.5.0 WorkPacket hash, or failed Binding QA stops this
transaction.
