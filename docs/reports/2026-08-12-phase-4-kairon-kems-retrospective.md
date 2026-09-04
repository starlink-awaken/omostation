---
type: ephemeral
created: 2026-09-03
---

# Phase 4 Retrospective — Kairon/KOS KEMS Content Operations

> Date: 2026-08-12
> Scope: Documents content-plane convergence, Task 5
> Accepted upstream: Kairon PR #65, squash merge `0a31da635826019927a99f0b67b0d89c5e342785`

## Outcome

Kairon/KOS now owns the reusable, metadata-only KEMS checks that were previously scattered across Documents scripts:

- all 12 public KEMS entry points and 10 learning-domain scripts have an explicit `retire | map-existing | extend` decision;
- seven scripts are marked for retirement, eight map to existing Workspace owners, and seven contribute a small reusable KOS behavior;
- `check_content_records` validates required metadata, allowed status, review freshness, duplicate refs, and exact index coverage;
- `check_source_consistency` compares immutable `SourceManifest` admission decisions with a redacted `GraphStore` snapshot;
- `build_domain_profile` binds a Documents Method/Profile and its sources by ref, version, and SHA-256 while reusing GraphStore and SQLite health contracts;
- no legacy CLI, MCP server, scheduler, dashboard, indexer, installer, or Documents writer was copied into Kairon.

This phase adds owner parity. It does not yet switch consumers or delete legacy Documents assets.

## SSOT Decision

Documents remains authoritative for content, Method, Profile, and source decisions. KOS is the only KEMS runtime and stores only derived runtime state. L4 owns domain identity and bootstrap, OMO owns task and lifecycle state, Runtime owns execution and schedules, and Cockpit owns projections.

The new domain profile therefore carries only refs, hashes, versions, counts, safe database health, and consistency status. Raw bodies, OCR text, evidence quotes, source URIs, and Documents paths are excluded from its output.

## Verification Evidence

- TDD RED: both new KEMS modules were absent and produced two collection errors;
- focused content/domain profile tests: 6 passed;
- KEMS test set: 68 passed;
- scoped Ruff check and format: clean;
- scoped mypy with skipped external imports: zero errors;
- GitNexus impact: LOW, no affected execution processes;
- GitHub CI: lint, KEMS focused tests, and KEMS integration smoke all passed;
- PR file surface: six files, 679 additions, no Documents-domain writes.

## Efficiency Adjustment

The repository-wide `make test-diff` target currently executes `uv run` inside `packages/kos`, where pytest is unavailable. Repository-wide Ruff also reports 13 existing errors in Iris, Kronos, Minerva, MOS, and Sophia. The broader KOS suite contains unrelated optional-dependency and existing SQLite/schema failures.

Under the single-user delivery bar, these are recorded as baseline debt because the new KEMS files pass focused tests, scoped lint/type gates, impact analysis, and all configured GitHub checks. Task 5 did not expand into repairing unrelated packages or installing optional dependencies.

## What Worked

1. **Decision table before porting.** Most legacy behavior mapped to an existing owner or should be retired; only seven behaviors needed an extension.
2. **Metadata-only boundary.** Outputs expose refs and hashes without turning Kairon into a second private-content authority.
3. **Reuse over copying.** GraphStore, SourceManifest, and SQLite health remain the runtime primitives.
4. **Focused evidence.** One impact pass and the configured CI gates were enough; no repeated hardening review loop was required.

## Remaining Debt

- Legacy consumers still call some Documents scripts; Task 9 performs consumer cutover after Runtime parity exists.
- The 22 legacy files remain in place until the migration registry has fingerprints, verification evidence, rollback references, and an approved removal batch.
- Runtime does not yet provide a Documents command/job adapter or enforce the no-write-back boundary at execution time.
- The 12 domain gateways still require the separately confirmed batch update and standalone-client smoke.

## Next Phase

1. Implement the Runtime Documents adapter and registered jobs without copying L4/KOS/OMO/Cockpit logic.
2. Enforce dry-run, JSON envelopes, bounded subprocess execution, and denial of writes back into Documents.
3. Only then cut active consumers from legacy KEMS scripts to KOS/Runtime owners and advance migration evidence.
