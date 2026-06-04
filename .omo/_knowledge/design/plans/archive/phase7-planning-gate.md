# Phase 7 planning gate

> Status: ratified gate packet
>
> Scope: planning gate + ratification only

## Objective

Open Phase 7 with a planning-first control packet that defines the full program and seeds only one execution-ready starter packet.

## Gate checklist

1. Phase 7 program structure is explicit and bounded
2. Only one execution-ready packet is seeded at ratification
3. `orphaned_tasks:1` is carried as tracked follow-up instead of hidden debt
4. Phase 7 Wave 1 focuses on tool adoption and user-journey enablement, not broad refactoring

## Ratification rule

**GO** only if:

1. the control plane can move from `Phase 6 completed` to `Phase 7 in_progress`
2. the starter packet remains inside Wave 1 journey-enablement scope
3. no second execution-ready packet is introduced
4. residual governance debt is explicitly named in the summary and starter packet gate

## Verification

1. `python3 -m pytest .omo/tests/test_phase7_planning_gate_docs.py -q`
2. `python3 scripts/omo_worker.py task validate --all-active`
3. `python3 scripts/sync_omo_state.py --omo-dir .omo`

## Exit judgment

The planning gate is complete when Phase 7 is live, exactly one Wave 1 packet is active, and the remaining governance debt is visible in control truth.
