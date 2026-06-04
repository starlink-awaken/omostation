# Phase 10 Wave 1 execution plan

## Goal

Seed the first cross-root rule registry baseline and prove it can resolve the operating rule bundle for `project.dispatch`.

## Scope

1. add `spaces/system-space-cross-root-rule-registry.yaml`
2. add `data/system-data-access-policy.yaml`
3. add `scripts/omo_rules.py` with a rule-bundle resolver
4. add `python3 scripts/omo_worker.py worker rules-eval <envelope_ref>`
5. seed a Wave 1 worker packet that points at the real Phase 9 rollout envelope

## Deliverables

1. `.omo/plans/phase10-wave1-execution-plan.md`
2. `spaces/system-space-cross-root-rule-registry.yaml`
3. `data/system-data-access-policy.yaml`
4. `scripts/omo_rules.py`
5. `.omo/workers/runs/phase10-wave1-cross-root-rules-envelope.yaml`
6. `.omo/tests/test_phase10_cross_root_rules.py`
7. `.omo/tests/test_phase10_kickoff_docs.py`

## Exit gate

1. Phase 10 is seeded as the active phase and Wave 1 packet
2. one real envelope resolves a rule bundle spanning `spaces/`, `data/`, `runtime/`, and `.omo/_delivery/`
3. `worker rules-eval` prints the resolved bundle for `project.dispatch`
