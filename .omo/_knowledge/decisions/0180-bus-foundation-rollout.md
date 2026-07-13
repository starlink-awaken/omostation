---
status: ACCEPTED
lifecycle: decision
owner: governance-team
last-reviewed: 2026-07-13
---

# ADR-0180 — bus-foundation 全面落地 (P7x-bus-foundation-rollout)

**Date**: 2026-07-09
**Round**: R-Integration (R80+)
**Status**: ACCEPTED
**Supersedes**: partial coverage of bus-foundation in R0–R97

## Context

Prior to this ADR, bus-foundation was a 0.3.0-quality library with 320+ tests
but adoption was entirely dormant: all 8 declared consumers listed it in
pyproject.toml yet **none** had a single production call site in their `src/`
trees. This is the P71 class-A failure mode: declaration without execution.

Root cause analysis identified three compounding factors:
1. No discovery mechanism — consumers imported `bus_foundation` but never initialized a backend
2. Missing topics SSOT — topic strings were scattered across consumers as raw literals
3. No regression gate — CI never checked whether declared consumers stayed active

## Decision

Implement a **3-plane facade + topics SSOT + dormant-adapter gate** pattern:

### 3-Plane Facade
bus-foundation exposes three planes:
- **Data plane**: publish/subscribe/envelope
- **Event plane**: typed domain events
- **Control plane**: health/metrics/admin

Each plane has a unified facade (`BusFacade`) that hides backend selection.

### Topics SSOT
All topic constants are centralized in `bus_foundation.topics` (30+ topic
constants). Consumers import from the SSOT, never hardcode strings.

### Dormant-Adapter GaC Gate (P74)
A new GaC gate `bus-usage-report` scans every consumer's `src/` for
production bus-foundation calls. Exits 1 if any declared consumer has no
real call site. Wired into gac-local-gate as non-strict (commit-time check).

## Consequences

### Positive
- 320 → 344 unit tests (+24)
- 6 new e2e tests across 5 consumers
- P74 gate prevents future dormancy regression
- Topics SSOT eliminates string drift

### Caveats
- `bus-usage-report` runs in ~2.5s on real workspace (adds to pre-commit time)
- pyzmq optional dep requires bus-foundation venv to run e2e

### Open Questions
- Should the gate also scan test files for mock-based false negatives?
- How to handle consumers that use bus-foundation indirectly via facade?

## References
- `.omo/_knowledge/patterns/p74-workflow-solidification-pattern.md`
- `projects/bus-foundation/src/bus_foundation/topics.py`
- `bin/bus-usage-report.py`
