# Debt reporting execution progress design

Date: 2026-06-02
Status: approved-by-default baseline (user requested continuation; user was unavailable during clarification, so this proceeds with the safest bounded follow-on after owner-presence, incorporating an explicit rubber-duck critique)
Scope: extend `report-trend` with a narrow additive `execution_progress` block anchored to the oldest selected run, using derived open-item counts from existing summary history fields, without forecasts, without slope math, without widening history schema to state-counts, and without using misleading burndown semantics

## 1. Context

The reporting stack now supports:

1. selected-run compact reporting
2. history index
3. latest-vs-prior diff with owner-level added/removed/shared semantics
4. multi-run summary trends
5. bounded trend windows by `--last <N>` and explicit run ranges
6. shared-owner-only owner trend series
7. excluded-owner `owner_presence` facts inside `report-trend`

That means the current trend packet can already answer:

1. how summary metrics evolve across a selected window
2. how stable shared owners evolve across that same selected window
3. which excluded owners appeared somewhere in the window and whether they were present at the window edges

After `owner_presence`, the next cross-run operator question is no longer “who was excluded?” but:

> are we actually reducing unfinished debt across this selected window, and relative to what baseline?

The current trend packet exposes enough raw summary fields to answer this question narrowly:

1. `total_items`
2. `executed_item_count`

From those fields, a safe derived metric already exists:

1. `open_item_count = total_items - executed_item_count`

This is the smallest usable execution-progress baseline because:

1. it is derivable from the existing history/trend contract
2. it focuses on unfinished items rather than total scope
3. it does not yet require forecasts, slopes, or time normalization
4. it avoids widening the history schema to state-counts in the same slice

## 2. Goals

This design should:

1. stay inside `report-trend`
2. remain additive to the existing trend packet
3. define a stable baseline for unfinished debt over the selected window
4. use only currently available history/trend summary fields
5. make sign direction and ratio semantics explicit
6. avoid misleading “burndown” naming before projection semantics exist

## 3. Non-goals

This design does not:

1. add date-based projection or completion forecasting
2. add slope math, normalized velocity, or per-day rates
3. widen history entries to carry state-counts
4. distinguish `pending_approval` vs `ready_to_execute` inside the new block
5. add per-owner progress baselines
6. create a new command

## 4. Approaches considered

### A. Rejected: `burndown` anchored to `total_items`

Behavior:

1. anchor on the oldest selected run’s `total_items`
2. compare later runs to that count as “remaining”

Pros:

- narrow and easy to compute

Cons:

- semantically wrong because `total_items` includes already executed items
- would call fully or partially executed debt “remaining”
- collapses scope growth and execution progress into the same misleading baseline
- creates a false “burndown” contract

This approach is rejected.

### B. Recommended: additive `execution_progress` anchored to derived `open_item_count`

Behavior:

1. derive `open_item_count = total_items - executed_item_count` for each selected run
2. anchor the block to the oldest selected run
3. expose per-run delta and ratio relative to that baseline

Pros:

- uses only current history fields
- tracks unfinished items instead of total scope
- keeps the slice narrow and auditable
- creates a stable baseline for any later projection work

Cons:

- still cannot distinguish scope growth from execution regression by itself
- requires careful naming and docs so operators do not overread the signal

### C. Wider: first widen history schema to carry state-counts, then design progress on top

Behavior:

1. extend reporting history entries with `state_counts`
2. define progress over explicit open states instead of derived counts

Pros:

- richer future modeling surface
- could later split approved-but-not-executed from pending-approval debt

Cons:

- larger schema change than needed for the next operator question
- mixes “history schema widening” with “execution progress baseline” in one slice
- introduces a new migration/test surface before the smaller baseline contract is proven useful

This approach is deferred.

## 5. Recommended design

Use **Approach B**.

The core decision is:

> extend `report-trend` with a parallel `execution_progress` block that anchors to the oldest selected run and reports unfinished-item movement using `open_item_count = total_items - executed_item_count`, while explicitly avoiding the overloaded term `burndown` and deferring all forecast semantics.

This is the smallest correct next step because:

1. it answers the next real operator question with existing data
2. it avoids the factual error of calling `total_items` “remaining”
3. it stays inside the current selected-window model
4. it leaves richer state-split progress and forecast math for later bounded slices

## 6. Architecture

### 6.1 Command boundary stays unchanged

Continue to use:

- `python3 scripts/omo_debt.py report-trend --omo-dir .omo`
- `python3 scripts/omo_debt.py report-trend --omo-dir .omo --last <N>`
- `python3 scripts/omo_debt.py report-trend --omo-dir .omo --from-run-stamp <STAMP> --to-run-stamp <STAMP>`

No new command should be introduced.

### 6.2 The new block is called `execution_progress`, not `burndown`

The new top-level additive block should be named:

1. `execution_progress`

It should **not** be named:

1. `burndown`
2. `forecast`
3. `velocity`

Reason:

1. classic burndown implies a monotonic line toward zero
2. the selected runs are not guaranteed to be evenly spaced in time
3. the line may legitimately go up when debt scope grows
4. this slice does not predict completion

The name must match what the block actually says: progress of unfinished execution relative to a baseline run.

### 6.3 `execution_progress` is anchored to the oldest selected run

The anchor should be:

1. the oldest selected run already emitted in `runs[0]`

The block should expose:

1. `anchor_run_stamp`
2. `baseline_open_item_count`

This keeps the baseline deterministic and window-relative.

### 6.4 The core derived metric is `open_item_count`

For each selected run:

1. `open_item_count = total_items - executed_item_count`

This is the narrowest safe unfinished-work metric available from the current history contract.

Important semantic note:

