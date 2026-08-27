---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P56 R2: 历史能力/过程/治理/参考/愿景文档批量归档, 当前活跃文档以各面 INDEX/SSOT 为准"
---
# Debt reporting owner trend design

Date: 2026-06-02
Status: approved-by-default baseline (user requested continuation; user was unavailable during the clarifying step, so this proceeds with the recommended bounded slice)
Scope: extend `report-trend` with a narrow owner-level multi-run trend block so operators can inspect shared-owner trend series over the already-selected history window without adding a new command, without sparse owner-gap semantics, and without changing the existing summary trend contract

## 1. Context

The debt-governance reporting stack now has these layers:

1. `.omo/debt/reporting/current.yaml` plus `runs/<RUN_STAMP>/current.yaml` for selected-run compact rollups
2. `.omo/debt/reporting/history/current.yaml` for canonical run enumeration with copied summary metadata and per-run reporting refs
3. `.omo/debt/reporting/diff/current.yaml` for latest-vs-prior comparison, including owner-level shared/added/removed diffs
4. `.omo/debt/reporting/trend/current.yaml` for multi-run summary trends
5. bounded trend selection via `--last <N>` and explicit run identity ranges via `--from-run-stamp <STAMP> --to-run-stamp <STAMP>`

That means the control plane can already answer:

1. what one selected run looks like
2. what runs exist
3. how the latest run changed versus the prior run
4. how summary metrics trend over a selected multi-run window
5. how to bound that window by recency count or explicit run identity

The next missing layer is:

> operators still cannot inspect how stable owners trend over a selected multi-run window.

This slice should stay narrow because:

1. the missing question is owner-series visibility, not richer analytics
2. sparse owner-gap semantics are a wider contract than the smallest safe slice
3. burndown, slope math, velocity, and migration analytics remain higher-order follow-ons
4. `report-diff` already covers pairwise added/removed owners, so `report-trend` does not need to duplicate owner-set change semantics

## 2. Goals

This design should:

1. extend `report-trend` instead of introducing a second owner-trend command
2. keep the existing summary trend packet and CLI semantics intact
3. surface owner-level multi-run series only for owners present in every selected run
4. keep owner ordering deterministic by owner name
5. preserve current selection semantics: full history, `--last <N>`, or explicit run range
6. make empty shared-owner intersections explicit without failing the whole trend command
7. continue to avoid re-deriving historical runs from raw dispatch / approval / execution facts

## 3. Non-goals

This design does not:

1. add a new `owner-trend` command
2. add sparse gap semantics for owners that appear in only some runs
3. emit per-owner added/removed lists in trend mode
4. change summary trend metrics or top-level packet fields
5. change `report-history` ordering semantics or make history the owner truth payload
6. change `report-diff`
7. add burndown projections, slope math, or normalized velocity
8. add owner migration or rename detection

## 4. Approaches considered

### A. Recommended: extend `report-trend` with shared-owner trend blocks sourced from per-run reporting artifacts

Behavior:

1. keep `reporting/history/current.yaml` as the canonical run-selection input
2. use each selected history entry's `reporting_ref` as the pointer to the already-derived per-run reporting artifact
3. compute the shared-owner intersection across the selected runs only
4. build per-owner run series and interval deltas for that shared-owner set

Pros:

- smallest safe slice after range selection landed
- preserves the existing `report-trend` command
- keeps summary trend contract stable
- does not read raw governance facts; it only enriches from already-materialized reporting packets

Cons:

- owner detail now comes from a second artifact layer after window selection
- shared-owner intersection gets narrower as the selected window grows

### B. Wider: allow sparse owner trends for all owners that appear anywhere in the selected window

Behavior:

1. union owner names across the selected window
2. allow missing runs for some owners and render sparse gaps

Pros:

- visually richer
- avoids excluding owners that were added or removed inside the selected window

Cons:

- much wider packet semantics
- requires explicit gap/null modeling for runs and intervals
- harder for operators and downstream automation to reason about
- bigger testing surface with lower confidence for Version 1

