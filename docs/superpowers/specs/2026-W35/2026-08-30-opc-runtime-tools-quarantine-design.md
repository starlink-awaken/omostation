---
schema_version: specification/v1
spec_version: 1.0.0
title: OPC runtime tools physical quarantine
bet_id: BET-Y1Q3-T10-92
status: accepted
lifecycle: contract
owner: governance-team
created: 2026-08-29
last_updated: 2026-08-29
risk_level: L2
human_gate: true
type: ssot
last_updated: 2026-09-03
---

# OPC runtime tools physical quarantine

## Intent

Remove two unconsumed executable helpers from the Documents content plane
without converting their absence into a false owner-parity claim.

## Contract

- Audit `Documents/@OPC` with the existing L4 content-plane classifier and
  select only artifacts classified as `runtime`.
- Audit current crontab, LaunchAgents, scheduled skills, and domain gateways
  with the existing consumer-audit tool; stop on forbidden or unmatched active
  consumers.
- Move selected files through the existing reversible quarantine owner into a
  protected Workspace retention package with a hash-valid manifest.
- Keep OPC content, contracts, projections, and facts in Documents. Advance
  the migration family only to `in_progress` until an accepted Toolbox or
  Workspace owner path is installed and documented.

## Acceptance

1. Exactly the two current OPC runtime files are selected.
2. Consumer and postflight evidence prove safe source absence and target parity.
3. Rollback remains possible and no permanent deletion occurs.
