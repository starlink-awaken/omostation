---
id: ADR-0385
title: CI Pruner + SSOT Usage — scheduled prune-ci-runs cron + SSOT freshness monitor
status: ACCEPTED
lifecycle: spec
owner: governance-team
last-reviewed: 2026-08-07
type: ssot
---

# 0385 — CI Pruner + SSOT Usage Round

> Parent: ADR-0383 (CI runs cap governance + E-5 path-filter).
> Closes M2 on the governance meta-roadmap: the cron pruner prevents
> 40000-run stalls from recurring, and the SSOT usage reporter discovers
> stale registry files.

## Context

ADR-0383 shipped the ad-hoc `prune-ci-runs.py` tool, but the 40000-run
cap requires periodic maintenance to prevent the cursor queue from stalling
again. A one-shot tool that pages through 40000 runs (slow) isn't suitable
for cron; a lightweight cron wrapper (`prune-ci-runs-cron.py`) skips the
scan and targets only the oldest runs by starting at page 300+.

Separately, ADR-0384's strategic direction included B2: SSOT usage
reporting to detect stale registry files. 34 files exist in
`.omo/_truth/registry/`; a freshness check catches files that haven't
been touched in N days — a signal for cleanup/retirement.

## Decision

### D1. A2 — `bin/ssot/prune-ci-runs-cron.py` + GitHub Actions cron workflow

Lightweight bounded pruner: starts at page 301 (oldest runs), scans
up to 500 pages, deletes completed runs, stops after 5 consecutive API
failures. No full scan, no pagination-through-all — designed for
5-15 minute cron windows.

GitHub Actions workflow `prune-ci-runs.yml`: runs weekly (Monday 05:00
UTC), workflow_dispatch for manual trigger, concurrency-cancel on
overlap, continues-on-error for the run but surfaces failures in PR
comments.

### D2. B2 — `bin/ssot/ssot-usage.py` + healthcheck integration

Reports all `.omo/_truth/registry/*.yaml` files with age. `--max-age N`
flags stale files. `--json` mode for cron/dashboard integration.
`gac-healthcheck` gains check #18 **SSOT usage**: runs ssot-usage in
JSON, reports stale count. Non-staging (healthcheck green only when
stale=0).

## Consequences

### Positive

- The 40000-run stall is now prevented proactively by a weekly cron
  (ADR-0383's tool was reactive / manual).
- Stale SSOTs are surfaced in healthcheck before they cause silent drift.
- Both tools are lightweight and fast (no full scan of 40000 runs;
  SSOT reporter is a stat(2) loop over 34 files).

### Negative / Trade-offs

- The pruner targets only the oldest tail (page 301+); recent runs are
  not prunable in a single cron cycle. Acceptable: GitHub's rolling
  window means the oldest tail moves continuously.
- `ssot-usage` reports file-modification-time, not semantic freshness
  (a SSOT might be "touched" by a CI run but not semantically updated).
  Acceptable: file-mtime is a reasonable proxy and the first useful
  signal.

## Compliance

- ADR-0384 M2 scope: A2 (cron pruner) + B2 (SSOT healthcheck).
- ADR-0203: requirement iteration; workflow run registered.
- ADR-0220 D1: claim `round-0385`.

## Verification

```bash
python3 bin/ssot/ssot-usage.py                  # 34 files, 0 stale
python3 bin/ssot/prune-ci-runs-cron.py --apply  # bounded delete ~50 pages
python3 bin/gac/gac-healthcheck.py              # 全绿 (CI平面 + SSOT usage)
make gac-local-gate                             # 41/41
```
