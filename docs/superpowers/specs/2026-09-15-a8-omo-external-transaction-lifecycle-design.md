---
schema_version: specification/v1
spec_version: 1.0.0
title: A8 OMO external adapter transaction lifecycle
bet_id: unbound
status: draft
lifecycle: spec
owner: governance-team
created: '2026-09-15'
last-reviewed: '2026-09-15'
implementation_authorized: false
value_indicator_policy: false
risk_level: L2
human_gate: true
type: ssot
---

# A8 OMO external adapter transaction lifecycle

## Problem

A8 currently records `absent`: OMO has transaction primitives but no unified
generic lifecycle for an external adapter effect. Existing policy enforcement
can start and settle a provider call, claims authority can fence Git
publication, and queues/receipts are durable, but these systems do not jointly
prove adapter identity binding, readback, dispatch, observation, verification,
release, and retirement for one transaction.

The authoritative review is
`docs/reports/2026-09-15-a8-external-transaction-authoritative-review.md`.

## Decision

Add one OMO-owned `ExternalTransactionService` that composes existing
primitives and owns the following append-only event lifecycle:

1. **Reserve** — persist transaction ID, adapter ID, role ID, capability,
   operation, request digest, principal identity, and lease deadline before
   any external effect.
2. **Bind** — bind the sealed Capsule/WorkPacket and verifier identity to the
   reserved transaction.
3. **Readback** — reload the reservation, role, capsule, and verifier records
   by durable IDs and verify every digest before dispatch.
4. **Start** — persist `Dispatch.Started`; only then hand a transport-only
   request to the adapter.
5. **Observe / ACK or fence** — consume a credential-free adapter receipt.
   Identity mismatch, missing receipt, or unknown outcome transitions to
   `fenced`; it never auto-retries.
6. **Verify** — run the bound role verifier and validate the receipt's
   operation, transaction ID, result digest, provenance, and policy digest.
7. **Release / retire** — append release for the reservation and retire the
   completed transaction; a fenced transaction remains queryable for operator
   resolution and never re-enters automatic dispatch.

The service uses the existing OMO event ledger for durability and idempotency.
It delegates authorization and identity to `RoleRegistry`, packet integrity to
Capsule, transport to the external adapter, and evidence projection to the
existing external receipt broker. It does not create a second dispatcher,
queue authority, or control plane.

## State model

```text
reserved -> bound -> readback_verified -> started
started -> observed -> verified -> released -> retired
started -> fenced
observed -> fenced
verified -> fenced
fenced -> operator_resolved
```

Legal terminal states are `retired` and `operator_resolved`. `fenced` is not
terminal and grants no retry authority.

## Hard invariants

- OMO owns the transaction state machine; the adapter is transport only.
- A role not admitted for the exact capability cannot advance beyond reserve.
- Capsule digest, role ID, capability, operation, transaction ID, and request
   digest must match on readback.
- Start is appended before an external effect.
- Unknown outcome always fences and requires an operator resolution.
- Duplicate transaction ID plus identical request is idempotent and performs
   no second provider effect.
- Duplicate transaction ID with a different request digest is rejected.
- Adapter payloads and receipts never contain credentials or raw private
  content.
- A8 admission does not grant A6 Orca, A7 Multica, Ruflo, or A9 Cockpit
  admission.

## Minimal implementation scope

- Add `projects/omo/src/omo/workflow/external_transaction.py`.
- Add focused tests in `projects/omo/tests/test_external_transaction.py`.
- Reuse:
  - `RoleRegistry` / role verifier binding;
  - `seal_capsule` / `verify_capsule`;
  - the event ledger's producer/idempotency semantics;
  - `record_external_receipt` for evidence projection.
- Keep transport adapters behind a narrow callable protocol for tests and
  later A6/A7/Ruflo integration.

## RED matrix

| Case | Expected |
|---|---|
| Reserve twice with same transaction/request | Same reservation; one event effect |
| Same transaction ID, different request digest | Reject before bind |
| Role not admitted for capability | Remain reserved; no bind |
| Capsule digest changes before readback | Reject and fence |
| Start ledger append fails | Zero adapter calls |
| Adapter returns mismatched transaction/operation | Fence, no verify |
| Adapter returns unknown/error | Fence, no auto retry |
| Receipt verification fails | Fence and preserve started receipt |
| Terminal receipt append fails | `receipt_unconfirmed`; transaction remains queryable |
| Happy path | Exactly one provider call and terminal retired receipt |
| Duplicate replay after retirement | No second provider call |

## Acceptance

- Focused external transaction tests cover every RED row.
- Existing role, capsule, claims authority, and external receipt tests remain
  green.
- `make gac-local-gate` passes.
- The A8 evidence gate can move from declared `absent` to mechanically
  evaluated only after all four exit criteria are implemented:
  - seven-stage contract;
  - identity mismatch never advances OMO;
  - unknown outcome never auto-retries;
  - duplicate effect is zero.

## Rollout

1. Merge this draft review/spec.
2. Human review and acceptance.
3. Implement the service and tests in one OMO child PR.
4. Add a read-only fake adapter canary.
5. Only after A8 passes, evaluate A6 Orca R0, A7 Multica AS0, and Ruflo R0
   against the transaction API.

## Rollback

Revert the new service and tests. Existing policy enforcement, claims
authority, queue, and external receipt behavior remain unchanged.

## Non-goals

- No second authoritative dispatcher or queue.
- No credential or raw provider output storage.
- No automatic retry after an unknown outcome.
- No claim that business value is proven.
- No external tool admission merely because the API exists.
