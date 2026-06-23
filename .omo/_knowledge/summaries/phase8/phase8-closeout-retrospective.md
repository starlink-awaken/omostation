---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P55 R2: phase 子目录历史总结批量归档, 当前阶段以 .omo/state/system.yaml 为准"
---
# Phase 8 closeout retrospective

## Overall judgment

**Phase 8 completed / GO**

## Main result

Phase 8 turned Phase 7's visibility loop into a governed control plane: budget and freshness can now influence execution before work starts, the worker/sync path no longer assumes a single `.omo` storage root, Hermes bridge bootstrap defaults to wrapper-only convergence, and sensitive blocked surfaces now have explicit ratification criteria.

## Completed work

1. **Wave 0 — planning gate**
   - ratified the control-first Phase 8 program and seeded one execution packet
2. **Wave 1 — budget and freshness control plane**
   - added pre-execution control decisions plus persisted control artifacts
3. **Wave 2 — Hermes and storage convergence**
   - removed key `.omo` root hardcoding from worker/sync paths
   - made Hermes bridge installation wrapper-only by default
4. **Wave 3 — cross-repo governance and blocked-surface ratification**
   - recorded the repo-local governance boundary for sensitive blocked surfaces and future rollout

## Verification baseline

1. `python3 -m pytest .omo/tests/test_omo_experience.py -q -k control_gate`
2. `python3 -m pytest .omo/tests/test_omo_automation.py -q -k 'custom_omo_root or wrapper_only or legacy_installers'`
3. `python3 scripts/omo_worker.py task validate --all-active`
4. `python3 scripts/sync_omo_state.py --omo-dir .omo`
5. `python3 -m pytest .omo/tests -q`

## Lessons

1. Control is most effective when visibility artifacts are promoted into explicit pre-execution gates.
2. Storage and bridge convergence does not require a full substrate rewrite; removing a few hardcoded assumptions yields most of the operational value.
3. Governance ratification should be the final layer of a phase, not an afterthought, because it decides how safely the new runtime can expand.
