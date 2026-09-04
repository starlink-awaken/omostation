---
schema_version: specification/v1
spec_version: 1.0.0
status: accepted
lifecycle: contract
owner: human-principal
created: 2026-08-29
last-reviewed: 2026-08-29
bet_id: BET-Y1Q3-T10-50
risk_level: L1
type: ssot
last_updated: 2026-09-03
---

# Service Gateway bounded liveness scan

## Objective

Make read-only Service Gateway health views return within a bounded budget even
when many registered endpoints are unreachable, while preserving service order
and truthful per-service `unreachable`/`timeout` results.

## Contract

- Batch liveness checks use bounded parallelism and a finite per-probe timeout.
- `status`, `score`, and `graph` consume the same batch result instead of
  probing the registry serially.
- A timed-out probe is reported as `timeout` with an explicit reason; it is not
  counted as healthy.
- No liveness scan writes service state, starts processes, changes host
  services, or mutates registry/runtime data.

## Acceptance

- Regression tests prove bounded batch behavior and stable result ordering.
- `ops status --json`, `ops score --json`, and `ops graph --format dot` return
  within the configured total budget on a large synthetic service list.
- Existing single-service liveness semantics remain covered by focused tests.
- Python syntax and the default GaC gate pass.
