---
schema_version: specification/v1
status: accepted
lifecycle: spec
owner: governance-team
last-reviewed: 2026-08-29
bet_id: BET-Y1Q3-T10-62
spec_version: 1.0.0
title: T10-62 Authority-Binding Contract Alignment — Design
type: doc
---

# T10-62 Authority-Binding Contract Alignment — Design

Date: 2026-08-29 · Bet: BET-Y1Q3-T10-62 · Risk: L1 · Appetite: 0.25 day

## Problem

omo #116 (BET-Y1Q3-T4-04) shipped the principal authority gate but left the
contract unaligned across consumers, breaking main:

1. The W2-03 capability-enforcement integration suite could never reach the
   semantics it tests — every fresh request is denied at the authority gate
   (`authority_required` / `authority_unknown`), so 8/11 cases failed.
2. The ecos M2 extension (reason enum `authority_*`, optional
   `principal_authority_ref`/`principal_receipt_digest`, v1.1.0) existed only
   on ecos main (#58); the root gitlink and omo's path-installed wheel were
   stale, so even the deny path could not construct a PolicyDecision
   (InvalidActionRequestError → PDP_UNAVAILABLE masquerade).
3. cockpit #91 (T4-04 Phase 2) introduced a direct `.omo/state` writer
   (`decide.py::_save_inbox`), tripping `omo.cli lint direct-omo-io`
   (contract_gatekeeper critical) and blocking root pushes.

## Design

- **omo test alignment (09acf5c2)**: register the fixture principal in an
  injectable `DefaultPrincipalAuthority`, wire it into every
  `PolicyEnforcementService` construction site, and carry the verified
  receipt triple on the shared `_request()` helper. Plus the lint repair of
  the cli/workflow_dispatch/blueprint extraction wave (F811/F821/format) so
  the pre-push gate passes for all queued work.
- **ecos pointer**: adopt e3a14731 (M2 1.1.0 additive extension) — no model
  edits here; #58 already shipped and recompiled the artifacts.
- **cockpit pointer (2d44b650)**: `decide.py` routes inbox writes through
  `omo.omo_io.ensure_parent_dir` + `write_text_atomic` (the sanctioned
  broker pair per contract_gatekeeper MUTATION_HELPER_NAMES).

## Verification

- `omo.cli lint direct-omo-io` exit 0 at the new cockpit pointer.
- W2-03 suite 11/11; sovereignty/resident suites 185 green.
- Ledger lint limited to pre-existing T1-12 and T10-58(quarantine, resolved
  by #2551) findings.

## Rollback

Pointer-only per consumer; revert the single alignment commit per repo.
