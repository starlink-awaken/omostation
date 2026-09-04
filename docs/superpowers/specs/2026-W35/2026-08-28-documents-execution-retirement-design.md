---
schema_version: specification/v1
spec_version: 1.0.0
status: accepted
lifecycle: contract
owner: human-principal
created: 2026-08-27
last_updated: 2026-08-27
bet_id: BET-Y1Q3-T10-41
risk_level: L1
type: ssot
last_updated: 2026-09-03
---

# Documents execution retirement and Workspace owner convergence

## 1. Decision

Documents becomes a durable content plane. Workspace becomes the only owner of
execution, state, schedules, caches, indexes, and generated runtime evidence.
This is a capability-boundary migration, not a bulk file move: business
documents remain at their current paths unless a separate content-archive
decision is accepted.

## 2. Scope

The next wave covers the remaining active or potentially active surfaces under
Documents `_runtime` and `.kems`, beginning with `daily-health-run.py`, KOS
ingest scheduling, and any executable referenced by an active cron, LaunchAgent,
Scheduled skill, or domain gateway. It also inventories generated caches and
SQLite/index artifacts so they can be quarantined without confusing them with
source documents.

## 3. Required classification

Every candidate receives exactly one disposition:

| disposition | meaning | action |
|---|---|---|
| content | source material, report, evidence, or human decision | retain in Documents |
| workspace-owner | capability has a verified Workspace owner | migrate consumer, then preserve rollback |
| reference-only | Workspace reads it as input | retain; forbid execution |
| quarantine | generated runtime/cache/index with no active consumer | move to recoverable quarantine and observe |
| unresolved | consumer or semantic parity is not proven | do not delete or move |

No file is removed solely because it has a `.py`, `.sh`, `.json`, `.yaml`, or
`.db` suffix. Consumer evidence and replacement parity are mandatory.

## 4. Gates

Before a physical move or deletion, the owner must record the source path,
consumer set, replacement, file and byte counts, tree digest, before/after
hashes, rollback location, and a bounded observation window. The gate fails
closed on an unknown active consumer, a Documents write, a root overlap, a
missing accepted release, a changed business document, or an unverified
replacement.

The first implementation wave may only migrate schedules and owner jobs. A
second wave may quarantine generated runtime/cache material after consumer=0
and a rollback drill. Permanent deletion requires a separate human-gated BET.

## 5. Acceptance

- `daily-health-run.py` and KOS ingest have an explicit owner/consumer map;
- all active Documents executors are either migrated, classified as a verified
  read-only reference, or fail-closed as unresolved;
- a complete `_runtime/.kems` inventory separates content from generated
  material;
- no business document bytes or metadata are changed by the inventory;
- no permanent deletion is performed in this BET;
- the Documents/Workspace boundary is reflected in the architecture and
  convergence plan.
