---
type: ephemeral
created: 2026-09-03
---

# Phase 5 Retrospective — Runtime Documents Plane

> Date: 2026-08-12
> Scope: Documents content-plane convergence, Task 6
> Accepted upstream: Runtime PR #46, squash merge `822656c56ae745e57d6c4aa6f0b64c451d76281c`

## Outcome

Runtime now has a narrow execution boundary for Documents-owned content domains:

- `runtime documents run <job-id>` dispatches only commands registered by an existing owner;
- the default registry is empty, so this phase does not invent production jobs or duplicate L4, Kairon, OMO, or Cockpit logic;
- `DOCUMENTS_CONTENT_ROOT` is read-only and defaults to `~/Documents`;
- `OMOSTATION_RUNTIME_STATE_ROOT` is the only writable state root and must be physically disjoint from Documents;
- every owner run gets a fresh private working root, while Runtime control and evidence remain outside the owner write allowlist;
- dry-run creates no state and starts no process; non-zero exits and timeouts remain visible;
- non-Documents Runtime CLI commands continue through the existing CLI unchanged.

This phase establishes a safe owner adapter. It does not register or switch real Documents consumers; those changes remain governed migration work.

## Post-MVP Owner Registration — 2026-08-12

Runtime PR #47, merged as `e727c00e86fa8584c7e1766a1ef7f05b7b9826c5`, added two
read-only L4 owner jobs to the previously empty default registry. Root PR #1380,
merged as `47f8dba1a7a1b8bb76315c33543c7ba3f0124d7d`, adopted that Runtime
revision in Workspace.

- `l4-registry-list` delegates `l4-kernel registry list --registry <path> --json`;
  an overridden `L4_DOMAIN_REGISTRY` must resolve below
  `DOCUMENTS_CONTENT_ROOT`, and its declared read scope is the same resolved
  relative path.
- `l4-content-audit` delegates `l4-kernel content audit <Documents-root> --json`.
  It is an observation job: an existing L4 audit failure remains a non-zero
  Runtime result rather than a Runtime false success.
- Both jobs remain manual, have no Documents write scope, and record their
  metadata-only receipt under the Runtime state root. The immediate CLI JSON
  retains owner stdout and stderr; the receipt deliberately does not copy them
  because an audit response can contain private content and be very large.

Verification for this addendum: Runtime focused job tests (22 passed), scoped
Ruff check/format, full Runtime suite, the Runtime PR lint/test jobs, an
independent code review, and all root PR #1380 checks passed. A real registry
run succeeded. A real content audit returned its existing non-zero result, which
is expected evidence of unresolved Documents content-plane debt rather than a
successful migration.

This is shared infrastructure only. It does **not** establish source parity,
consumer cutover, a compatibility bridge, or a terminal migration state for
`@公共/_runtime`, `@驾驶舱/_runtime`, or any other migration family.

## SSOT Decision

Runtime owns execution mechanics and schedules, not domain meaning. Job specifications record owner, reads, writes, schedule, timeout, evidence path, and fail-closed policy, while the underlying commands remain authoritative in L4, Kairon, OMO, Cockpit, or another registered owner.

Documents is never a Runtime state store. Evidence is metadata-only and excludes owner stdout/stderr because command output may contain private content. Runtime state, temporary files, receipts, indexes, caches, and logs stay under the configured Runtime state root.

## Execution Boundary

The initial implementation validated declared paths but still launched an unrestricted subprocess. Review-driven TDD strengthened the actual execution boundary:

1. macOS owner processes execute through the fixed system sandbox with writes limited to declared output and a fresh per-run work root;
2. unsupported platforms or a missing sandbox return `125` without starting the owner;
3. state/Documents overlap is rejected in either direction, including case-folded and Unicode aliases on case-insensitive filesystems;
4. Runtime evidence/control is separated from owner output and published through directory file descriptors without following symlinks;
5. receipts use same-directory temporary files and atomic replacement, so scheduled jobs can run repeatedly;
6. timeout cleanup is bounded and returns `124`, including detached descendants holding output pipes;
7. non-UTF-8 output and expected setup/evidence I/O failures produce stable results and JSON instead of tracebacks.

## Verification Evidence

- TDD began with module-absence collection errors and added focused RED cases for every execution-boundary defect found in review;
- final focused suites: paths 8, commands 12, jobs 17;
- final covering command/job set: 29 passed;
- real macOS smoke: repeated owner attempts to poison XDG/work paths could not write Documents or Runtime control;
- CLI smoke: Documents help and delegated legacy version both exited zero;
- scoped Ruff check and format check: clean;
- full Runtime suite: reached 100% with exit zero;
- GitHub CI: lint and test passed;
- final independent code review: Ready to merge with no Critical, Important, or Minor findings.

## Efficiency Adjustment

The full suite still emits one pre-existing AsyncMock warning in registry sync. The workspace lock also has pre-existing resolution drift, so verification used `uv run --no-sync`; `uv.lock` was not modified. Neither issue was expanded into this task because all changed surfaces and configured GitHub checks passed.

Fresh per-run working roots are currently retained for diagnosis. Cleanup policy and non-macOS sandbox support are future operational work, not reasons to weaken the current fail-closed boundary.

## What Worked

1. **Execution enforcement over declarations.** A write policy matters only when the launched process cannot bypass it.
2. **Private control versus owner output.** Physical separation made evidence and repeated scheduling reliable.
3. **Real smoke tests.** APFS aliases, symlink poisoning, detached descendants, and repeated runs exposed defects that ordinary unit mocks missed.
4. **Stable envelopes.** Failure remains machine-readable without hiding the owner exit code or private output.
5. **Thin ownership.** Runtime gained dispatch mechanics without becoming another KEMS, task, domain, or dashboard authority.

## Remaining Debt

- Only the two generic, read-only L4 observation jobs are registered. Tasks 7–9
  still need a per-family owner command, source parity, consumer evidence, and
  any required compatibility bridge before a migration-family status can move.
- Non-macOS execution stays unavailable until an equally strong write sandbox is implemented.
- Fresh work-root retention needs an explicit Runtime-owned cleanup/retention policy after operational volume is measured.
- The 12 domain gateways still need their separately confirmed batch update and standalone Cowork-client smoke.
- Physical migrations and legacy retirement still require fingerprints, rollback packs, consumer cutover, and confirmation gates.

## Next Phase

1. Build a source-command, consumer, owner, parity, and rollback record for one
   `@公共/_runtime` or `@驾驶舱/_runtime` family at a time.
2. Add a dedicated owner job only when the owner implementation and its direct
   parity tests exist; do not relabel the generic L4 observation jobs as a
   family replacement.
3. Publish a compatibility bridge with telemetry where a live consumer still
   calls a Documents path; do not delete or switch schedules in that PR.
4. Advance the migration registry only with source and target fingerprints,
   consumer evidence, and the required confirmation gate.
5. Treat cron, LaunchAgent, Claude Scheduled, and client reload/UI changes as a
   separately confirmed physical cutover after the owner command is proven.
