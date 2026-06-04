# Phase 9 Wave 3 execution plan

Packet: `P9-W3-IDENTITY-ADMISSION-CONTRACT`

## Goal

Define the first cross-root identity, authorization, and admission contract that can govern actions across `.omo`, `projects/*`, `spaces/`, `data/`, and `runtime/` without collapsing those roots back into `.omo`.

## Default design anchor

Wave 3 uses **actor + space membership** as the identity anchor:

1. actor answers **who**
2. space membership answers **where**
3. role/capability answers **what may happen**
4. admission answers **whether this specific routed action may enter**

This keeps identity, policy, and admission separable while still making cross-root decisions machine-checkable.

## Scope

1. define the workspace actor model
2. define how actors become members of a space
3. define role/capability mapping for cross-root actions
4. define admission checks for routed work that crosses governed roots

## Deliverables

1. `.omo/plans/phase9-wave3-execution-plan.md`
2. `.omo/tasks/active/P9-W3-IDENTITY-ADMISSION-CONTRACT.yaml`
3. `spaces/_schema/space-identity-admission.schema.yaml`
4. `spaces/system-space-identity-admission.yaml`
5. `spaces/system-space-capability-taxonomy.yaml`
6. `spaces/system-space-admission-matrix.yaml`
7. `.omo/workers/templates/worker-task-envelope.yaml`
8. `.omo/workers/runs/phase9-wave3-identity-admission-envelope.yaml`
9. `scripts/omo_admission.py`
10. `scripts/omo_worker.py`
11. `.omo/tests/test_phase9_identity_admission_contract.py`
12. `.omo/tests/test_omo_admission.py`

## Exit gate

1. identity is anchored on actor + space membership, not implicit path ownership
2. cross-root authorization language is explicit before rollout/ops work starts
3. admission has a defined decision point for routed work that targets governed roots
