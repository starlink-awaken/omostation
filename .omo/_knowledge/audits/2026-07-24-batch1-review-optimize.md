---
title: STRAT-P81 Batch1 code review + optimize pass
date: 2026-07-24
type: audit
pr: https://github.com/starlink-awaken/omostation/pull/483
---

# Batch1 review / optimize

## Scope

Code + tests + honesty on PR #483 delivery surface (`bin/delivery/*`, tests, closeout, planned cards).

## Findings → actions

| # | Finding | Sev | Action taken |
|---|---------|-----|--------------|
| 1 | Handshake logic duplicated in synthetic vs backlog paths | M | Extracted `_run_collab_handshake` |
| 2 | G-DEL.2b test accepted loose env / even `meets_gate` as pass | M | Assert `env_class=in-process_simulation`, physical False, `official_announce=false` |
| 3 | No negative-path tests for fail_verify / missing path | M | Added 3 tests (fail verify, inject_fail rate, missing path) |
| 4 | Path check used `is_file or exists` (dirs pass) | L | Prefer `is_file()` for remediation cards |
| 5 | schedule_harness physical always exit 0 | L | Exit **2** when physical fail-closed |
| 6 | Unused `--json` on failover_drill | L | Removed |
| 7 | closeout D1 still said delta 0 while goals=5193 | M | Reconciled closeout table |
| 8 | planned needs-human schema incomplete (CI task validate) | M | Schema-filled batch1 + p80 residual planned cards on branch |
| 9 | PR size ~500 files from task archive renames | L/ops | Document only — do not expand further |

## Verification

```
uv run --with pytest --with pyyaml python -m pytest \
  tests/test_batch1_role_framework.py tests/test_physical_suspend_reminder.py -q
# 12 passed
ruff check bin/delivery/role_framework.py ...  # clean
schedule_harness --mode physical → exit 2
```

## Residual risks (not fixed this pass)

- Main/pre-existing **ruff** noise in ecos/cockpit/scripts archive (not Batch1 code)
- **audit** workflow `Resource not accessible by integration` (permissions)
- C2 still **partial** (3-day cron wall-clock)
- Collab trail MD files are verbose protocol dumps (acceptable evidence; could later compact to index-only)
