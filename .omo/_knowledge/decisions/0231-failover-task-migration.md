---
status: ACCEPTED
lifecycle: decision
owner: 夏明星
last-reviewed: 2026-07-24
related:
  - 0230-agent-registry-node-role-capability.md
  - 0228-m1-acceptance-physical-deferred-reorder.md
supersedes: []
amends: []
---

# ADR-0231: Failover — task migration on node loss

## Context

Batch1 C3: design task migration when a node is lost; script dry-run without real hosts.

## Decision

1. On false-death / mark_unhealthy, agents on that node stop receiving new tasks.
2. Scheduler picks least-loaded healthy agent (existing TaskScheduler policy).
3. Drill entry: `bin/delivery/failover_drill.py --dry-run` (sim 4 nodes, kill node-0,
   assert all tasks land elsewhere).
4. Physical pull-cable uses the same script once hosts restore; no code change path
   for strategy — only env/endpoint config for physical measure.

## Confirmation

- dry-run exits 0 with `migrated_away_from_dead_node=true`
- `meets_physical_gate=false` always in sim

## Status

**ACCEPTED** (2026-07-24).
