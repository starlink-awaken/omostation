---
schema_version: specification/v1
spec_version: 1.0.0
title: Family dashboard Workspace owner migration Phase A
bet_id: BET-Y1Q3-T10-111
status: accepted
lifecycle: contract
owner: family-hub
created: 2026-08-30
last_updated: 2026-08-30
type: ssot
last_updated: 2026-09-03
---

# Family dashboard Workspace owner migration Phase A

## Context

The Documents content plane still contains a mature Next.js application at
`/Users/xiamingxing/Documents/@家庭生活/family-dashboard-app`. A read-only
2026-08-31 inventory measured 38,925 files and 731,769,092 bytes. Most of that
surface is reproducible runtime material:

- `node_modules`: 34,839 files and 619,976,925 bytes;
- `.next`: 3,759 files and 109,447,419 bytes;
- `app-data`: 20 files and 1,022,959 bytes;
- source, scripts, public assets, tests, and configuration: the remaining small
  canonical application surface.

The source directory is not a Git repository. It includes a Next.js 16 / React
19 application with pages, API routes, search, tasks, files, health, growth,
assets, timelines, AI helpers, cron routes, tests, deployment assets, and a Bun
lockfile. It also includes generated state, local credentials, browser auth
state, build output, and household-specific data/configuration.

The existing `projects/family-hub` repository is the declared owner but does
not yet provide parity. It currently owns a smaller Vite quest UI, Express API,
Python FastMCP service, and SQLite-backed task/points behavior. Deleting the
Documents application now would lose capability. Keeping both applications as
peers would preserve a second product contract and violate the declared owner
boundary.

The current migration registry already names the replacement as
`projects/family-hub/apps/dashboard plus Workspace runtime state` and requires
the old source to remain until family-hub build, E2E, and client cutover pass.
The broader convergence plan requires owner implementation before consumer
cutover and physical retirement.

These counts and file observations are a dated discovery snapshot. The import
must remeasure the source immediately before producing its immutable receipt.

## Decision

Execute the convergence in three separately admitted phases:

1. **Phase A — owner import, this specification and BET.** Establish the
   canonical dashboard source under `projects/family-hub/apps/dashboard`, with
   deterministic provenance, no private/runtime payloads, explicit path
   boundaries, test fixtures, and build/test evidence. Keep the old app and all
   consumers unchanged.
2. **Phase B — runtime-state relocation, separate BET.** Materialize current
   generated data, indexes, caches, audit logs, and any SQLite state under the
   existing Workspace runtime plane; prove read-only Documents access and
   proposal/approval-mediated writes.
3. **Phase C — entry cutover and retirement, separate BET.** Switch Cockpit and
   operational consumers to family-hub, execute real-data E2E and an observation
   window, then quarantine or remove the old app and reproducible caches through
   a recoverable transaction.

Phase A creates no second registry, dispatcher, human entry point, data store,
or control plane. `family-hub` remains the owner; Cockpit remains the eventual
single human entry; OMO remains the write approval/evidence authority.

## Alternatives

1. **Independent nested Next.js package — selected.** Add
   `apps/dashboard/package.json` and its own `bun.lock`, preserving the imported
   application's dependency graph while avoiding changes to the existing Vite,
   Express, and Python roots.
2. **Convert family-hub to a Bun monorepo now — rejected for Phase A.** A root
   workspace can be evaluated later, but it couples source relocation to package
   manager, CI, Vite, API, and release changes that are not required to establish
   ownership.
3. **Copy the entire 806 MiB directory — rejected.** It would import caches,
   generated indexes, local secrets, browser credentials, and household data,
   obscuring the distinction between source ownership and runtime relocation.
4. **Delete the old application and rebuild selected screens — rejected.** The
   current family-hub is not feature-equivalent and lacks evidence for safe
   substitution.

## Phase A architecture

The target is a bounded application package:

```text
projects/family-hub/
├── api/                         existing Express owner surface
├── src/                         existing Vite quest UI and Python package
├── apps/
│   └── dashboard/              imported Next.js application owner surface
│       ├── src/
│       ├── scripts/
│       ├── public/
│       ├── e2e/
│       ├── tests/fixtures/      synthetic, non-household build/E2E data
│       ├── package.json
│       ├── bun.lock
│       └── migration receipt
└── tests/                       existing family-hub tests
```

The nested package is independently installable and testable. Phase A does not
replace the root `package.json`, move the Vite app, merge APIs, change ports, or
change launch/runtime registrations.

## Import contract

