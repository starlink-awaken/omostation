# Debt reporting state progress design

Date: 2026-06-02
Status: approved-by-default baseline (user requested continuation; user was unavailable during clarification, so this proceeds with the safest bounded follow-on after execution-progress, incorporating an explicit rubber-duck critique)
Scope: extend `report-trend` with a narrow additive `state_progress` block that exposes selected-window `pending_approval`, `ready_to_execute`, and `executed` counts plus gate-blocking baseline deltas, using existing selected per-run reporting artifacts without widening history schema and without adding projection semantics

## 1. Context

The reporting stack now supports:

1. selected-run compact reporting
2. history index
3. latest-vs-prior diff with owner-level added/removed/shared semantics
4. multi-run summary trends
5. bounded trend windows by `--last <N>` and explicit run ranges
6. shared-owner-only owner trend series
7. excluded-owner `owner_presence`
8. summary-level `execution_progress`

That means the current trend packet can now answer:

1. how summary metrics evolve across the selected window
2. how shared owners and excluded owners behave inside the window
3. whether unfinished debt is shrinking or growing relative to the oldest selected run

What it still cannot answer is:

> when unfinished debt changes, how much of that window-relative movement is still blocked in `pending_approval` versus already in `ready_to_execute`?

This is the next narrow operator question because:

1. `execution_progress` deliberately collapses `pending_approval + ready_to_execute`
2. a rising or flat unfinished baseline is not actionable without knowing whether the bottleneck is approval or execution
3. projection / forecast would overreach before this bottleneck split is visible

Important current data fact:

1. history entries do **not** carry `state_counts`
2. selected per-run reporting artifacts already carry `summary.state_counts` with `pending_approval`, `ready_to_execute`, and `executed`
3. the CLI already loads selected reporting artifacts for owner-level trend blocks when `trend_status` is available

That makes artifact-derived state progress the smallest viable next slice.

## 2. Goals

This design should:

1. stay inside `report-trend`
2. remain additive to the existing packet
3. split selected-window progress by actionable summary state
4. keep `execution_progress` and `state_progress` anchor semantics aligned
5. avoid history schema widening in this slice
6. keep operator meaning explicit and testable

## 3. Non-goals

This design does not:

1. widen reporting history entries to include `state_counts`
2. add forecasts, slope math, normalized velocity, or completion dates
3. reopen owner-gap semantics
4. add per-owner state progress
5. create a new command
6. replace `execution_progress`

## 4. Approaches considered

### A. Recommended: additive `state_progress` derived from selected per-run reporting artifacts

Behavior:

1. keep `execution_progress` unchanged
2. add a parallel top-level `state_progress` block
3. derive `pending_approval` from artifact `summary.state_counts`
4. derive `executed` from history `executed_item_count`
5. derive `ready_to_execute = total_items - pending_approval - executed`
6. anchor baseline deltas to the oldest selected run

Pros:

- reuses data already loaded by the current CLI flow
- exposes the first actionable split beneath `execution_progress`
- avoids widening history schema
- keeps baseline semantics aligned with the selected window

Cons:

- requires careful consistency rules so state counts do not diverge from history
- introduces a second progress-oriented block alongside `execution_progress`

### B. Wider: first widen history entries to carry `state_counts`

Behavior:

1. extend `reporting/history/current.yaml` entries with `state_counts`
2. build `state_progress` purely from history thereafter

Pros:

- single data source for both progress blocks
- could support later history-only consumers

Cons:

- larger schema migration than the next operator question requires
- creates duplicated truth unless history/state generation is reworked carefully
- expands scope across refresh, history generation, docs, tests, and artifact compatibility all at once

This approach is deferred.

### C. Skip state progress and jump to forecast/projection

Pros:

- potentially more visible analytics output

Cons:

- projection remains uninterpretable if unfinished work is blocked at the approval gate
- violates the principle of landing narrower prerequisites before wider forecasting
- risks inventing completion math without enough operator-grounded primitives

This approach is rejected for now.

## 5. Recommended design

Use **Approach A**.

The core decision is:

> extend `report-trend` with a parallel `state_progress` block derived from selected per-run reporting artifacts, using the same oldest selected run anchor as `execution_progress`, so operators can tell whether unfinished debt is still blocked in `pending_approval` or already available in `ready_to_execute`.

This is the smallest correct next step because:

1. it answers the most immediate follow-on question created by `execution_progress`
2. it uses already available selected-run artifact inputs
3. it does not require a history schema migration
4. it remains focused on window-relative counts, not projection semantics

## 6. Architecture

### 6.1 Command boundary stays unchanged

Continue to use:

- `python3 scripts/omo_debt.py report-trend --omo-dir .omo`
- `python3 scripts/omo_debt.py report-trend --omo-dir .omo --last <N>`
- `python3 scripts/omo_debt.py report-trend --omo-dir .omo --from-run-stamp <STAMP> --to-run-stamp <STAMP>`

No new command should be introduced.

### 6.2 `state_progress` is parallel to `execution_progress`

The trend packet should gain a new additive top-level block:

```yaml
state_progress:
  state_progress_status: state_progress_available
  anchor_run_stamp: 2026-05-20T00-00-00Z
  baseline_pending_approval: 4
  runs:
    - run_stamp: 2026-05-20T00-00-00Z
      pending_approval: 4
      ready_to_execute: 6
      executed: 0
      pending_approval_delta_vs_baseline: 0
```

This block should stay parallel because:

