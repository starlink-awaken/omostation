---
status: ACCEPTED
lifecycle: decision
owner: 夏明星
last-reviewed: 2026-07-24
related:
  - 0228-m1-acceptance-physical-deferred-reorder.md
  - 0225-g-del-physical-multihost-gate-caliber.md
  - STRAT-P81-strategic-roadmap.md
supersedes: []
amends: []
---

# ADR-0230: Agent registry — node / role / capability (sim first)

## Context

Batch1 C1 needs node registration, heartbeat, false-death detection, and relation
to agora I0. Physical multi-host remains blocked (ADR-0228).

## Decision

1. **Three-level model**:
   - **node_id**: logical or physical host
   - **role_id**: capability profile (engineering/governance/audit or implementer…)
   - **agent_id**: running instance on a node with capacity/inflight
2. **Implementation**: extend `bin/delivery/agent_registry.py` (in-process multi-node
   sim) with `detect_false_death(stale_after_s)`.
3. **agora I0**: registry remains L2 measurement/sim plane; production discovery
   continues via agora bos-services / MCP — no dual writer of port SSOT.
4. **Caliber**: tests fill only `meets_sim_harness`; never physical `meets_gate`.

## Confirmation

- 4 logical nodes register + heartbeat + false-death unit tests pass
- Schedule harness reuses registry (`schedule_harness.py`)

## Status

**ACCEPTED** for Batch1 sim ship (2026-07-24).