The importer operates from an explicit source and destination and fails closed.
It produces a deterministic selected-source receipt before copying and a target
receipt after copying.

### Allowed canonical classes

- application TypeScript/TSX/CSS and static public assets;
- build, lint, unit-test, Playwright, Docker, and deployment configuration after
  host-path and secret normalization;
- scripts required to build or validate application data;
- package metadata and the source Bun lockfile;
- product documentation that does not contain household facts, credentials, or
  host-only operational instructions;
- sanitized schemas/templates and synthetic test fixtures.

### Forbidden classes

- `node_modules/`, `.next/`, `out/`, `build/`, coverage, and test results;
- `app-data/`, generated indexes, generated embeddings, AI caches, and SQLite;
- `.env.local`, other local env files, credentials, tokens, browser auth state,
  `.trae/`, `.DS_Store`, logs, audit logs, and TypeScript build info;
- source `data-manifest` or embedded JSON containing real household identities,
  health, finance, schedule, task, or relationship facts unless converted to a
  reviewed synthetic fixture;
- absolute `/Users/...`, Documents-default, or host-specific deployment paths;
- symlinks, sockets, devices, or unrecognized file types.

The receipt records source-root identity, selected relative paths, type, mode,
size, SHA-256, selected count/bytes/fingerprint, exclusion categories, and the
target fingerprint. It is migration evidence, not a second capability registry.
The source remains untouched.

## Data and path boundaries

Phase A introduces one internal path adapter consumed by dashboard code:

- `FAMILY_DOCUMENTS_ROOT`: explicit read-only household content root. There is
  no fallback to `process.cwd()/..` and no default absolute user path.
- `FAMILY_DASHBOARD_STATE_ROOT`: generated JSON, indexes, embeddings, AI cache,
  task state, and audit output root. Production use must resolve outside Git and
  outside Documents under the existing Workspace runtime plane.
- tests and build use temporary or checked-in synthetic fixtures; they do not
  require live Documents or copied `app-data`.

Direct Documents mutation is disabled by default. Routes or actions that save
files, update vaccine/milestone Markdown, perform backup, or otherwise write
through the content root return a typed disabled response in Phase A. Enabling
real writes is a Phase B decision requiring OMO proposal/approval and audit
receipts; an environment toggle alone is insufficient authority.

The imported package may retain read-side functionality and route shapes, but a
read must remain within the canonicalized Documents root, reject traversal and
symlink escapes, and degrade explicitly when the root or fixture is unavailable.

## Build and runtime behavior

Phase A proves the code can be owned and reproduced by family-hub without
claiming production cutover:

- dependency installation is locked by the nested `bun.lock`;
- unit tests use temp directories and synthetic fixture data;
- `next build` must not generate or modify tracked files;
- build-time rendering must not depend on private household data;
- generated CSS, Next output, app data, audit output, and auth state remain
  ignored;
- the existing family-hub Vite build and Python tests remain green;
- no host service, schedule, Cockpit contract, port registry, or Documents node
  is changed.

## Error handling

The import stops without changing the source when it encounters an unknown file
class, symlink, source drift, destination collision, duplicate relative path,
hash mismatch, secret/PII scanner finding, absolute host path, or target file not
represented in the receipt.

The application fails closed for an absent/invalid Documents root, absent state
root, path escape, write request, malformed generated data, or write-capability
request. User-facing read routes may return an explicit unavailable/empty state;
they must not silently point back to the old Documents application directory.

Rollback for Phase A is Git revert of the child import commit. Because no source,
runtime payload, consumer, or host state changes, operational rollback is not
required in this phase.

## Testing and evidence

Implementation is test-first for new boundary behavior. Required evidence:

1. Import policy tests reject every forbidden class, symlink, unknown file,
   collision, source drift, target drift, absolute host path, and representative
   household/private fixture.
2. A dry-run import receipt is deterministic; apply produces exact selected
   source/target path and fingerprint equality while the full source tree remains
   unchanged.
3. Path adapter tests prove explicit roots, no parent fallback, Documents
   traversal/symlink rejection, state isolation, and temporary fixture support.
4. Write-boundary tests cover file save, tasks, vaccine/milestone updates, AI
   caches, rebuild, backup, and audit paths; no test writes into Documents.
5. Dashboard unit tests, lint, and production build pass from a clean child clone
   without live household data.
6. A bounded Playwright smoke covers authentication plus representative home,
   members, health, growth, assets, search, tasks, files, graph, and unavailable
   write behavior using synthetic data.
