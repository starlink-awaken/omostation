---
schema_version: report/v1
lifecycle: history
type: implementation-evidence
owner: runtime-team
created: 2026-08-30
last_updated: 2026-08-30
bet_id: BET-Y1Q3-T10-99
---

# Learning runtime owner parity — implementation evidence

## Scope

This slice establishes Workspace Runtime ownership for the two read-only
semantics of the legacy
`Documents/@学习进化/_control/scripts/knowledge-decay.sh` command:
`scan` and `ls-orphan`. It does not mutate Documents, install a schedule, or
move the remaining learning control-plane scripts.

## Owner contract

The canonical entry is:

```text
runtime documents run documents-learning-decay --json
runtime documents run documents-learning-orphans --json
```

Both jobs are declared in the Workspace binding registry with owner
`runtime-learning`, a single read scope of
`@学习进化/_knowledge/50-concepts`, `writes: []`, a manual schedule, and
fail-closed evidence schema `runtime.documents-learning-decay.v1`.
Runtime persists only aggregate evidence under its state root; concept names,
titles, source text, and absolute Documents paths are not emitted in the
owner evidence.

## Verification

- RED: before the owner module existed, the new behavior suite failed during
  collection with `ModuleNotFoundError`.
- GREEN: the focused Runtime suite passed with 57 tests; Ruff check and format
  check passed for all changed Runtime files.
- The real Documents concept root was inspected read-only on 2026-08-30 with
  `scan`: 74 concept files, 27 referenced, 47 orphan, 0 decay candidates,
  staleness buckets fresh=1, normal=1, aging=72, stale=0, decayed=0,
  uncommitted=0. The truthful status was `attention` because orphan concepts
  exist.
- The installed `runtime documents` entrypoint executed both registered jobs
  against the real concept root. Each produced a Runtime-only receipt with
  `evidence_error: null`; each returned owner exit code 1 and status
  `attention`, preserving the health finding rather than masking it as success.
- Dry-run executed without starting an owner or creating Runtime state.
- A malformed owner payload was rejected with exit code 74 and no accepted
  evidence projection.

## Mainline closure

The Runtime child PR #69 merged to child main as
`6a156a2d1621b295294341ebef0be4f33e9b6ad8`. Root PR #2685 merged to root main
as `454679dc2d7449b9c4c9029d3e00c92f52016e97`; the root gitlink was verified
against that child mainline commit. Root required checks were all successful,
including the long-running `governance-verify`. The implementation was
delivered as three root lane-separated commits because the repository gate
forbids mixing `governance_state` with docs or submodule-pointer changes.

## Boundary and residual

The migration family remains `learning-runtime: in_progress` with
`owner_parity: partial`: read-only parity is proven, while the following
legacy semantics still require separate governed work:

- `mark-stale` and any other Documents-writing operation;
- `l4-kernel.sh` and `vault-healthcheck.sh` control-plane behavior;
- daemon/executor wrappers, `.githooks/pre-commit-g18`, and
  `_inbox/inbox-router.sh`.

No host launchd/cron/client configuration was changed by this implementation.
