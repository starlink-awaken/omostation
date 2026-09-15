---
id: T10-151
title: "A8 OMO 外部事务生命周期 — 7 阶段状态机"
status: accepted
date: "2026-09-15"
author: governance-agent
implementation_ref: "omostation-omo:agent/governance-agent/t10-151-a8-impl"
implementation_commit: "79b6c43"
parent_bet: T10-146
---

# A8 OMO External Transaction Lifecycle Design

## Summary

7-stage append-only event lifecycle for OMO external adapter transactions:
reserve → bind → readback → start → observe (ACK/fence) → verify → release → retire.

## Design

### State Machine

```
reserved ──► bound ──► readback_verified ──► started
    │                                      │
    │                                      ├─► observed ──► verified ──► released ──► retired
    │                                      │
    │                                      └─► fenced ──► operator_resolved
    └─► fenced ──► operator_resolved
```

### 7 Stages

1. **Reserve** — Register transaction intent with unique correlation key
2. **Bind** — Bind transaction to adapter capsule and verifier role
3. **Readback** — Verify capsule digest and role capabilities unchanged
4. **Start** — Persist start event, prepare adapter invocation
5. **Observe** — Consume adapter receipt; identity mismatch or unknown outcome → fence
6. **Verify** — Validate receipt operation matches bound capability
7. **Release/Retire** — Release resources, retire transaction (terminal)

### Fence-on-Unknown

Any unhandled error state (`unknown`, `failed`, `error`) transitions to `fenced`.
Fenced transactions require operator resolution — no auto-retry.

### Ledger-Backed

All state transitions are appended to `LedgerBroker` as `ExternalTransaction.*` events.
Idempotency keys prevent duplicate events.

## Acceptance Criteria

- [x] 7-stage state machine implemented
- [x] Fence-on-unknown for adapter errors
- [x] Identity mismatch detection (transaction_id, operation)
- [x] Digest readback verification
- [x] Operator resolution for fenced transactions
- [x] Full RED matrix test coverage (22 tests)
- [x] 22/22 tests passing
