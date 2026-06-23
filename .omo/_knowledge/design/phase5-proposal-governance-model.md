---
plane: knowledge
type: design
status: active
freshness: 2026-05-31
maintainer: auto
---
lifecycle: contract
owner: governance-team
last-reviewed: 2026-06-23
---

# Phase 5 proposal governance model

## 1. Decision

Phase 5 adopts a single proposal contract for all **truth-mutating** work above the direct-execution boundary.

The contract is:

1. **L0-L1**: direct execution remains allowed where explicitly whitelisted.
2. **L2**: proposal is mandatory, approval may be automatic, verification is mandatory.
3. **L3**: proposal and explicit approval are both mandatory before apply.
4. **Secrets and security posture changes are never carried as raw values inside proposals**; only `secret_ref` or equivalent references are allowed.

This freezes the Wave 0 design seam so Wave 1 can implement the governance runtime without re-litigating entity shape or approval boundaries.

## 2. Plane ownership

| Plane | Proposal responsibility |
|------|--------------------------|
| control | governance level caps, current phase/wave, approval policy switches |
| truth | proposal SSOT records and approved desired mutations |
| delivery | apply logs, verification evidence, audit chain, failed execution records |
| knowledge | rationale, review decisions, operator guidance, retrospectives |

**Rule:** proposals are **truth entities**; execution artifacts derived from them are **delivery evidence**.

## 3. Proposal entity

The canonical proposal record lives under:

`_truth/task-center/proposals/<proposal-id>.yaml`

Required fields:

```yaml
id: p-20260531-001
title: Freeze landing model for task-center truth and delivery ownership
status: proposed
operation_level: L2
requested_by: copilot-cli
target:
  plane: truth
  kind: task_center_registry
  ref: _truth/task-center/registry.yaml
change_summary:
  - remove mirrored runtime snapshot outside owner planes
impact:
  blast_radius: medium
  touches:
    - _truth/task-center/
    - _delivery/task-center/
verification_plan:
  - schema validation
  - regression tests
rollback_plan:
  - restore prior YAML
  - rerun sync
secret_refs: []
trace_id: trace-...
```

Non-goals:

1. no embedded secret values
2. no direct storage of approval chat transcripts inside truth records
3. no mixed proposal plus execution log record in one file

## 4. Lifecycle

Canonical lifecycle:

```text
draft -> proposed -> approved -> applied -> verified -> archived
                    \-> rejected
                    \-> expired
                    \-> failed
```

State semantics:

| State | Meaning |
|------|---------|
| `draft` | incomplete local work, not yet submitted |
| `proposed` | frozen request waiting for approval policy |
| `approved` | permitted to execute, not yet applied |
| `applied` | desired change executed, verification pending |
| `verified` | execution evidence confirms outcome |
| `archived` | closed and retained for audit/history |
| `rejected` | denied before apply |
| `expired` | not applied within TTL / no longer valid |
| `failed` | apply attempted but outcome invalid or incomplete |

## 5. Approval boundary

| Operation level | Examples | Proposal required | Approval required | Apply actor | Verification required |
|----------------|----------|-------------------|-------------------|-------------|-----------------------|
| `L0` | harmless read/status | no | no | direct | no |
| `L1` | bounded task-local writes | optional by feature | no | worker/coordinator | task-level |
| `L2` | registry edits, blueprint/task declarations, low-risk truth mutation | yes | auto/self approval allowed | coordinator or governed executor | yes |
| `L3` | phase changes, secrets policy changes, security posture changes | yes | yes, explicit human/coordinator approval | coordinator only | yes, before promotion |

Wave 0 freeze:

1. **Phase promotion is always L3.**
2. **Secrets ownership changes are always L3.**
3. **Worker agents may prepare L2 material but do not self-promote proposals to applied.**
4. **Coordinator remains the only actor that syncs `goals/current.yaml` and `state/system.yaml`.**

## 6. Apply and verify contract

An `approved` proposal may be applied only if:

1. referenced files still match the expected preconditions
2. operation level is permitted by current control policy
3. required `secret_ref` references resolve without exposing the secret value in logs
4. a verification plan is attached

Apply output belongs in delivery, for example:

- `_delivery/task-center/proposals/<proposal-id>/apply.json`
- `_delivery/task-center/proposals/<proposal-id>/verify.json`
- `_delivery/task-center/proposals/<proposal-id>/diff.patch`

Verification must answer:

1. what changed
2. whether the desired state now matches the proposal
3. whether rollback remains available
4. whether any divergence flags were raised

## 7. MCP surface and runtime seam

Wave 1 implementation should align to four verbs:

1. `task_propose`
2. `task_approve`
3. `task_apply`
4. `task_proposal_list`

Runtime rules:

1. `task_apply` rejects anything not in `approved`
2. `task_approve` checks operation level and current approval policy
3. `task_proposal_list` may read truth plus delivery summaries, but never surfaces secret material
4. proposal `trace_id` must continue into apply and verify records

## 8. Wave 1 implementation implications

This freeze implies the following for the next execution lane:

1. build proposal storage under `_truth/task-center/proposals/`
2. build delivery evidence under `_delivery/task-center/proposals/`
3. wire control-plane policy to level caps and approval switches
4. reject L2/L3 truth mutation paths that bypass proposals

## 9. Outstanding items deferred beyond this freeze

These are intentionally left for implementation, not for further design debate:

1. exact TTL/retention for `expired` and `archived`
2. whether verification writes one file or multiple stage-specific records
3. exact MCP response schemas

Those details may iterate in Wave 1 so long as they stay inside the contract frozen above.
