---
schema: md/v1
status: ACCEPTED
lifecycle: spec
owner: 夏明星
last-reviewed: 2026-09-25
type: ssot
id: ADR-0229
related: 
supersedes: []
amends: []
---


# ADR-0229: Role framework — engineering / governance / audit first-ship

## Context

STRAT-P81 Batch1 B1 requires a role definition framework + collab protocol with
≥3 first-ship roles. G-DEL.2a contract already defines message types; runtime
exists as process-local CollabBus (`bin/delivery/role_collab.py`).

## Decision

1. **First-ship roles**: `engineering`, `governance`, `audit` (maps to implementer /
   orchestrator / verifier in G-DEL.2a handshake).
2. **Role =** capability set + send/recv message boundaries + private memory scope prefix.
3. **Host surface**: `bin/_archive/2026-08-conv3/role_framework.py` (thin orchestration over existing
   delivery tooling; aetherforge/swarm reserved for later multi-host).
4. **Protocol**: assign → claim_ack → handoff → verify_result → complete with
   PermissionError on illegal send/recv.

## Confirmation

- 3 roles register/load/switch unit-tested
- Protocol replay unit-tested
- Process-local only; does not fill physical `meets_gate`

## Status

**ACCEPTED** for Batch1 ship (2026-07-24).