7. Existing family-hub Vite build and Python/FastMCP tests pass unchanged.
8. Child PR required checks pass, merge to child main is proven, and tests replay
   from child main before the root gitlink PR is created.
9. Root gitlink equals child `origin/main`, root required checks pass, root PR is
   merged, and the same root/family-hub tree and focused checks replay from root
   main.

## Delivery ordering

1. Merge this bootstrap specification/BET PR and replay ledger/spec validation.
2. Obtain explicit review of the written specification.
3. Produce and merge a detailed implementation plan document.
4. Create a fresh full-profile delivery attempt and start a BET-bound workflow.
5. Add RED tests and the deterministic import capability before copying source.
6. Import and adapt the dashboard in an isolated family-hub clone.
7. Merge the family-hub PR after required checks and mainline replay.
8. In a fresh root clone, update only the family-hub gitlink and root evidence;
   merge the root PR and replay from root main.
9. Close Phase A with a report, retro, completion matrix, and workflow closeout.
10. Admit Phase B and Phase C separately; do not infer their completion from
    Phase A.

## Phase boundaries and non-goals

Phase A does not:

- copy current `app-data`, real `data-manifest`, SQLite, indexes, caches, logs,
  credentials, or household content into Git;
- mutate or delete any Documents file;
- change host processes, cron, LaunchAgents, ports, deployment, or runtime state;
- cut Cockpit or any consumer to the new package;
- merge the existing quest UI/API/MCP implementations into the Next server;
- enable direct Documents writes;
- remove `family-dashboard-app`, `.next`, or `node_modules` from Documents;
- mark the migration family done;
- claim runtime parity, production availability, principal-bound value, or
  Documents-wide physical purity.

Phase B is complete only after Workspace runtime state and governed writes are
proven with real data. Phase C is complete only after the unique Cockpit contract,
consumer cutover, real-data E2E, observation window, recoverable old-app
retirement, and fresh Documents audit are proven.

## Acceptance criteria

- `projects/family-hub/apps/dashboard` exists on child and root main as the sole
  canonical Git-owned source for the imported Next dashboard.
- Import receipts prove exact selected source/target equality and unchanged
  source while every forbidden/runtime/private class is absent from Git.
- Explicit Documents/state root and disabled-write contracts are covered by
  tests; no default path resolves to the old application or a parent directory.
- Dashboard install, unit tests, lint, production build, synthetic E2E, existing
  Vite build, and Python/FastMCP tests pass from clean mainline checkouts.
- Child and root PRs are submitted, required checks pass, both PRs are merged,
  root gitlink equals child main, and mainline replay succeeds.
- The old Documents app and consumers remain unchanged, the migration family
  remains pending, and Phase B/C plus user value remain `NOT_PROVEN`.

## Anti-metrics

- Copied file count or bytes alone do not prove ownership or parity.
- A successful `next build` does not prove runtime data relocation or cutover.
- A merged child PR does not prove root-main adoption.
- A root gitlink does not prove Cockpit, live runtime, or user value.
- Absence of obvious secrets in a spot check does not replace an explicit import
  allowlist, forbidden-class scan, and reviewed receipt.

## Decision log

| # | Fork | Decision | Reason |
|---|---|---|---|
| 1 | Nested package or root monorepo conversion | Keep a standalone `apps/dashboard` package | Establishes ownership with the smallest cross-surface coupling and preserves existing family-hub entry points. |
| 2 | Whole-tree copy or allowlisted import | Deterministic allowlisted import | The source contains roughly 730 MB of reproducible/runtime material plus credentials and household data. |
| 3 | Import real manifests or synthesize fixtures | Keep real facts out of Git and use synthetic fixtures | family-hub is a GitHub repository; household health, finance, identity, and schedule data are runtime/content inputs, not source code. |
| 4 | Implicit parent root or explicit roots | Require explicit Documents and state roots | Moving the package changes `process.cwd()` ancestry; implicit fallback would silently read or write the wrong owner surface. |
| 5 | Preserve direct writes or disable them | Disable Documents writes in Phase A | Real writes need OMO proposal/approval and operational evidence, which belongs to Phase B. |
| 6 | Cut over with import or defer | Defer all consumers to Phase C | Source ownership is necessary but does not prove real-data parity or production readiness. |
| 7 | One broad BET or staged admission | Separate A/B/C BETs | Source import, host-state relocation, and consumer retirement have different risks, rollback, and proof. |
| 8 | PR created or merged as delivery | Require child and root merge plus mainline replay | The user explicitly requires PR merge, and branch-local evidence does not establish authoritative ownership. |
