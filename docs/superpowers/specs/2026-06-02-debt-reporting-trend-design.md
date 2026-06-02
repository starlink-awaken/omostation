# Debt reporting trend design

Date: 2026-06-02
Status: approved-by-default baseline (user requested continuation; user was unavailable during design approval, so this proceeds with the recommended bounded slice after the owner-level diff layer landed)
Scope: add a narrow multi-run debt reporting trend surface that summarizes ordered run-to-run progress across the existing reporting history index, without yet adding owner-level trends, slope math, projections, or richer owner-set migration analytics

## 1. Context

The debt-governance reporting stack now has these layers:

1. `.omo/debt/reporting/current.yaml` plus `runs/<RUN_STAMP>/current.yaml` for latest-run compact rollups
2. `.omo/debt/reporting/history/current.yaml` for canonical run enumeration with latest/prior resolution and copied run summary metadata
3. `.omo/debt/reporting/diff/current.yaml` for latest-vs-prior summary and owner-level diff

That means the control plane can already answer:

1. what one selected run looks like
2. what runs exist
3. how the latest run changed versus the immediately prior run

The next missing layer is:

> operators can compare two runs, but there is still no explicit surface that shows how debt governance is progressing across multiple runs over time.

This needs to stay narrow for four reasons:

1. the reporting stack already has the right single-run, history, and latest-vs-prior layers, so the next step is an ordered multi-run surface rather than another pairwise diff variant
2. the live repo still has only one checked-in run, so the first trend surface must treat insufficient history as a valid packet state
3. the trend slice should reuse existing per-run summary metadata instead of re-deriving an expanding number of historical runs from raw facts every time
4. owner-level trends, projections, and slope math all introduce wider semantics than the first useful multi-run progress view

## 2. Goals

This design should:

1. add one explicit trend command and generated surface
2. expose multi-run progress from oldest to newest rather than newest to oldest
3. read trend inputs from the canonical reporting history index
4. keep the metric set intentionally small and management-facing
5. write a valid packet when there are fewer than two runs
6. keep owner-level trends and richer analytics explicitly deferred

## 3. Non-goals

This design does not:

1. add owner-level trends across multiple runs
2. add slope math, per-day normalization, projections, or forecasts
3. re-derive every historical run from dispatch, approval, and execution facts at trend-generation time
4. add explicit run-window override flags in Version 1
5. rename or replace the existing `report-history` or `report-diff` surfaces
6. promote new trend pointers into `state/system.yaml`

## 4. Approaches considered

### A. Recommended: `report-trend` from history summary metadata

Add one explicit `report-trend` command that reads the canonical run list and copied summary fields from `reporting/history/current.yaml`, reorders runs oldest-to-newest, and emits one compact trend packet with ordered runs plus interval deltas for a small fixed metric set.

Pros:

- builds directly on the completed history index instead of inventing another source
- keeps multi-run cost stable as run count grows
- preserves the explicit-command / explicit-surface pattern already used by `report`, `report-history`, and `report-diff`
- gives management-facing progress visibility without owner-trend overreach

Cons:

- formally upgrades some history metadata from “index convenience” to canonical trend input for this slice
- adds one more reporting surface

### B. Narrower: `report-burndown` only

Add a surface focused only on backlog reduction / completion semantics, likely centered on `total_items`, `executed_item_count`, and completion rates.

Pros:

- very small
- easy to explain as a progress signal

Cons:

- “burndown” is too narrow for approval coverage and execution completion progression
- naming would mislead operators into thinking the surface is only about backlog burn
- likely leads to a second near-duplicate trend surface later

### C. Wider: multi-run trend plus owner trends now

Add top-level trend analytics and owner-level run series in the same increment.

Pros:

- most complete management surface immediately
- might reduce later follow-up work

Cons:

- far too wide for the first multi-run slice
- owner trend semantics require stable multi-run membership interpretation that has not yet been designed
- greatly increases packet and test complexity while the live repo still has only one run

## 5. Recommended design

Use **Approach A**.

The core decision is:

> add a dedicated `report-trend` surface under `reporting/trend/current.*` that reads a bounded metric set from `reporting/history/current.yaml`, orders runs oldest-to-newest, emits consecutive interval deltas, and treats insufficient history as a valid packet state without yet adding owner trends or slope math.

This sequencing is correct because:

1. the stack already has single-run, history, and pairwise comparison layers
2. trend is the next missing management-facing question after pairwise diff
3. the history index already copies the four metrics needed for a small, stable trend surface
4. deferring slopes and owner trends keeps the slice small enough to validate cleanly with synthetic fixtures

## 6. Architecture

### 6.1 Explicit command boundary

Add:

- `python3 scripts/omo_debt.py report-trend --omo-dir .omo`

Behavior:

