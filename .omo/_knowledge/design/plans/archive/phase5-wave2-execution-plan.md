---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P55 R1: Phase 1-13 历史执行计划归档, 当前阶段/状态以 .omo/state/system.yaml + .omo/goals/current.yaml 为准"
---
# Phase 5 Wave 2 execution plan

> Status: completed packet
>
> Goal: `G5.2` auto-discovery + templates

## Objective

Compress task definition cost while preserving a single metadata truth.

## What Wave 2 locked in

1. **Single-source metadata rule**
   - `task-center-requirements.md` and `phase5-task-center-landing-model.md` establish `_truth/task-center/registry.yaml` as the only truth owner for scheduling definitions.
   - indexes remain link surfaces, never dynamic mirrors.

2. **Template packet rule**
   - `.omo/tasks/README.md` remains the canonical governance task schema.
   - `phase5-wave0-task-specs.md` becomes the reference pattern for turning program goals into execution-ready task packets.
   - plan/spec/task/evidence/retro is the reusable template chain for future waves.

3. **Discovery/reconciliation rule**
   - frontmatter and registry reconciliation stay downstream of the owner-plane contract, not a parallel SSOT.
   - drift repair must produce delivery evidence rather than silently mutating indexes.

## Evidence packet

1. Wave 0 task packet shows the phase-to-task templating pattern in production use.
2. `.omo` plan/readme/index updates show how packets are promoted without creating fake live mirrors.
3. the convergence audit and review refresh packet remain the anti-corruption guardrails for discovery/template work.

## Exit judgment

Wave 2 is complete as a **metadata compression and packet-templating contract**: future discovery/template implementation can be derived from this packet without re-opening truth ownership or plan/task translation rules.
