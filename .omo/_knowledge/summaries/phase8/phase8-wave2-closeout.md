# Phase 8 Wave 2 closeout

## Verdict

**GO** — the highest-value Hermes/storage seams are now converged enough to move into Wave 3 governance ratification.

## What closed

1. `scripts/omo_worker.py` now supports a configurable OMO storage root instead of assuming `.omo`.
2. `scripts/sync_omo_state.py` now derives divergence artifact refs and active-queue headers from the actual storage root.
3. `scripts/install-all-bridges.sh` now defaults to wrapper-only mode and requires explicit `--legacy-installers` opt-in to run legacy bridge installers.

## Evidence

1. `scripts/omo_worker.py`
2. `scripts/sync_omo_state.py`
3. `scripts/install-all-bridges.sh`
4. `.omo/tests/test_omo_automation.py`
5. `.omo/plans/archive/phase8-wave2-execution-plan.md`

## Exit judgment

Wave 2 met its bar: Phase 8 no longer depends on a single hardcoded `.omo` storage root in its key worker/sync path, and Hermes bridge bootstrap is now biased toward wrapper-only convergence instead of legacy installer side effects.
