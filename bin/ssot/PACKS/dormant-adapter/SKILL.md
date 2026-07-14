---
name: dormant-adapter
version: 0.3.1
status: ACTIVE
triggers:
  - "dormant adapter"
  - "P71 class-A trap"
  - "declaration without execution"
scope: |
  Detect consumers that declare bus-foundation in their dependencies
  but have no production call sites. The P74 dormant-adapter guard
  ensures every consumer is truly active on the bus.
out_of_scope: |
  Detecting dead CODE (not just dead DEPENDENCIES).
  General code quality checks (use lint instead).
  Cross-repository dependency management.
owner: governance-team
last-reviewed: 2026-07-09
related:
  - TELOS.md#beliefs (B1: dormant code is dead code)
  - ../../gac-local-gate.py (the bus-usage-report gate)
  - ../../../CLAUDE.md
---

# Dormant Adapter Detector

Detects "P71 class-A traps": consumer projects that declare
`bus-foundation` in their `pyproject.toml` but have **no production
call site** for the bus. A consumer that imports the facade but never
calls `bus_event.publish(...)` is dormant.

## Why this exists

On 2026-07-09, P7x bus-foundation rollout found that **8/8 consumers
were dormant** at the 0.3.0 release — they had `bus-foundation = [...]`
in dependencies but no actual bus usage. This Pack catches that
class of failure at pre-commit time.

## When to use

- **Before declaring a consumer "ready"** for a new bus-foundation release
- **In CI** via `gac-local-gate.py` (registered as `bus-usage-report`)
- **Periodically** as a health check on the consumer ecosystem

## Inputs

- `--root <dir>`: workspace root (default: parent of script dir)
- `--json`: emit machine-readable output
- `--projects-dir <name>`: name of projects subdir (default: `projects`)

## Outputs

Human-readable summary by default. With `--json`:

```json
{
  "root": "/path/to/workspace",
  "total_consumers": 8,
  "active": 8,
  "dormant": 0,
  "reports": [
    {"project": "omostation", "has_dep": true, "production_calls": 7, ...}
  ]
}
```

Exit codes:
- `0`: every consumer is active
- `1`: at least one consumer is dormant (P71 trap)

## Algorithm

1. Discover all `pyproject.toml` files under `--root/--projects-dir`
2. For each, check if `bus-foundation` is in dependencies
3. For projects with the dep, scan `src/` + `packages/*/src/` for
   call sites matching either of:
   - Direct facade call: `bus_event.publish(...)` etc.
   - Wrapped helper: `_bus_publish(...)` etc.
4. Report: ACTIVE if ≥1 call site, DORMANT if zero

See `../src/dormant_adapter.py` for the canonical implementation.

## See also

- [PAI/LifeOS dormant-adapter pattern](https://github.com/danielmiessler/LifeOS)
  — adapted from PAI's "do not declare unused dependencies" principle
- `TELOS.md` §B1 — "Dormant code is dead code"
- `../../../CLAUDE.md` — how this Pack fits into the workspace
