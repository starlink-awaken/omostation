# Phase 10 Wave 3 execution plan

## Goal

Expand the normalized bundle interface to the first multi-action, action-first matrix.

## Scope

1. keep all work inside `system-space`
2. add `runtime.observe` next to `project.dispatch`
3. prove both actions resolve through the same typed bundle keys
4. keep CLI output and bundle readers action-agnostic

## Deliverables

1. `.omo/plans/phase10-wave3-execution-plan.md`
2. `.omo/_delivery/task-center/contracts/runtime-observe-delivery-contract.yaml`
3. `.omo/workers/runs/phase10-wave3-action-matrix-envelope.yaml`
4. `scripts/omo_rules.py`
5. `.omo/tests/test_phase10_wave3_docs.py`
6. `.omo/tests/test_phase10_wave3_matrix.py`

## Exit gate

1. Phase 10 Wave 3 is the only active packet and Wave 2 is archived
2. both `project.dispatch` and `runtime.observe` resolve through the same normalized bundle keys
3. `worker rules-eval` stays action-agnostic while printing the normalized refs
