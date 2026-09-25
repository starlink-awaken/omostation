---
schema: md/v1
status: ACCEPTED
lifecycle: spec
owner: 夏明星
last-reviewed: 2026-09-25
type: ssot
id: ADR-0231
related: 
supersedes: []
amends: []
---


# ADR-0231: Failover — task migration on node loss

## Context

Batch1 C3: design task migration when a node is lost; script dry-run without real hosts.

## Decision

1. On false-death / mark_unhealthy, agents on that node stop receiving new tasks.
2. Scheduler picks least-loaded healthy agent (existing TaskScheduler policy).
3. Drill entry: `bin/_archive/2026-08-conv3/failover_drill.py --dry-run` (sim 4 nodes, kill node-0,
   assert all tasks land elsewhere).
4. Physical pull-cable uses the same script once hosts restore; no code change path
   for strategy — only env/endpoint config for physical measure.

## Confirmation

- dry-run exits 0 with `migrated_away_from_dead_node=true`
- `meets_physical_gate=false` always in sim

## Status

**ACCEPTED** (2026-07-24).