### C. Cleaner-but-wider prerequisite: extend `report-history` to copy compact owner snapshots into every history entry, then let `report-trend` stay single-source

Pros:

- history would become a fully self-contained trend source
- trend helper would not need to open per-run reporting packets

Cons:

- wider prerequisite slice than the next missing operator need
- duplicates owner detail into history
- expands the history packet significantly before that payload is clearly needed elsewhere

## 5. Recommended design

Use **Approach A**.

The core decision is:

> extend `report-trend` with an additive `owners` block that reports shared-owner multi-run series for the already-selected window, while keeping `reporting/history/current.yaml` as the canonical selector and using each selected run's `reporting_ref` as the pointer to owner detail.

This is the smallest correct next step because:

1. run selection semantics are already stable after `--last` and explicit range support
2. per-run reporting artifacts already contain owner metrics, so no new truth surface is required
3. shared-only owner trends stay easy to explain and test
4. pairwise owner-set change semantics remain the job of `report-diff`

## 6. Architecture

### 6.1 CLI boundary stays unchanged

Continue to use:

- `python3 scripts/omo_debt.py report-trend --omo-dir .omo`
- `python3 scripts/omo_debt.py report-trend --omo-dir .omo --last <N>`
- `python3 scripts/omo_debt.py report-trend --omo-dir .omo --from-run-stamp <STAMP> --to-run-stamp <STAMP>`

No new command should be introduced.

Owner-level trend is an additive enrichment of the existing trend surface, not a separate operator workflow.

### 6.2 Summary trend remains history-driven

The current rule stays intact:

1. `report-trend` uses `reporting/history/current.yaml` to choose which runs participate
2. summary `runs[]` and `intervals[]` continue to come directly from the copied summary metadata in history
3. ordering remains oldest-to-newest after window selection

This slice does **not** move summary trend back toward raw dispatch facts.

### 6.3 Owner detail is loaded from each selected run's `reporting_ref`

Owner metrics do not live inside the current history entries. Therefore the owner enrichment path should:

1. select runs via the existing history-driven logic
2. for each selected run, require `reporting_ref` to be present
3. load the referenced per-run reporting artifact
4. read its `owners[]` block as the source of owner-level metrics

This remains compatible with the current trust model because those per-run reporting packets are already-derived reporting artifacts, not raw dispatch/approval/execution facts.

### 6.4 Shared-owner intersection is relative to the selected window

This is the critical correctness rule.

The shared-owner set must be computed over the **selected runs only**:

1. full visible history when no selection flags are provided
2. the newest-N window when `--last <N>` is used
3. the inclusive selected range when explicit run bounds are used

An owner appears in the owner trend block only if that owner is present in every selected run's `owners[]`.

This means a wider window may produce fewer shared owners than a narrower one. That is an intentional Version 1 trade-off and must be documented.

### 6.5 Owner metric set is fixed and owner-scoped

Owner trends use the same conceptual metric family as summary trend, but with owner-scoped field names:

1. `item_count`
2. `executed_item_count`
3. `approval_coverage_rate`
4. `execution_completion_rate`

Important:

1. owner trend must **not** try to read `total_items` from owner entries
2. summary trend continues to use `total_items`
3. owner trend is additive; it does not change summary metric names

### 6.6 Owner block states are explicit

Top-level `trend_status` keeps its existing meanings:

1. `insufficient_history` when fewer than two runs are selected
2. `trend_available` when at least two runs are selected

Owner behavior:

1. when `trend_status` is `insufficient_history`, `owners` is `null`
2. when `trend_status` is `trend_available` and at least one shared owner exists, `owners.owners_trend_status` is `owners_trend_available`
3. when `trend_status` is `trend_available` but the selected window has no shared owners, `owners.owners_trend_status` is `no_shared_owners`

The command should not fail just because the shared-owner intersection is empty.

### 6.7 Owner packet shape stays compact and parallel

Add an optional `owners` block to the trend packet:

