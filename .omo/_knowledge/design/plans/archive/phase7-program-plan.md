---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P55 R1: Phase 1-13 历史执行计划归档, 当前阶段/状态以 .omo/state/system.yaml + .omo/goals/current.yaml 为准"
---
# Phase 7 program plan

> Status: active
>
> Theme: let the tools actually run through real user journeys

## Objective

Phase 7 turns already-landed runtime, discovery, and skill seams into visible user-facing adoption loops. The emphasis is not "more tools exist", but "the toolchain is exercised through real journeys, with cost/freshness visibility and governance continuity."

## Wave structure

### G7.1 / Wave 1 — user journey enablement

Goal: raise tool adoption and D2 journey coverage by making Hermes and OMO use the existing tool surfaces end-to-end.

Scope:

1. self-context preload into Hermes-style flows
2. TaskObject/task bridge for complex work
3. positive-confirmation consensus marking
4. first freshness report and D2 reassessment

Packet:

- `P7-W1-USER-JOURNEY-ENABLEMENT`

### G7.2 / Wave 2 — resource accounting visibility

Goal: remove D9 cost blindness by making usage and cost visible through governed artifacts.

Scope:

1. token and cost accounting surfaces
2. usage registry or usage-db truth
3. summary CLI/report entry points

### G7.3 / Wave 3 — freshness entropy automation

Goal: make freshness degradation measurable and persistent instead of ad hoc.

Scope:

1. structured freshness output
2. writing reports into governed knowledge truth
3. D6 refresh scoring update

## Sequencing rule

1. Ratification seeds **Wave 1 only**
2. Wave 2 stays gated until Wave 1 closeout records a GO
3. Wave 3 stays gated until Wave 2 closeout records a GO
4. Active queue never contains more than one execution-ready packet

## Governance follow-up

`orphaned_tasks:1` remains a tracked follow-up entering Phase 7. Wave 1 must either resolve it or explicitly ratify its temporary tolerance before closeout.

## Verification baseline

1. `python3 scripts/omo_worker.py task validate --all-active`
2. `python3 scripts/sync_omo_state.py --omo-dir .omo`
3. `python3 -m pytest .omo/tests -q`
