# Phase 7 Wave 2 execution plan

> Status: completed packet
>
> Goal: `G7.2` resource accounting visibility

## Objective

Make operator-visible usage and cost accounting real enough to support follow-up governance decisions.

## What Wave 2 landed

1. **Usage accounting truth**
   - `scripts/omo_experience.py` now writes `.omo/_truth/task-center/usage-accounting.yaml`.
2. **Dispatch visibility**
   - accounting reports summarize task counts, dispatch counts, and worker distribution from live runtime artifacts.
3. **Cost surface**
   - cost-by-org data is folded into the same accounting report so resource visibility no longer depends on ad hoc inspection.

## Verification

1. `python3 -m pytest .omo/tests/test_omo_experience.py -q`
2. `python3 scripts/omo_experience.py accounting --now 2026-05-31T10:20:00Z`
3. `python3 scripts/sync_omo_state.py --omo-dir .omo`
4. `python3 -m pytest .omo/tests -q`

## Exit judgment

Wave 2 is complete when usage and cost are persisted into governed truth and summarized for operators without inventing a second control surface.
