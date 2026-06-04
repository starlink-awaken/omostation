# Phase 7 Wave 3 execution plan

> Status: completed packet
>
> Goal: `G7.3` freshness entropy automation

## Objective

Convert freshness drift from a conversational intuition into a persistent, operator-readable runtime mechanism.

## What Wave 3 landed

1. **Freshness artifact**
   - `scripts/omo_experience.py` now emits `.omo/_delivery/task-center/freshness/current.yaml`.
2. **Stale-item judgment**
   - freshness reports score drift and list stale items directly from live divergence/state surfaces.
3. **Operator summary**
   - the generated Wave 3 summary turns freshness into a documented, reviewable closeout artifact.

## Verification

1. `python3 -m pytest .omo/tests/test_omo_experience.py -q`
2. `python3 scripts/omo_experience.py freshness --now 2026-05-31T10:25:00Z`
3. `python3 scripts/sync_omo_state.py --omo-dir .omo`
4. `python3 -m pytest .omo/tests -q`

## Exit judgment

Wave 3 is complete when freshness drift is persistently recorded, scored, and explainable through governed artifacts rather than manual interpretation.
