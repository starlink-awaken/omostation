---
status: ACCEPTED
lifecycle: decision
owner: governance-team
last-reviewed: 2026-07-15
---

# ADR-0204 — ADR-0203 可执行闸门 + pre-push 路径 + worktree/ADR 占号

- **Status**: ACCEPTED
- **Date**: 2026-07-15
- **Owner**: governance-team

## Context

ADR-0203 made requirement iterations **normatively** mandatory. Follow-up needed:

1. Executable signal when agents stage delivery files without an active workflow run.
2. pre-push still pointed at pre-rationalization `bin/sync-submodules-push.sh`.
3. worktree claim only inited ecos+scripts → agent-workflow/doctor often broken.
4. Concurrent ADR numbers still collide (0195 lesson).

## Decision

### D1 — Staged-only hard gate

`omo.workflow.diagnostics.requirement_iteration_report`:

| Signal | Severity (`mode: required`) |
|--------|-----------------------------|
| Staged in-scope paths, **no** active run | **halt** (compliance exit 1) |
| Unstaged in-scope dirty, no active run | **warn** only |
| Active run present | pass |
| `AGCP_REQUIREMENT_ITERATION_GATE=0` | bypass |

Rationale: shared multi-agent worktrees often have unstaged noise; staged ≈ “about to commit”.

Wired into `compliance_report` + `status`. Path lists SSOT in
`requirement_iteration_policy.in_scope_paths` / `exclude_paths`.

### D2 — pre-push SSOT paths

`.githooks/pre-push` calls `bin/ssot/sync-submodules-push.sh` and
`bin/ssot/submodule-reachability-gate.py`, with fallback to `bin/` wrappers.
Compatibility wrappers restored under `bin/` for old docs/scripts.
Operators must re-run `make install-hooks` after pull.

### D3 — worktree default submodule set

`gac-worktree.sh claim` default init:

`projects/ecos scripts projects/omo projects/cockpit projects/agora`

### D4 — ADR number hint/claim

`bin/adr/next-adr-id.py` prints next free `ADR-NNNN` from `decisions/`.
Optional `--session X --claim` writes short-lived
`.omo/_delivery/adr-claims/<session>.json`. claim worktree prints the hint.

## Non-goals

- Blocking on unstaged dirty alone
- CI always-fail when runner has no staged files (clean tree stays green)
- Distributed ADR locks across machines (file claim is best-effort)

## Verification

```bash
# with active run (this PR):
uv run --with pyyaml python bin/agent-workflow.py compliance --json | jq .requirement_iteration

# pre-push paths
test -f bin/ssot/sync-submodules-push.sh
test -x bin/sync-submodules-push.sh
grep -n 'bin/ssot/sync-submodules-push' .githooks/pre-push

python3 bin/adr/next-adr-id.py --json
```

## References

- ADR-0203 requirement iteration mandatory
- pattern: pre-push-ssot-path-drift, adr-concurrent-number-collision