1. `open_item_count` counts everything not yet executed
2. it does **not** distinguish `pending_approval` from `ready_to_execute`
3. that richer split is a future schema-widening slice, not part of this one

### 6.5 Per-run fields stay baseline-relative and sign-explicit

Each `execution_progress.runs[]` entry should contain:

1. `run_stamp`
2. `open_item_count`
3. `open_item_delta_vs_baseline`
4. `open_item_ratio_vs_baseline`

Sign convention:

1. `open_item_delta_vs_baseline < 0` means fewer unfinished items than the baseline run
2. `open_item_delta_vs_baseline = 0` means unchanged unfinished-item count
3. `open_item_delta_vs_baseline > 0` means more unfinished items than the baseline run

The ratio should be:

1. `open_item_count / baseline_open_item_count`

### 6.6 Baseline zero is a first-class valid state

If the oldest selected run has:

1. `baseline_open_item_count = 0`

then the block should remain valid but shift status:

1. `progress_status = baseline_fully_executed`
2. `open_item_ratio_vs_baseline = null` for every run

This avoids divide-by-zero and makes the reason explicit.

### 6.7 `execution_progress` activates only when trend activates

Rules:

1. when `trend_status` is `insufficient_history`, `execution_progress` is `null`
2. when `trend_status` is `trend_available` and `baseline_open_item_count > 0`, `progress_status = progress_available`
3. when `trend_status` is `trend_available` and `baseline_open_item_count == 0`, `progress_status = baseline_fully_executed`

This keeps the new block aligned with the existing multi-run contract.

### 6.8 Scope growth remains visible but not separately modeled

This slice does **not** add a separate scope-growth classifier.

Instead:

1. `execution_progress` reports unfinished-item movement relative to the baseline
2. the existing summary `intervals[*].total_items_delta` remains the place to inspect scope movement between adjacent runs
3. operator docs must say that `open_item_ratio_vs_baseline > 1.0` can reflect scope growth, not just execution stagnation

This avoids duplicating summary interval data inside the new block.

### 6.9 No forecast or slope semantics in Version 1

Do **not** add:

1. `projected_zero_run`
2. `estimated_completion_date`
3. `slope`
4. `velocity`
5. `normalized_rate`

This slice is about baseline-relative unfinished work only.

## 7. Proposed YAML contract

```yaml
execution_progress:
  progress_status: progress_available
  anchor_run_stamp: 2026-05-20T00-00-00Z
  baseline_open_item_count: 10
  runs:
    - run_stamp: 2026-05-20T00-00-00Z
      open_item_count: 10
      open_item_delta_vs_baseline: 0
      open_item_ratio_vs_baseline: 1.0
    - run_stamp: 2026-06-01T00-00-00Z
      open_item_count: 9
      open_item_delta_vs_baseline: -1
      open_item_ratio_vs_baseline: 0.9
    - run_stamp: 2026-06-10T00-00-00Z
      open_item_count: 7
      open_item_delta_vs_baseline: -3
      open_item_ratio_vs_baseline: 0.7
```

Valid alternative state:

```yaml
execution_progress:
  progress_status: baseline_fully_executed
  anchor_run_stamp: 2026-05-20T00-00-00Z
  baseline_open_item_count: 0
  runs:
    - run_stamp: 2026-05-20T00-00-00Z
      open_item_count: 0
      open_item_delta_vs_baseline: 0
      open_item_ratio_vs_baseline: null
    - run_stamp: 2026-06-01T00-00-00Z
      open_item_count: 2
      open_item_delta_vs_baseline: 2
      open_item_ratio_vs_baseline: null
```

## 8. Data flow and implementation shape

### 8.1 Helper boundary

The pure trend helper should continue to own this slice.

Likely shape:

1. keep `_trend_run(...)` and `_interval(...)` unchanged
2. add one pure helper for per-run derived open-item math
3. add one pure helper that builds the `execution_progress` block from `ordered_runs`

No file I/O should be added inside the trend helper for this slice.

### 8.2 CLI behavior stays unchanged

The CLI already:

1. loads history
2. selects window/range
3. builds trend packet
4. reloads owner reporting inputs only when needed for owner blocks

`execution_progress` depends only on the already available summary trend runs, so no new CLI loader step should be required.

## 9. Testing requirements

The implementation plan must cover at least:

1. steady decrease across the selected window
2. unchanged unfinished-item count relative to baseline
3. unfinished-item increase relative to baseline
4. `baseline_open_item_count == 0`
5. `execution_progress is null` under insufficient history
6. markdown rendering of `execution_progress`
7. CLI regression showing the packet emitted by `report-trend`
8. docs regression locking naming and sign semantics

## 10. Documentation requirements

`.omo/AGENT.md` must explicitly say:

1. `execution_progress` is not a forecast
2. `open_item_count = total_items - executed_item_count`
3. negative `open_item_delta_vs_baseline` means progress
4. positive `open_item_delta_vs_baseline` can reflect either scope growth or regression/stagnation
5. `intervals[*].total_items_delta` remains the place to inspect adjacent scope movement
6. `baseline_fully_executed` is valid and keeps the ratio null instead of failing

## 11. Why this slice now

This slice is the right next step because:

1. it follows naturally from the now-complete selected-window trend contract
2. it answers a summary-level operator question without reopening owner semantics
3. it keeps the base honest by avoiding the overloaded term `burndown`
4. it creates a clean prerequisite for any later forecast/projection work

## 12. Deferred follow-ons

This design continues to defer:

1. sparse owner-gap analytics
2. owner migration semantics
3. state-split progress based on explicit `pending_approval` / `ready_to_execute`
4. slope math
5. normalized velocity
6. completion forecasting