```yaml
owners:
  owners_trend_status: owners_trend_available
  shared_owner_count: 2
  owners_excluded_count: 1
  compared:
    - owner: commerce-governance
      runs:
        - run_stamp: 2026-05-20T00-00-00Z
          item_count: 1
          executed_item_count: 0
          approval_coverage_rate: 0.0
          execution_completion_rate: 0.0
        - run_stamp: 2026-06-01T00-00-00Z
          item_count: 2
          executed_item_count: 0
          approval_coverage_rate: 1.0
          execution_completion_rate: 0.0
      intervals:
        - from_run_stamp: 2026-05-20T00-00-00Z
          to_run_stamp: 2026-06-01T00-00-00Z
          item_count_delta: 1
          executed_item_count_delta: 0
          approval_coverage_rate_delta: 1.0
          execution_completion_rate_delta: 0.0
```

Rules:

1. `compared` is sorted by owner name
2. each owner entry's `runs[]` order must match the selected oldest-to-newest trend order
3. each owner entry's `intervals[]` order must match the top-level interval order
4. `owners_excluded_count` reports owners present somewhere in the selected window but not in every selected run
5. names for excluded owners stay deferred; Version 1 only exposes the count

### 6.8 Missing owner detail still fails closed when it matters

Owner enrichment should preserve the current trust posture.

Required rules:

1. every selected run must still satisfy the existing summary-metadata validation
2. when owner enrichment is attempted, every selected run must have a loadable `reporting_ref`
3. every shared owner entry must have non-null values for `item_count`, `executed_item_count`, `approval_coverage_rate`, and `execution_completion_rate`
4. if a selected run's referenced reporting artifact is missing or malformed, `report-trend` must fail closed with a clear error

This keeps the additive owner block trustworthy rather than silently partial.

### 6.9 `report-diff` remains untouched

Pairwise owner-set change semantics still belong to `report-diff`.

Do not:

1. add `owners.added` / `owners.removed` to trend mode
2. add owner-migration inference to trend mode
3. change diff packet fields or diff docs in this slice

## 7. Data flow

For:

- `python3 scripts/omo_debt.py report-trend --omo-dir .omo --last 3`

the command should:

1. load `reporting/history/current.yaml`
2. apply existing window/range selection rules
3. build summary `runs[]` and `intervals[]` as today
4. if at least two runs are selected, load each selected run's `reporting_ref`
5. compute the shared-owner intersection across those selected run packets
6. build owner `compared[]` entries in owner-name order
7. compute owner intervals from adjacent oldest-to-newest runs
8. write `.omo/debt/reporting/trend/current.yaml` and `.md`

## 8. Error handling

The command should fail closed when:

1. a selected history run lacks valid summary trend metadata
2. a selected run's `reporting_ref` is missing when owner enrichment is needed
3. the referenced per-run reporting artifact cannot be loaded
4. a shared owner entry is missing any required owner metric field

The command should **not** fail when:

1. fewer than two runs are selected; that remains `insufficient_history`
2. the shared-owner intersection is empty; that remains a valid `no_shared_owners` owner state

## 9. Testing strategy

Write tests in this order:

1. helper RED: two runs with two shared owners -> owner block appears with deterministic owner ordering and correct owner-scoped deltas
2. helper RED: owner present only in the selected window should appear when `--last` or range narrows away older conflicting runs
3. helper RED: no shared owners across the selected window -> `owners_trend_status: no_shared_owners`, no failure
4. helper RED: `insufficient_history` -> `owners` remains `null`
5. helper RED: missing/malformed per-run reporting artifact -> fail closed
6. CLI RED: `report-trend` still accepts existing selection modes and writes owner block into live artifacts
7. docs RED: `.omo/AGENT.md` must explain shared-only owner trend semantics, window-relative intersection, and the continued deferral of sparse owner-gap semantics

## 10. Success criteria

This slice is complete when:

1. `report-trend` continues to pass all existing summary trend tests unchanged
2. `report-trend` emits a deterministic additive `owners` block for shared owners when `trend_status: trend_available`
3. selected-window semantics are preserved across full history, `--last <N>`, and explicit run ranges
4. empty shared-owner intersections produce a valid packet state instead of a command failure
5. docs and live artifacts reflect the new owner trend surface
6. canonical `.omo` verification remains green
