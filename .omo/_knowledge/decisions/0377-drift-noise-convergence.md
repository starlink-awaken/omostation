---
id: ADR-0377
title: Drift-noise convergence — runtime-derived plane exclusion + release_ready semantics
status: ACCEPTED
lifecycle: spec
owner: governance-team
last_updated: 2026-08-05
---

# 0377 — Drift-Noise Convergence Round

> Parent: ADR-0106 (GaC), ADR-0376 (M1 tracked-truth).
> This round removes the last yellow from `gac-healthcheck` — the
> `gac-drift` GRAY noise from runtime-derived targets — and fixes two
> pre-existing `test_governance_evolution.py` failures (one tool
> semantics bug, one environment-dependent test).

## Context

After ADR-0376 (M1 117/0/0/0), `gac-healthcheck` still showed one
yellow: **`gac-drift: ⚠️ drift_count=2`**, both GRAY:

| Rule | target | check_type |
|------|--------|-----------|
| CR-M4-HEALTH-SCORE | `projects/ecos/.omo/_derived/m4-health.json` | freshness |
| CR-M4-DERIVED-PLANE-AUDIT | `projects/ecos/.omo/_derived/` | ssot_pointer |

The targets live in the **runtime-derived plane** (`_derived/`,
gitignored in `projects/ecos/.gitignore:73`). Those files exist only
after the local generation step (`m4-health-score.py --emit` /
radar_cron). Every fresh checkout, worktree, or CI run reports
`target 文件不存在` — a permanent false GRAY that desensitizes the
drift signal.

Separately, `tests/test_governance_evolution.py` had 2 pre-existing
failures in a clean tree (handoff-documented):

1. `packages_rejects_invalid_decision_file` — an invalid decision
   record yields `ok=False` but **`release_ready=True`**: 
   `release_ready = not review_findings or decision_summary["ready"]`
   short-circuits to True when `review_findings` is empty, swallowing
   the invalid count. The decision state is corrupt, so release must
   NOT be ready.
2. `packages_require_ready_blocks_pending_decisions` — asserted live
   `git status` contains review-required pending paths. In a clean
   repo `review_findings` is empty → exit 0 is correct; the test only
   passed by accident when the workspace was perpetually dirty. An
   environment-dependent test.

## Decision

### D1. G11 — Exclude the runtime-derived plane from static target checks

`bin/gac/gac-drift.py`:

- `EXCLUDE_DIRS` gains `_derived` (runtime-derived plane; the set is
  documented "hardcode 合法, 非活文档").
- `check_target_exists` short-circuits via `_is_excluded(fpath)`
  before the `exists()` probe, so any rule whose target is a
  gitignored runtime product no longer emits static drift.

`drift_count` 2 → 0; `gac-healthcheck` 机制4 line turns fully green.
The derived-plane freshness (CR-M4-HEALTH-SCORE) remains enforced at
runtime by `m4-health-score.py` / radar_cron, which is the correct
layer for it.

### D2. G12 — `release_ready` must be False on invalid decision data

`bin/gac/governance-evolution.py::build_package_report`:

```python
release_ready = decision_summary["invalid"] == 0 and (
    not review_findings or decision_summary["ready"]
)
```

Invalid records mean the decision state cannot be trusted; they are
already reflected in `report_ok` and `decision_summary.invalid`, and
now in `release_ready` / `release_gate` too.

### D3 — Deterministic pending-decisions test

`test_governance_evolution_packages_require_ready_blocks_pending_decisions`
rewritten to inject `git_status_lines` on the module
(`importlib` + monkeypatch) with a crafted
`?? .omo/tasks/planned/fake-review.yaml` (→ `governance-task-lifecycle`,
a `RELEASE_REVIEW_PACKAGES` member), then assert
`build_package_report(require_ready=True)` blocks. No longer depends
on live repo state.

### D4 — Regression tests for the exclusion

`tests/test_gac_drift_indexed_rule.py` +3:
- `_derived` file target → no drift (CR-M4-HEALTH-SCORE)
- `_derived/` dir target → no drift (CR-M4-DERIVED-PLANE-AUDIT)
- non-derived missing target still flags (exclusion does not weaken
  the main path)

## Consequences

### Positive

- **Last yellow removed**: `gac-healthcheck` is 100% green with zero
  warnings across all 16 checks.
- **Invalid decisions now honestly block release readiness** — the
  gate semantics match `decision_summary.invalid` and `report_ok`.
- Test suite deterministic: both previously-failing tests pass in a
  clean tree and in CI.
- `EXCLUDE_DIRS` covers the full fresh-worktree missing-target set
  (verified: only the 2 M4 targets were missing, both under
  `_derived/`).

### Negative / Trade-offs

- `_derived` is a hardcoded exclusion like the rest of `EXCLUDE_DIRS`;
  a future runtime-derived plane under a different name would need the
  same treatment. Accepted: the set is small, documented, and
  architecture-stable.
- The G12 semantics change tightens release gate behavior: any
  deployment pipeline that previously proceeded despite invalid
  decision records will now be blocked until the records are fixed.
  That is the intended safety behavior.

## Compliance

- ADR-0106: static drift checks now match "non-derived, live-plane"
  semantics; runtime checks own the derived plane.
- ADR-0376: extends the tracked/runtime-plane truth principle from M1
  to target-exists checks.
- ADR-0203: requirement iteration; workflow run registered with path
  coverage.
- ADR-0220 D1: claim `round-0377` (deleted after merge).

## Verification

```bash
# D1 — drift 归零
python3 bin/gac/gac-drift.py --json
#   {"drift_count": 0, "red_drifts": [], "gray_drifts": []}

# D2 — invalid decision → not release-ready
python3 bin/gac/governance-evolution.py packages \
  --decisions <invalid-file> --json
#   {"ok": false, "release_ready": false, ...}

# D1/D2/D3/D4 — tests
python3 -m pytest tests/test_gac_drift_indexed_rule.py \
  tests/test_governance_evolution.py -q
#   25 passed

# 全量健康
python3 bin/gac/gac-healthcheck.py
#   16/16 ✅, 无 ⚠️
```
