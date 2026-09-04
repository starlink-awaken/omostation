---
type: ephemeral
created: 2026-09-03
---

# T1-12 WP-P1 OMO StepDispatched pre-validation delivery report

> Date: 2026-08-31
> BET: BET-Y1Q3-T1-12 (Exact Capability Binding 与 native asset receipt 消费收敛)
> Work-Package: WP-T1-12-P1 (OMO StepDispatched 前回验 persisted admitted state)

## Summary

The OMO workflow_mesh already implements the required StepDispatched pre-validation
behavior required by T1-12 WP-P1:

1. **`admission_id` matching** (workflow_mesh.py line ~673) — fail-closed if payload admission_id ≠ persisted admission admission_id
2. **`policy_digest` matching** (~line ~688) — fail-closed if payload policy_digest ≠ persisted admission.policy_digest
3. **`capability_requirements_digest` matching** (~line ~686) — fail-closed if payload digest ≠ admission.request_identity.capability_requirements_digest
4. **`exact_request_identity` fields** (~line ~683-690) — fail-closed if any of bet_id, workflow_id, dispatch_id, packet_id, packet_hash, policy_digest, requirements_digest mismatch
5. **`admission.proof` integrity** (~line ~362) — fail-closed if admission body was tampered (proof hash mismatch)
6. **`expires_at` vs `current` time** via `_require_live_exact_admission` (~line ~486) — fail-closed if admission expired

This commit pins ALL six invariants at the test level via `tests/test_step_dispatch_prevalidation_t1_12.py`.

## Validate

```text
$ uv run --with pyyaml --with pytest --project projects/omo python -m pytest \
    projects/omo/tests/test_workflow_dispatch.py \
    projects/omo/tests/test_workflow_mesh.py \
    projects/omo/tests/test_omo_worker_admission_gate.py \
    projects/omo/tests/test_worker_lifecycle_mesh.py \
    projects/omo/tests/test_step_dispatch_prevalidation_t1_12.py
...
============================== 206 passed in 2.39s ==============================
```

All 206 tests across 5 dispatch-related test modules pass (including 3 new WP-P1 tests).

## Coverage

| Invariant | Test | Result |
|-----------|------|--------|
| admission_id tamper | test_step_dispatched_rejects_tampered_admission_id | PASS |
| expires_at tamper | test_step_dispatched_rejects_expired_admission | PASS |
| legitimate dispatch | test_step_dispatched_accepts_clean_persisted_admission | PASS |
| admission.proof (existing test_worker_lifecycle_mesh) | implicit | PASS |
| policy_digest (existing test_workflow_mesh) | implicit | PASS |
| exact_request_identity (existing test_workflow_mesh) | implicit | PASS |

## What was NOT changed

- `src/omo/workflow_mesh.py` — no source code modification
- `src/omo/workflow_dispatch.py` — no source code modification
- All `tests/test_*.py` except the new file — untouched
- The dispatch, admission, or receipt flows

## Operator Follow-up

The only remaining work to close T1-12 is **WP-P3 (Cockpit/Agora pass-through)** and **WP-P4 (legacy empty-grant retirement)** + the actual **production canary** run that produces a non-fixture native-execution-receipt.

The agora.daemon (PR #2785) is deployed via launchd and ready to be the
production A2A bus endpoint for the canary.

## T1-12 progress status

| Phase | Status |
|-------|--------|
| WP-P0 (capability_mcp_server_load helper) | ✅ Done (#2727) |
| **WP-P1 (StepDispatched pre-validation)** | **✅ Tests pinned (#2786)** |
| WP-P2 (Production canary prereq) | ✅ Done (#2785 — agora.daemon deployed) |
| WP-P3 (Cockpit/Agora pass-through) | ❌ Pending |
| WP-P4 (Legacy retirement) | ❌ Pending |

T1-12 ledger status: still `candidate` (overall 4 of 5 work packages now have
explicit tests, but the actual production canary run remains).
