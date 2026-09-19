---
schema_version: specification/v1
spec_version: 1.0.0
title: Family runtime KEMS physical quarantine
bet_id: BET-Y1Q3-T10-93
status: accepted
lifecycle: contract
owner: governance-team
created: 2026-08-29
last-reviewed: 2026-08-29
risk_level: L2
human_gate: true
type: ssot
last_updated: 2026-09-03
---

# Family runtime KEMS physical quarantine

## Intent

Remove stale executable surfaces from the family Documents domain while
preserving the domain's human content and keeping rollback available.

## Contract

- Audit `/Users/xiamingxing/Documents/@家庭生活/_runtime` and select only its
  L4-classified runtime entries; dangling symlinks are moved as symlinks and
  their lexical targets are never followed or rewritten.
- Audit `/Users/xiamingxing/Documents/@家庭生活/_control/_scripts` as a
  separate source root and select only its L4-classified runtime files.
- Require a fresh consumer receipt with zero forbidden executors and zero
  unmatched consumers before either move.
- Use the existing reversible quarantine owner for two collision-free,
  hash-verified Workspace retention packages.
- Leave README, contracts, projections, facts, and all other family content in
  Documents. Advance the registry only to `in_progress` until a Runtime/Kairon
  owner parity contract is accepted.

## Acceptance

1. The two scoped audits select 11 symlinks and 2 regular scripts exactly.
2. Source absence and target equality are independently verified for both
   manifests.
3. Rollback remains possible and no permanent deletion occurs.
