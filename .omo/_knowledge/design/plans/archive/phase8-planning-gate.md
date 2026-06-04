# Phase 8 planning gate

> Status: ratified gate packet
>
> Scope: planning gate + Wave 1 starter packet only

## Objective

Open Phase 8 with a control-first planning packet that defines how budget and freshness become pre-execution gates instead of post-execution observations.

## Gate checklist

1. Phase 8 program structure is explicit and bounded
2. only one execution-ready packet is seeded at ratification
3. Wave 1 is limited to budget and freshness control
4. Hermes/storage/cross-repo debt remains visible but gated

## Ratification rule

**GO** only if:

1. control plane can move from `Phase 7 completed` to `Phase 8 in_progress`
2. the starter packet stays within budget/freshness control scope
3. no second execution-ready packet is introduced
4. deeper architecture debt remains explicit instead of being hidden inside Wave 1

## Verification

1. `python3 -m pytest .omo/tests/test_phase8_planning_gate_docs.py -q`
2. `python3 scripts/omo_worker.py task validate --all-active`
3. `python3 scripts/sync_omo_state.py --omo-dir .omo`

## Exit judgment

The planning gate is complete when Phase 8 is live, exactly one Wave 1 packet is active, and the next runtime work is limited to the budget/freshness control plane.
