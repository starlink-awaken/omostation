---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P55 R1: Phase 1-13 历史执行计划归档, 当前阶段/状态以 .omo/state/system.yaml + .omo/goals/current.yaml 为准"
---
# Phase 10 Wave 2 execution plan

## Goal

Normalize the cross-root bundle into one typed contract surface before adding more governed actions.

## Scope

1. add a typed delivery contract under `.omo/_delivery/task-center/contracts/`
2. normalize the `spaces/`, `data/`, and `runtime/` bundle shape for `project.dispatch`
3. extend `scripts/omo_rules.py` to return a typed bundle structure
4. seed a Wave 2 worker packet that proves the normalized bundle against the real workspace

## Deliverables

1. `.omo/plans/phase10-wave2-execution-plan.md`
2. `.omo/_delivery/task-center/contracts/project-dispatch-delivery-contract.yaml`
3. `.omo/workers/runs/phase10-wave2-normalized-rules-envelope.yaml`
4. `scripts/omo_rules.py`
5. `.omo/tests/test_phase10_wave2_docs.py`
6. `.omo/tests/test_phase10_wave2_normalization.py`

## Exit gate

1. Phase 10 Wave 2 is the active packet and Wave 1 is archived to `tasks/done/`
2. one real envelope resolves a normalized bundle with typed `data_contract` and `delivery_contract`
3. `worker rules-eval` prints the normalized bundle refs for `project.dispatch`