1. load `.omo/debt/reporting/history/current.yaml`
2. select the ordered run window from that packet
3. reorder runs from oldest to newest
4. compute consecutive interval deltas from those already-published run summaries
5. write one trend packet plus Markdown summary

This keeps trend generation explicit and operator-invoked, consistent with the rest of the reporting stack.

### 6.2 History is the canonical trend input for Version 1

Version 1 trend should read from the reporting history packet rather than re-deriving all historical runs from raw facts.

Required rule:

1. `report-history` remains the producer of the canonical ordered run inventory
2. `report-trend` consumes the copied run summary fields already present in `history.current.yaml`
3. `report-trend` does **not** re-open dispatch, approval, and execution evidence for every historical run

This intentionally refines the earlier history-layer caution: those copied fields remain “index metadata” for the history surface itself, but they become the canonical trend input for this narrow multi-run analytics slice.

Reason:

1. the metric set is already small and explicitly copied into history
2. trend cost should not grow into N-run full fact re-derivation
3. historical trend stability should not depend on all underlying raw evidence remaining available forever

### 6.3 Distinct generated surfaces

Trend outputs should be generated under:

1. `.omo/debt/reporting/trend/current.yaml`
2. `.omo/debt/reporting/trend/current.md`

Design intent:

1. `reporting/current.*` remains one selected run
2. `reporting/history/current.*` remains run enumeration plus copied per-run summary metadata
3. `reporting/diff/current.*` remains latest-vs-prior comparison
4. `reporting/trend/current.*` becomes the ordered multi-run progress surface

### 6.4 Valid insufficient-history packet

If the history surface contains fewer than two runs, `report-trend` should still write a valid packet.

That packet should:

1. set `trend_status: insufficient_history`
2. include any known runs in oldest-to-newest order
3. keep `intervals: []`
4. render Markdown that clearly says the trend baseline is not yet established

This keeps the command pipeline-safe before the repo accumulates enough live runs.

### 6.5 Oldest-to-newest ordering

The history index orders runs newest-to-oldest, which is correct for discovery but wrong for trend reading.

Trend must therefore:

1. read from history
2. invert the run order
3. emit `runs[]` oldest-to-newest
4. emit `intervals[]` oldest-to-newest

This makes interval deltas intuitive: later progress appears as the delta from one older run to the next newer run.

### 6.6 Missing reporting metadata fails closed

Trend must not silently skip runs whose reporting metadata is incomplete.

Required rule:

1. every run used by `report-trend` must have `reporting_exists: true`
2. every run used by `report-trend` must have non-null values for the four Version 1 trend metrics
3. if any run in the history window is missing those fields, `report-trend` should fail closed with a clear error naming the offending run

This is intentionally stricter than `report-history`.

Reason:

1. the history index exists to make missing reporting artifacts visible
2. trend should not silently rewrite history by skipping incomplete runs
3. introducing “skip missing runs” semantics would be a wider analytics design choice and should be a later explicit slice if ever needed

### 6.7 Fixed metric set for Version 1

Version 1 trend should use exactly these four metrics already present in the history index:

1. `total_items`
2. `executed_item_count`
3. `approval_coverage_rate`
4. `execution_completion_rate`

Do **not** add:

1. `pending_approval`
2. `gate_item_count`
3. `owner_count`
4. owner-level metrics

Those would require either widening the history index first or re-deriving from raw facts, both of which are outside this slice.

### 6.8 No slope math in Version 1

Do **not** compute slopes yet.

Reason:

1. run cadence is irregular
2. “per run” and “per day” normalization would produce different meanings
3. slope fields would lock in semantics before interval normalization is designed

Version 1 should stay with:

1. ordered run values
2. consecutive interval deltas

That is enough to expose real multi-run progress without prematurely freezing the wrong math model.

## 7. Trend model

The trend packet should remain compact and explicit.

It should contain:

1. `generated_at`
2. `trend_status`
3. `window_run_count`
4. `oldest_run_stamp`
5. `latest_run_stamp`
6. `runs`
7. `intervals`

### 7.1 `trend_status`

Allowed values:

1. `trend_available`
2. `insufficient_history`

### 7.2 `runs`

Each run entry should include:

1. `run_stamp`
2. `dispatch_run_ref`
3. `reporting_ref`
4. `total_items`
5. `executed_item_count`
6. `approval_coverage_rate`
7. `execution_completion_rate`

Ordering:

1. oldest to newest

### 7.3 `intervals`

Each interval entry should represent one consecutive pair:

1. `from_run_stamp`
2. `to_run_stamp`
3. `total_items_delta`
4. `executed_item_count_delta`
5. `approval_coverage_rate_delta`
6. `execution_completion_rate_delta`

Ordering:

1. oldest-to-newest consecutive pairs

Example:

```yaml
intervals:
  - from_run_stamp: 2026-06-01T00-00-00Z
    to_run_stamp: 2026-06-10T00-00-00Z
    total_items_delta: -1
    executed_item_count_delta: 2
    approval_coverage_rate_delta: 1.0
    execution_completion_rate_delta: 0.2222222222
```

### 7.4 Packet examples

`trend_available`:

```yaml
generated_at: 2026-06-12T00:00:00Z
trend_status: trend_available
window_run_count: 3
oldest_run_stamp: 2026-05-20T00-00-00Z
latest_run_stamp: 2026-06-10T00-00-00Z
runs:
  - run_stamp: 2026-05-20T00-00-00Z
    dispatch_run_ref: .omo/debt/dispatch/runs/2026-05-20T00-00-00Z.yaml
    reporting_ref: .omo/debt/reporting/runs/2026-05-20T00-00-00Z/current.yaml
    total_items: 10
    executed_item_count: 0
    approval_coverage_rate: 0.0
    execution_completion_rate: 0.0
  - run_stamp: 2026-06-01T00-00-00Z
    dispatch_run_ref: .omo/debt/dispatch/runs/2026-06-01T00-00-00Z.yaml
    reporting_ref: .omo/debt/reporting/runs/2026-06-01T00-00-00Z/current.yaml
    total_items: 9
    executed_item_count: 1
    approval_coverage_rate: 1.0
    execution_completion_rate: 0.1111111111
  - run_stamp: 2026-06-10T00-00-00Z
    dispatch_run_ref: .omo/debt/dispatch/runs/2026-06-10T00-00-00Z.yaml
    reporting_ref: .omo/debt/reporting/runs/2026-06-10T00-00-00Z/current.yaml
    total_items: 9
    executed_item_count: 0
    approval_coverage_rate: 0.0
    execution_completion_rate: 0.0
intervals:
  - from_run_stamp: 2026-05-20T00-00-00Z
    to_run_stamp: 2026-06-01T00-00-00Z
    total_items_delta: -1
    executed_item_count_delta: 1
    approval_coverage_rate_delta: 1.0
    execution_completion_rate_delta: 0.1111111111
  - from_run_stamp: 2026-06-01T00-00-00Z
    to_run_stamp: 2026-06-10T00-00-00Z
    total_items_delta: 0
    executed_item_count_delta: -1
    approval_coverage_rate_delta: -1.0
    execution_completion_rate_delta: -0.1111111111
```

`insufficient_history`:

```yaml
generated_at: 2026-06-12T00:00:00Z
trend_status: insufficient_history
window_run_count: 1
oldest_run_stamp: 2026-06-10T00-00-00Z
latest_run_stamp: 2026-06-10T00-00-00Z
runs:
  - run_stamp: 2026-06-10T00-00-00Z
    dispatch_run_ref: .omo/debt/dispatch/runs/2026-06-10T00-00-00Z.yaml
    reporting_ref: .omo/debt/reporting/runs/2026-06-10T00-00-00Z/current.yaml
    total_items: 9
    executed_item_count: 0
    approval_coverage_rate: 0.0
    execution_completion_rate: 0.0
intervals: []
```

## 8. Testing and verification strategy

The trend slice should be proven through focused synthetic tests before canonical verify.

Required unit coverage:

1. oldest-to-newest ordering is correct even when history input is newest-to-oldest
2. interval deltas are computed correctly
3. `insufficient_history` produces a valid packet with one run and no intervals
4. missing reporting metadata fails closed with a clear run-specific error
5. Markdown renders trend and insufficient-history states clearly

Required CLI/integration coverage:

1. `report-trend` requires the history packet
2. `report-trend` reads trend inputs from history summary metadata rather than re-deriving from raw facts
3. `report-trend` fails closed when history includes a run with `reporting_exists: false` or null trend metrics
4. synthetic history fixtures can prove multi-run ordering and interval delta behavior

Canonical verify remains:

1. focused trend/doc suites
2. `bash bin/verify-omo.sh`

## 9. Operator impact

Operator guidance in `.omo/AGENT.md` should add:

1. `python3 scripts/omo_debt.py report-trend --omo-dir .omo`
2. `.omo/debt/reporting/trend/current.yaml`
3. `.omo/debt/reporting/trend/current.md`
4. `trend_status: insufficient_history | trend_available`
5. the fixed Version 1 metric set
6. continued deferral of owner trends and slope math

## 10. Why this is the right next slice

This is the smallest useful next step because it:

1. completes the progression from single-run -> history -> pairwise diff -> multi-run trend
2. keeps the metric set bounded to fields the history index already publishes
3. avoids the semantic trap of “burndown-only” naming while still exposing progress over time
4. avoids slope math and owner-trend overreach
5. creates a stable base for any later burndown view or richer multi-run analytics
