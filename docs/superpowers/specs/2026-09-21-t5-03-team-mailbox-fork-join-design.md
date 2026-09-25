---
schema: md/v1
status: accepted
lifecycle: spec
owner: governance-team
last-reviewed: 2026-09-25
type: ssot
schema_version: specification/v1
spec_version: 1.0.0
title: team-mailbox fork-join multi-agent orchestration
bet_id: BET-Y2Q2-T5-03
created: '2026-09-21'
implementation_authorized: true
value_indicator_policy: false
risk_level: L2
human_gate: false
---


# team-mailbox fork-join multi-agent orchestration

## Problem

With durable delivery (BET-Y2Q2-T5-02) in place, there is still no
orchestration protocol: fanning one objective out to several agents and
joining their results back together is manual, unobservable, and has no
claim discipline. Parallel lanes drift without a shared join barrier.

## Change

Implement a `fork_join` coordinator on top of the durable mailbox without
touching delivery internals. `fork` publishes one task message per lane with
a shared `run_id`; `join` blocks until every lane's result message arrives or
the barrier timeout fires, then aggregates results in lane order. Wire the
task-claim state machine (`pending` → `claimed` → `done`) to mailbox
messages so double-claim is rejected. Cover with `bun test` cases:
fork-scatter, join-gather ordering, barrier timeout, and double-claim
rejection. If join correctness is not met, fall back to single-task direct
dispatch and keep fork-join unadvertised.

## Acceptance

- `cd ~/.config/opencode/plugin/team-mailbox && bun test` exits 0.
- `grep -r -c "fork_join" ~/.config/opencode/plugin/team-mailbox` exits 0.
- `grep -c "team-mailbox" ~/.config/opencode/opencode.json` reports >= 1.

## Non-goals

- No change to delivery-semantics internals.
- No cross-machine synchronization.
