# Capability binding policy

> Status: active
> Phase: 12

---

## Rules

1. Required scenario capabilities must resolve to registry records before a trace is accepted.
2. Missing required capability records fail closed.
3. Fallback is allowed only when the scenario declares `fallback-with-audit` and the trace records the fallback.
4. Dry-run traces may simulate execution but must record concrete capability IDs and entrypoints.
5. A scenario trace is evidence for readiness, not permission for live mutation.

## Audit trail

Every accepted trace must include:

- scenario id
- registry capability IDs
- entrypoints
- mode
- created timestamp
- step status
- missing capability list
