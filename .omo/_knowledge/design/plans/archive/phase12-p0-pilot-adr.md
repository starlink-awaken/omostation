---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P55 R1: Phase 1-13 历史执行计划归档, 当前阶段/状态以 .omo/state/system.yaml + .omo/goals/current.yaml 为准"
---
# Phase 12 P0 pilot ADR

> Status: accepted
> Date: 2026-06-01

---

## Decision

Select `LiteLLM -> agentmesh Gateway` as the single Phase 12 P0 fusion pilot.

## Context

Phase 12 may run exactly one P0 pilot. The alternative candidate is `memU -> gbrain memory backend`.

## Evaluation

| Candidate | Value | Risk | Interface maturity | Result |
|-----------|-------|------|--------------------|--------|
| LiteLLM -> agentmesh Gateway | High routing value and clear gateway boundary | Medium | Higher | selected |
| memU -> gbrain memory backend | High memory value but deeper data semantics risk | High | Lower | deferred to Phase 14 |

## Rollback plan

- Keep provider routing unchanged unless a later approved task activates it.
- Disable the pilot registry contract.
- Preserve package dry-run as no-mutation evidence.

## Deferred item

`memU -> gbrain memory backend` remains in Phase 14 as a deferred deep absorption candidate.
