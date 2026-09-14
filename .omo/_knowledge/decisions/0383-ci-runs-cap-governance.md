---
id: ADR-0383
title: CI runs cap governance + E-5 path-filter SSOT completion
status: ACCEPTED
lifecycle: spec
owner: governance-team
last-reviewed: 2026-08-06
type: ssot
---

# 0383 — CI Runs Cap Governance + E-5 Completion Round

> Parent: ADR-0379..0382 (CI plane family).
> Addresses the recurring GitHub cursor-queue stall (repo pinned at the
> 40000-run retention cap) with a maintenance tool, and completes the
> E-5 path-filter SSOT (observability → value-driven scope parity).

## Context

Since ADR-0379, every PR round hit the same wall: the repo's Actions
run history is pinned at the 40000-run cap, GitHub's check-suite
computation ("cursor" queue) intermittently stalls forever on new head
commits, and the only workaround was rebuilding the PR from a fresh
branch (done 3 times). Root cause: run volume (20+ concurrent agents ×
45 checks) exceeds GitHub's retention window, and the capped repo
degrades suite scheduling.

Second: E-5 (path-filter SSOT) from ADR-0380's next_step was only
partially landed in ADR-0381 (triggers observable, path values not).

## Decision

### D1. `bin/ssot/prune-ci-runs.py` — CI run retention maintenance

Local maintenance tool that deletes old completed workflow runs via
`gh api` (GITHUB_TOKEN cannot delete runs; user-level token required):

- `--before <YYYY-MM-DD>` / `--keep <N>` selection, `--dry-run` default,
  `--apply` to delete, 3x retry on transient API errors, `created<`
  API-side filtering so deletion targets the old tail without paging
  the whole history.
- Purpose: keep the repo comfortably under the 40000-run cap so the
  cursor check-suite queue stops stalling. Documented as a periodic
  maintenance step (weekly, or whenever `cursor [queued]` stalls recur).

Maintenance run executed this round: background deletion of completed
runs before 2026-07-01 (targeting the oldest ~10K runs).

### D2. E-5 completion — path-filter values in the registry

`ci-surfaces.yaml::workflow_triggers` entries for path-filtered
workflows (ci-lint, governance-check, meta-model-check,
omostation-governance, publish-pypi) now carry the concrete `paths:`
list. `check_workflow_trigger_drift` compares workflow YAML paths vs
registry paths (set equality) → `trigger-drift` warn on mismatch.
+2 tests (drift detected / clean match).

## Consequences

### Positive

- The 40000-run stall now has a maintenance remedy instead of the
  "rebuild PR on a new branch" hack; the tool is committed and
  documented so any operator can run it.
- E-5's path values are machine-readable: a future local-gate scope
  computation can consume them directly (the observability half of the
  original E-5 goal is complete).
- Detector: 0 errors, 4 defense-in-depth overlap warns.

### Negative / Trade-offs

- Deleting runs removes CI history/artifacts (retention-limited
  anyway at 40K). Deletion is gated behind `--apply`.
- Full E-5 value-driven scope parity (local gate consuming paths to
  compute its own scope) remains future work; this round makes the
  data available.
- Cleanup speed: ~1 API call per run → a 10K-run sweep takes hours;
  acceptable for a periodic maintenance task.

## Compliance

- ADR-0379/0380/0381: completes the CI-plane initiative (E-5 half).
- ADR-0203: requirement iteration; workflow run registered with path
  coverage.
- ADR-0220 D1: claim `round-0383` (deleted after merge).

## Verification

```bash
python3 bin/ssot/prune-ci-runs.py --before 2026-07-01 --dry-run
#   DRY-RUN 模式; total scanned / kept / deleted 统计
python3 bin/gac/check-ci-surfaces.py --json   # ok, 0 errors
python3 -m pytest tests/test_ci_surfaces.py -q  # 11 passed
python3 bin/gac/gac-healthcheck.py            # 全绿
```
