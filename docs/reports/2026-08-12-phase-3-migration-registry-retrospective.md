---
type: ephemeral
created: 2026-09-03
---

# Phase 3 Retrospective — Documents Migration Registry and Coverage Gate

> Date: 2026-08-12
> Scope: Documents content-plane convergence, Task 4
> Delivery: root PR #1359 from `work/documents-content-plane-migrations`

## Outcome

The current Documents runtime/cache debt is now a machine-owned migration inventory instead of a prose-only estimate:

- 15 non-overlapping migration families declare source patterns, artifact kinds, disposition, target owner, replacement, known consumer references, rollback, confirmation gate, and lifecycle status;
- the four major surfaces remain individually visible: family dashboard app, ToolBox staging, career code archives, and Zotero app data;
- a read-only checker fails closed on missing or multiple family matches, empty owners/replacements, unsafe patterns, duplicate IDs, incomplete samples, unsupported states, and terminal states without verification evidence;
- CI runs a fast representative-sample gate, while a local explicit `--documents-root` invocation performs the full L4 audit;
- no checker path moves, deletes, chmods, executes, or rewrites Documents content.

The live scan covered 44,527 runtime/cache candidates with zero unmatched and zero multiply matched assets:

| Evidence | Count |
|---|---:|
| Runtime | 7,649 |
| Cache | 36,878 |
| Total migration candidates | 44,527 |
| Major family dashboard surface | 37,423 |
| Major ToolBox staging surface | 2,703 |
| Major career archive surface | 2,601 |
| Major Zotero surface | 756 |
| Other governed families | 1,044 |

All 15 families remain `pending`. Coverage is not treated as migration completion.

## SSOT Decision

The migration registry is the owner of migration classification and lifecycle only. It does not replace:

- L4 for runtime/cache/content classification;
- L4 manifests for domain identity or content archives;
- Kairon/KOS for KEMS behavior;
- Runtime for execution and scheduling;
- OMO for tasks, approvals, and evidence;
- Cockpit for human and MCP projections.

This avoids storing 44,527 copied file records. The registry owns stable family rules; L4 supplies the live artifact set; the checker proves exact-one composition at evaluation time.

## Verification Evidence

- TDD RED: checker module absent; six contract tests failed;
- GREEN: nine migration-checker tests plus six domain-binding tests passed; the CI-surface registry validation also passed;
- live L4 composition: 322,221 audited artifacts, 44,527 runtime/cache candidates, zero unmatched, zero multiple matches;
- Ruff check and format: clean;
- GaC validation: 136 rules, zero errors/warnings;
- GaC drift: zero drift;
- governance trend: 133 active rules, full ADR coverage, within freeze limits;
- CI surface registry: zero errors; existing unrelated warnings remain advisory;
- document SSOT lint: 175 files, zero conflicts.

## What Worked

1. **Exact-one composition.** A path cannot silently disappear between migration teams or be claimed by two owners.
2. **Samples in CI, full scan locally.** CI stays fast and portable without pretending GitHub has access to private Documents content.
3. **Truthful lifecycle.** `verified` and `retired` require fingerprints, consumer scan, rollback reference, and verification time; `done` is not an accepted shortcut.
4. **Rule subtraction.** The new required rule replaced an already removed, superseded rule, keeping the GaC rule count at 136.
5. **No duplicated inventory.** Globs plus live L4 evidence are enough; a 44,527-row registry would be slow and immediately stale.

## Incident and Fix

The first live CLI run returned `candidate_count=0` even though a direct L4 audit showed 44,527 candidates. A second isolated import showed the audit itself was healthy. The CLI boundary was strengthened so live output now includes total audited artifacts and L4 counts. A non-empty Documents root cannot silently succeed if the audit reports zero artifacts, and a live scan cannot report zero migration candidates while any migration family remains non-terminal. Dedicated regressions lock both fail-closed conditions. Terminal evidence is also required to contain non-empty strings rather than placeholder keys.

## Remaining Debt

- All migrations are pending; no source consumer has been cut over in this phase.
- Existing content audit still contains seven invalid archive findings in addition to runtime/cache debt.
- The registry intentionally groups some domain runtime behind Runtime delegation; Task 5 must refine KEMS parity into `retire | map-existing | extend` decisions before code porting.
- Physical writes, app-data changes, deletes, external-repo relocation, and 12-domain gateway updates still require their explicit confirmation gates.

## Next Phase

1. Build the Kairon/KOS parity table for public, learning, family, and work-domain KEMS functions.
2. Add the minimal Runtime Documents adapter that denies writes back into Documents and delegates to registered owners.
3. After exact batch-write confirmation, update the 12 domain gateways and run standalone-project smoke for `vault`, `work-weijian`, and `creative`.
4. Do not retire any legacy source until owner parity, consumer cutover, fingerprints, and rollback evidence are present in the registry.
