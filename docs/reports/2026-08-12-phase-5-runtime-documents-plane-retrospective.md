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

- No production Documents jobs are registered yet; Tasks 7–9 add owners only after parity and consumer evidence.
- Non-macOS execution stays unavailable until an equally strong write sandbox is implemented.
- Fresh work-root retention needs an explicit Runtime-owned cleanup/retention policy after operational volume is measured.
- The 12 domain gateways still need their separately confirmed batch update and standalone Cowork-client smoke.
- Physical migrations and legacy retirement still require fingerprints, rollback packs, consumer cutover, and confirmation gates.

## Next Phase

1. Freeze infrastructure hardening and deliver the three-domain MVP first.
2. Under an exact three-domain write confirmation, update only `vault`, `work-weijian`, and `creative` gateways.
3. Register one low-risk read-only owner job and smoke the standalone Claude/Codex/Zed project flow.
4. After MVP acceptance, register and cut over the public/cockpit Runtime families and expand to 12/12 domains.
5. Advance migration registry states only when owner parity and rollback evidence are present.