1. `execution_progress` answers unfinished baseline movement
2. `state_progress` answers where that unfinished work sits in the summary workflow
3. combining both into one block would make each contract harder to reason about

### 6.3 `state_progress` depends on artifact availability

Unlike `execution_progress`, `state_progress` depends on selected per-run reporting artifacts.

Its explicit statuses should be:

1. `state_progress_available`
2. `insufficient_history`
3. `artifacts_unavailable`

Rules:

1. when `trend_status` is `insufficient_history`, `state_progress` stays `null`
2. when trend is available but `reporting_packets_by_run` was not supplied, `state_progress` stays `null`
3. when trend is available and selected artifacts exist, `state_progress_status = state_progress_available`

The YAML block should only be present when artifacts are available, but docs/tests must still make the `artifacts_unavailable` semantic explicit for the pure helper boundary.

### 6.4 Anchor semantics must match `execution_progress`

`state_progress` must anchor to:

1. `ordered_runs[0]`

And that must equal:

1. `execution_progress.anchor_run_stamp`

This keeps both progress blocks aligned to the same selected-window baseline.

### 6.5 Data-source split must be explicit

Per selected run:

1. `pending_approval` comes from artifact `summary.state_counts["pending_approval"]`
2. `executed` comes from history `executed_item_count`
3. `ready_to_execute` is derived as `total_items - pending_approval - executed`

This choice is deliberate:

1. it keeps `executed` structurally consistent with `execution_progress`
2. it avoids silently trusting two different `executed` sources
3. it makes any inconsistency between artifact state counts and summary history detectable

### 6.6 State-count consistency is a fail-closed contract

For each selected run:

1. `pending_approval + ready_to_execute + executed` must equal `total_items`

If not:

1. `report-trend` must fail closed with a `ValueError`

This matches the repo’s existing tendency to fail closed on inconsistent reporting inputs.

### 6.7 Baseline delta focuses on gate-blocking count

The key new delta is:

1. `pending_approval_delta_vs_baseline`

Sign meaning:

1. negative means fewer items are blocked at approval than at the oldest selected run
2. zero means no change in approval-gated count
3. positive means more items are blocked at approval than at baseline

This is the primary actionable signal in the new block.

### 6.8 No extra ratios or forecasts in Version 1

Do **not** add:

1. `pending_approval_ratio_vs_baseline`
2. `approval_clearance_velocity`
3. `projected_ready_to_execute`
4. `projected_completion`

The goal here is state-split visibility, not another progress math layer.

## 7. Proposed YAML contract

```yaml
state_progress:
  state_progress_status: state_progress_available
  anchor_run_stamp: 2026-05-20T00-00-00Z
  baseline_pending_approval: 4
  runs:
    - run_stamp: 2026-05-20T00-00-00Z
      pending_approval: 4
      ready_to_execute: 6
      executed: 0
      pending_approval_delta_vs_baseline: 0
    - run_stamp: 2026-06-01T00-00-00Z
      pending_approval: 2
      ready_to_execute: 6
      executed: 1
      pending_approval_delta_vs_baseline: -2
    - run_stamp: 2026-06-10T00-00-00Z
      pending_approval: 1
      ready_to_execute: 4
      executed: 3
      pending_approval_delta_vs_baseline: -3
```

## 8. Data flow and implementation shape

### 8.1 Helper boundary

This slice should stay inside the pure trend helper.

Likely shape:

1. add a helper that reads selected-run summary state counts from `reporting_packets_by_run`
2. add a helper that builds `state_progress` from `ordered_runs` plus selected reporting packets
3. continue to leave file I/O in the CLI, not inside the pure helper

### 8.2 CLI behavior stays additive

The current CLI already:

1. builds a summary-only trend packet first
2. returns early on `insufficient_history`
3. loads selected per-run reporting artifacts
4. rebuilds the final packet with artifact-backed optional blocks

`state_progress` should reuse that existing artifact pass and not introduce any new loader stage.

## 9. Testing requirements

The implementation plan must cover at least:

1. `state_progress` with decreasing `pending_approval` over the selected window
2. `state_progress` with unchanged `pending_approval`
3. `state_progress` with increasing `pending_approval`
4. `state_progress is null` under insufficient history
5. `state_progress.anchor_run_stamp == execution_progress.anchor_run_stamp`
6. per-run identity/order parity with `execution_progress.runs`
7. fail-closed mismatch when derived state counts do not sum back to `total_items`
8. markdown rendering of the new block
9. CLI regression showing `report-trend --last 2` emits `state_progress`
10. docs regression locking status names and sign semantics

## 10. Documentation requirements

`.omo/AGENT.md` must explicitly say:

1. `state_progress` is not a forecast
2. `pending_approval` comes from reporting artifact summary state counts
3. `executed` stays aligned with history `executed_item_count`
4. `ready_to_execute` is derived to keep the block internally consistent with `total_items`
5. negative `pending_approval_delta_vs_baseline` means fewer approval-blocked items than at baseline
6. `state_progress` and `execution_progress` share the same oldest selected run anchor
7. `artifacts_unavailable` is a helper-level semantic, not a silent success state

## 11. Why this slice now

This design is the right next step because:

1. it makes `execution_progress` actionable instead of merely descriptive
2. it uses already available selected-run artifact data
3. it stays smaller than history-schema widening
4. it remains a prerequisite slice before any meaningful projection work

## 12. Deferred follow-ons

This design continues to defer:

1. history schema widening for `state_counts`
2. per-owner state progress
3. sparse owner-gap analytics
4. projection and forecast semantics
5. slope math and normalized velocity
