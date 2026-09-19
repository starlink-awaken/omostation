---
schema_version: governance-waiver/v1
status: active
lifecycle: history
type: governance-process-waiver
owner: governance-team
created: 2026-09-19
last-reviewed: 2026-09-19
---

# Waiver — scheduler-compile plane filter unbound start

- Timestamp (UTC): 2026-09-19T09:05:30Z
- Actor: governance-agent (clone fix-scheduler-compile-planes-20260919-s4)
- Run: 20260919T090530Z-project-code-change-0dc06004

## Scope

`AGCP_REQUIREMENT_ITERATION_GATE=0` was used only as the process-level
prefix for this single unbound `project-code-change` workflow start, under
the operator's standing directive to keep resolving temporary issues
without per-step re-authorization (MVP mode). All later gates (claim,
verify, compliance, Git hooks, CI) use default strictness.

## Change

- `bin/scheduler-compile.py`: `compile_crontab` now filters to
  `status=active` jobs whose `planes` contain `crontab`, matching the
  registry-side filter in `check_drift`. This prevents launchd-only
  entries from leaking into `--generate crontab` output, which cron
  rejects as an invalid schedule.
- `tests/test_scheduler_compile.py`: adds contract tests for the plane
  filter and 5-field schedule validation.

## Provenance (successor chain)

- Original proposal: commit `d6287e213e29271914f9ef985132d39c3634a027`
  (worktree `fix-scheduler-compile-planes-20260919`, base `a79ab630c`).
- Successor s2: commit `e57e814dea0e8aefbcc52f3c74951ebcb47edb8e` on base
  `44bab9f3df4715ad86392cfe9720868f6ffe6887`; blocked closeout recorded
  (claims-authority hard-pin, awaiting operation-specific publish approval).
- Successor s3: commit `df03038f7c5d7e7a8afd200671556ddf4d7299ff` on base
  `9ee8d172efb35bd2cbac2f6f2184deaba3c9a992`; superseded after #4020/#4022
  landed. s2 preserved as evidence.
- Successor s4 (this clone): replayed verbatim via `git apply` onto base
  `a9e93dc29eb4414aba8e77bb7f02addd4ad38cf5` (remote main at creation).
  NOTE: concurrent merges may advance main again; if origin/main differs
  at approval time, a fresh same-scope successor is created before publish.

## Verification

- `uv run --with pytest --with pyyaml python -m pytest tests/test_scheduler_compile.py -q`
  → 7 passed on this base.
- Scoped GaC gate on both claimed code paths → ok, 0 blocking findings.

## Rollback

Single commit revert of both files restores prior behavior; no runtime,
registry, CI, or branch-protection state is touched.
