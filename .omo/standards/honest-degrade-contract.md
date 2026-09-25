---
schema: md/v1
status: active
lifecycle: history
owner: governance-team
last-reviewed: 2026-09-25
type: ssot
schema_version: standard/v1
standard: honest-degrade-contract
created: 2026-09-18
---


# Honest-Degrade Contract

## Problem

When a dependency is unavailable, slow, or partially working, the easy lie is
to report **pass** and let downstream consumers act on unproven state. Three
isomorphic instances of the honest alternative already exist in this repo with
no shared contract doc; this file is that contract.

## Tri-state

Every readiness / health / gate signal MUST resolve to exactly one of:

| State | Meaning | Downstream effect |
| ----- | ------- | ----------------- |
| `pass` | All required checks verified | Consumer may proceed |
| `degraded` | Partial function; what is missing is named | Consumer may proceed **only** on paths that do not need the missing part |
| `fail-closed` | Required state cannot be proven | Consumer MUST refuse; no silent fallback to pass |

There is no fourth state. "Unknown", "skipped", and "timeout" MUST map to one
of the three (timeouts and unprovable states are `fail-closed`, never `pass`).

## Stable-reason naming rules

Degraded and fail-closed signals MUST carry a machine-stable reason string:

1. `snake_case`, ASCII, no spaces (e.g. `git_timeout`, `readiness_generated`).
2. Stable across refactors: renaming a reason is a breaking change for
   consumers that match on it; add a new reason instead.
3. Carries `detail` (human-readable, bounded length) alongside `reason`
   (machine-readable). Never put the machine signal only in free text.
4. Timeouts surface as named reasons, never as uncaught exceptions that a
   caller could misread as success.

## Prohibition on faking pass

1. A degraded check MUST appear in the explicit degraded list; a required
   check whose status is not `pass` MUST flip the aggregate away from `pass`.
2. Best-effort recovery steps (reinstalls, retries, cache fallbacks) MUST NOT
   flip a failed required check back to `pass`; record their own status
   separately.
3. Zero-result / empty answers from an index or lookup MUST be treated as
   unproven (`fail-closed` or named `degraded`), never as confirmation.
4. Fetch / network fallbacks MUST record which path was taken; a fallback that
   was not reached is `fail-closed`, not success-by-default.
5. Cancelled or never-run CI is not evidence of health; see #3950 precedent.

## Conforming examples

- `bin/gac/agent-clone.py`: readiness receipt aggregates per-check
  `pass`/`degraded` into `ready`/`degraded` with an explicit `degraded_checks`
  list; `ToolError` carries stable `reason` strings (e.g. `git_timeout`,
  `git_unavailable`) with bounded `detail`.
- Claim fetch fallback paths: fetch failures record the attempted path and
  refuse rather than declaring success on an unfetched base.
- Tool-index circuit-breaker: a 0-result lookup refuses instead of confirming.
- #3711 (T10-166) ASD panels data contract: panels carry
  provenance / freshness / degradation fields.
- #3950 cancelled-CI honesty: cancelled runs are excluded from failure counts,
  never counted as passes.
