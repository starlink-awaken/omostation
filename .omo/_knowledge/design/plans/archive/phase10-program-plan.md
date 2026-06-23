---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P55 R1: Phase 1-13 历史执行计划归档, 当前阶段/状态以 .omo/state/system.yaml + .omo/goals/current.yaml 为准"
---
# Phase 10 program plan

> Status: active
>
> Theme: cross-root operating rule unification

## Objective

Phase 10 upgrades the workspace from “individual contracts exist” to “a single governed rule bundle can be resolved across spaces, data, runtime, delivery, and worker execution without duplicating policy logic in every packet.”

## Wave structure

### G10.1 / Wave 1 — cross-root rule registry baseline

Goal: define the first registry that maps a governed action to its cross-root contract bundle.

Status:

1. active as the current execution packet
2. packet: `P10-W1-CROSS-ROOT-RULE-REGISTRY`

Packet:

- `.omo/plans/phase10-wave1-execution-plan.md`

Scope:

1. define a cross-root rule registry for `system-space`
2. define the first data-root policy referenced by that registry
3. add a resolver/evaluation seam for worker envelopes
4. seed a live Wave 1 packet that proves bundle resolution for `project.dispatch`

### G10.2 / Wave 2 — rule normalization across data / runtime / delivery

Goal: normalize the per-root contracts so they can be reasoned about as one operating model.

### G10.3 / Wave 3 — rollout matrix expansion

Goal: expand the single live path into a reusable rollout matrix across more actions and spaces.

### G10.4 / Wave 4 — debt cleanup and closeout

Goal: pay down residual historical coupling and close Phase 10 with a stable contract surface.

## Sequencing rule

1. Wave 1 is the only execution-ready packet at Phase 10 kickoff
2. Wave 2 waits until a real cross-root bundle resolver exists
3. Wave 3 waits until the normalized contracts can be composed mechanically
4. Wave 4 closes only after historical debt is moved out of current-phase assumptions

## Success metrics

1. one registry resolves the rule bundle for a governed action
2. `spaces/`, `data/`, `runtime/`, and `.omo/_delivery/` each participate through explicit refs
3. worker execution can inspect the bundle without hardcoding per-root paths
4. Phase 10 can advance without reopening Phase 9 contracts
