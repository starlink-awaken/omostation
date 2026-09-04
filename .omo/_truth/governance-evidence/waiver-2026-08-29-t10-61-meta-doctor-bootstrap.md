---
schema: workflow-waiver/v1
lifecycle: history
owner: governance-team
created: 2026-08-29
last_updated: 2026-08-29
title: T10-61 meta-doctor refs-only registry bootstrap waiver
type: doc
---

schema_version: workflow-waiver/v1
waiver_id: WAIVER-2026-08-29-T10-61-BOOTSTRAP
issued_at: 2026-08-29T10:00:00Z
issued_by: user-authorized-agent
scope:
  bet_id: BET-Y1Q3-T10-61
  paths:
  - .omo/_truth/registry/ci-surfaces.yaml
  - tests/test_ci_surfaces.py
  - docs/plans/3y-bet-ledger.yaml
  - docs/superpowers/specs/2026-08-29-meta-doctor-refs-only-registry-design.md
  - docs/reports/2026-08-29-meta-doctor-refs-only-registry.md
  - .omo/_knowledge/retros/BET-Y1Q3-T10-61.md
reason: User-authorized continuation of the Documents capability-downshift work; the new BET and accepted specification must be bootstrapped before the formal workflow run can claim its surfaces.
constraints:
- Registry-only binding plus regression coverage; no meta-doctor implementation or workflow redesign.
- No Documents content or host/runtime mutation.
- Formal agent workflow must be started and all claimed paths verified before closeout.
expiry: 2026-08-30T10:00:00Z
