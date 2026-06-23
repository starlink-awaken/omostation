---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P55 R1: Phase 1-13 历史执行计划归档, 当前阶段/状态以 .omo/state/system.yaml + .omo/goals/current.yaml 为准"
---
# Phase 8 Wave 2 execution plan

Packet: `P8-W2-HERMES-STORAGE-CONVERGENCE`

## Goal

Reduce the highest-value Hermes and storage trust seams by removing `.omo` storage hardcoding from the worker/sync path and by making Hermes bridge installation wrapper-only by default.

## Scope

1. worker runtime accepts a configurable OMO storage root
2. sync/divergence artifacts and active-queue headers derive refs from the actual storage root
3. Hermes bridge bootstrap defaults to wrapper-only mode
4. legacy installer scanning becomes explicit opt-in

## Deliverables

1. `scripts/omo_worker.py`
2. `scripts/sync_omo_state.py`
3. `scripts/install-all-bridges.sh`
4. `.omo/tests/test_omo_automation.py`
5. `.omo/summaries/phase8-wave2-closeout.md`

## Exit gate

1. worker and sync can operate against a non-`.omo` root in tests
2. divergence artifact refs and active-queue headers no longer hardcode `.omo`
3. `install-all-bridges.sh` skips legacy installer execution unless `--legacy-installers` is passed
