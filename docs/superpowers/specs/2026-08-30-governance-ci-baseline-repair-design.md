---
schema_version: specification/v1
status: accepted
lifecycle: spec
type: design
owner: governance-team
created: 2026-08-30
last-reviewed: 2026-08-30
bet_id: BET-Y1Q3-T10-98
spec_version: 1.0.0
---

# Governance and CI baseline repair

## Problem

The current root mainline has four independent baseline defects that block
truthful delivery closeout: a clean CI checkout can lose the tracked state
projection after recursive private-submodule failure; one active BOS declaration
points at a missing root entrypoint; three governance rules use a check type
outside the canonical M2 enum; and ADR coverage cannot account for ADR-0435.
The resident BOS contract also still points at an older Agora gitlink.

## Decision

Repair only the declared baseline surfaces:

1. Make the state/goals CI job root-only so its checkout does not depend on
   recursive submodule availability.
2. Restore the missing monthly-healthcheck compatibility entrypoint as a thin
   Workspace-owned adapter to the canonical GaC healthcheck, and register it.
3. Map the three procedural governance declarations to existing executable M2
   categories (`audit_chain`, `freshness`, and `registry_integrity`) rather than
   expanding the metamodel with an unimplemented type.
4. Put ADR-0435 in the canonical decisions directory with valid frontmatter and
   index coverage; retain the historical `docs/adr` source as a compatibility
   record until its ownership is separately reviewed.
5. Bump the root Agora gitlink only to the fetched child `origin/main` so the
   resident BOS route check consumes the authoritative child registry.

No Documents content, host runtime, quarantine payload, or user-value evidence
is changed by this BET.

## Acceptance

- `gac-mof-validate`, ADR coverage, resident BOS routing, BOS evidence smoke,
  and clean-checkout state/goals enforcement are green.
- Existing root tests and `make gac-local-gate` pass without weakening or
  hiding a real declaration/execution gap.
- Root and child gitlink ancestry/reachability are recorded separately.
