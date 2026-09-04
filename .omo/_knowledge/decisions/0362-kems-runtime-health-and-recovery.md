---
number: 362
id: ADR-0362
title: KEMS runtime health and verified SQLite recovery
status: ACCEPTED
date: 2026-08-04
owner: governance-team
lifecycle: spec
last_updated: 2026-08-04
---

# ADR-0362: KEMS runtime health and verified SQLite recovery

## Context

KEMS now has durable SQLite stores for OCR quality, adjudication, manifests,
pipeline checkpoints, model acceptance, and shadow forecasts. Each store is
idempotent, but operators had no common way to distinguish a healthy empty store
from a missing, corrupt, externally readable, or referentially inconsistent
database. Backup and restoration were also left to ad-hoc filesystem copies.

## Decision

Add a read-only KEMS runtime health contract and a verified SQLite backup/restore
path in `kos.kems.health`.

- Health reports contain only path, integrity, foreign-key, table, row-count and
  permission metadata; source rows and free-form payloads are never returned.
- Missing, corrupt, referentially inconsistent, or non-private databases report
  `degraded`; they never become an implicit empty-success state.
- Backups use SQLite's online backup API, a temporary file, mode `0600`, atomic
  replacement, and post-write health verification.
- Existing destinations are protected unless the operator explicitly requests
  replacement with `force`; restore uses the same verification path.
- Health and recovery have no authority to create a manifest, promote a model,
  mutate WorkflowRun state, dispatch an OMO task, or invoke a provider.

## Consequences

KEMS can expose a deterministic operational health projection and recover its
SQLite state without copying source content. A degraded store becomes an
explicit preflight blocker for manifest and shadow operations. The operator must
still run the existing adjudication, manifest, acceptance, and OMO approval gates.

## Verification

- Kairon KEMS regression and health tests pass.
- Ruff passes for the new module, scripts, and tests.
- Root GaC, documentation SSOT, and ADR coverage remain required before merge.
