---
schema: md/v1
status: active
lifecycle: history
owner: governance-team
last-reviewed: 2026-09-25
type: report
title: A8 OMO external adapter transaction authoritative review
last_updated: '2026-09-15'
bet: BET-Y1Q4-T10-151
---


# A8 external adapter transaction — authoritative current state

## Purpose

`BET-Y1Q4-T10-151` requires a five-path search before claiming that the A8
transaction chain is absent. This review checks ADR, archive, mutation
surfaces, ingress delivery artifacts, and current OMO code at root main
`ad8f25feae315c9a0632c3b41cfef4d5de85be08` with OMO gitlink
`30af1ac3e80c14caa006691373646b50f9324f44`.

## Verdict

**Partial existence, no unified generic lifecycle.**

The repository already contains strong transaction primitives:

- policy decision / started receipt / terminal receipt;
- ledger-backed idempotency and `receipt_unconfirmed`;
- claim mutation and legacy publication fences;
- persistent queue enqueue/dequeue;
- controlled task start/stop/restart/complete;
- credential-free external receipt ingestion.

None of these is a generic OMO-owned external adapter transaction with the
required `reserve → bind → readback → start → ACK/fence → release/retire`
state machine. The A8 evidence gate therefore correctly records `absent`.

## Five-path evidence

### 1. ADR and architecture

- ADR-0370 (`docs/_knowledge/decisions/0370-agt-ecos-integration.md`) accepts
  the BOS URI external adapter registration pattern: M1 component/routes,
  Agora services, L0 constraints, X1 policy, and GaC backend integration.
- `docs/external-adapter-integration-pattern.md` is an integration checklist.
  It does not define an OMO-owned per-transaction state machine or release
  semantics.
- No ADR defines all seven required transaction stages.

### 2. Archive

Targeted archive searches found historical adapter registration, governance,
idempotency, and worker dispatch material, but no completed generic external
adapter transaction lifecycle. No archived implementation provides reserve,
bind, readback, and retire as one OMO-owned transaction.

### 3. Mutation surfaces

`.omo/_truth/registry/mutation-surfaces.yaml` registers brokered governance
ingress, task, bridge, C2G adapter, and state projection writes. It has no
`external adapter transaction` mutation surface and no release/retire target
for such transactions.

### 4. Ingress delivery artifacts

Searches under `.omo/_delivery` and `runtime/omo/_delivery` found no external
adapter transaction journal or seven-stage receipt chain. Existing artifacts
are task/ingress/evidence records rather than generic transaction state.

### 5. Current OMO code

- `projects/omo/src/omo/sovereignty/enforcement.py`
  - `PolicyEnforcementService.decide` durably admits an action.
  - `enqueue_allowed_action` persists an admitted action for later execution.
  - `persist_started` writes a start receipt before provider dispatch.
  - `execute` invokes the provider at most once and writes succeeded, failed,
    or `receipt_unconfirmed`.
  - Same `action_id` plus request hash is idempotent; a different request hash
    is rejected.
  - This is the closest existing lifecycle, but it has no explicit adapter
    reserve record, role/capsule binding readback, release, or retire stage.
- `projects/omo/src/omo/workflow/claims_authority.py`
  - Implements claim mutation reservation/settlement and Git publication
    fencing, including unknown outcomes and operator resolution.
  - The scope is claims/publication authority, not arbitrary external adapter
    transactions.
- `projects/omo/src/omo/sovereignty/persistent_queue.py`
  - Provides durable enqueue/dequeue only, not transaction ownership or
    terminal settlement.
- `projects/omo/src/omo/omo_ingress_task_execution.py`
  - Provides controlled process start, status, stop, restart, and task
    completion. It does not bind external role/capsule identity or read back
    an adapter transaction.
- `projects/omo/src/omo/omo_external_receipt.py`
  - Accepts credential-free external receipts, but only terminal
    `succeeded` or `degraded` evidence. It does not own reservation, binding,
    dispatch fencing, release, or retirement.

## Consequence for T10-151

The minimal implementation must compose these primitives rather than create a
second dispatcher or parallel authority. The missing generic service should
use the existing event ledger semantics and bind `RoleRegistry`, `Capsule`,
and external receipts to one transaction identity.

## Search commands

```bash
git grep -n -i -E 'reserve|readback|fence|release/retire|transaction lifecycle|external transaction' origin/main
git grep -n -i -E 'external.*adapter|adapter.*external|begin_claim|settle_claim|legacy.*fence|unknown outcome|idempoten' origin/main
git grep -n -i -E 'reserve.{0,80}bind|bind.{0,80}readback|readback.{0,80}start|start.{0,80}ACK.{0,80}fence|fence.{0,80}release.{0,80}retire' origin/main
rg -n -i -E 'reserve.{0,80}bind|bind.{0,80}readback|readback.{0,80}start|start.{0,80}ACK.{0,80}fence|fence.{0,80}release.{0,80}retire|external transaction' .omo/_delivery runtime/omo/_delivery
```

The exact-chain grep found only the A8 declaration in
`bin/gac/gate-evidence-receipt.py` and the T10-151 Ledger entry; neither is an
implementation.
