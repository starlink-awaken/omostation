---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P56 R2: 历史能力/过程/治理/参考/愿景文档批量归档, 当前活跃文档以各面 INDEX/SSOT 为准"
---
# Debt reporting run range design

Date: 2026-06-02
Status: approved-by-default baseline (user requested continuation; user was unavailable during design approval, so this proceeds with the recommended bounded slice after `report-trend --last` landed)
Scope: add one narrow closed-interval run-stamp range selector for `report-trend` so operators can inspect an interior historical window without changing `report-diff`, without adding single-bound moving anchors, and without introducing owner-level trends or projection math

## 1. Context

The debt-governance reporting stack now has these layers:

1. `.omo/debt/reporting/current.yaml` plus `runs/<RUN_STAMP>/current.yaml` for selected-run compact rollups
2. `.omo/debt/reporting/history/current.yaml` for canonical run enumeration with copied summary metadata
3. `.omo/debt/reporting/diff/current.yaml` for latest-vs-prior comparison
4. `.omo/debt/reporting/trend/current.yaml` for multi-run trend summaries
5. `report-trend --last <N>` for newest-N bounded windows

That means the control plane can already answer:

1. what one selected run looks like
2. what runs exist
3. how the latest run changed versus the prior run
4. how the visible history trends over time
5. how the most recent N runs trend over time

The next missing layer is:

> operators still cannot intentionally select an interior historical window by run identity.

The `--last <N>` slice solved recency windows, but it deliberately did **not** solve:

1. “show me the range from run A through run B”
2. “exclude newer runs and focus on a specific interior segment”
3. “pin a historical window by stable run identity instead of moving recency”

This next slice must stay narrow because:

1. the core missing capability is identity-based range selection, not richer analytics
2. owner trends and projections still depend on a stable range contract and should not be bundled here
3. `report-diff` already has a separate pairwise latest-vs-prior contract and should remain untouched
4. single-bound open ranges would introduce moving implicit anchors that are wider and less stable than the smallest safe contract

## 2. Goals

This design should:

1. let operators select a closed historical interval by run stamp
2. keep output ordering oldest-to-newest within the selected range
3. keep fail-closed behavior for missing range stamps and missing reporting metadata
4. keep the no-flag and `--last <N>` behaviors intact
5. make the requested range visible in the packet for auditability
6. avoid changing `report-diff`

## 3. Non-goals

This design does not:

1. allow single-bound open ranges
2. allow combining `--last` with range flags
3. add owner-level multi-run trend series
4. add projections, burndown math, slope math, or normalized velocity
5. change the four Version 1 trend metrics
6. change `report-history` ordering or packet shape
7. change `report-diff` selection semantics or packet shape

## 4. Approaches considered

### A. Recommended: closed interval with both bounds required

Add two flags:

- `--from-run-stamp <STAMP>`
- `--to-run-stamp <STAMP>`

Both are required when range mode is used.

Behavior:

1. validate both run stamps against the existing `%Y-%m-%dT%H-%M-%SZ` contract
2. locate both stamps in `reporting/history/current.yaml`
3. select the inclusive newest-to-oldest slice between them
4. reorder that selected window oldest-to-newest for trend rendering

Pros:

- safest Version 1 contract
- fully explicit and reproducible
- avoids moving implicit anchors
- naturally composes with the existing oldest-to-newest trend output

Cons:

- slightly more verbose than single-bound open ranges
- callers who want “from X to latest” must pass both bounds explicitly

### B. Wider: allow single-bound open ranges

Add `--from-run-stamp` and `--to-run-stamp`, but allow either bound independently.

Pros:

- more ergonomic at the CLI
- fewer arguments for common use

Cons:

- single-bound requests silently depend on moving oldest/latest anchors
- harder to reason about reproducibility as history grows
- wider semantics than the minimum safe slice

### C. Different direction: skip range and jump to owner-level multi-run trends

Pros:

- more visible analytics expansion

Cons:

- owner trends need a stable range contract first
- current history packet does not carry per-owner run-series data
- wider scope than this next bounded step

## 5. Recommended design

Use **Approach A**.

The core decision is:

> extend `report-trend` with one explicit closed-interval range mode, `--from-run-stamp <STAMP> --to-run-stamp <STAMP>`, where both bounds are required, both endpoints are inclusive, and the command continues to fail closed if either stamp is invalid, missing from history, or selects runs with incomplete reporting metadata.

This sequencing is correct because:

1. it extends the current trend surface instead of inventing a second overlapping command
2. it answers the next smallest operator question after `--last <N>`
3. it keeps the first range contract explicit and reproducible
4. it gives future owner-trend or projection slices a stable identity-based window primitive

## 6. Architecture

### 6.1 Explicit CLI boundary

Extend the existing command:

- `python3 scripts/omo_debt.py report-trend --omo-dir .omo --from-run-stamp <STAMP> --to-run-stamp <STAMP>`

Rules:

1. range mode requires **both** flags
2. neither flag may be combined with `--last`
3. omitted range flags preserve existing behavior (`full history` or `--last`)

No new command should be introduced.

### 6.2 Range endpoints are inclusive

The selected range includes both requested stamps.

For:

- `--from-run-stamp 2026-05-20T00-00-00Z`
- `--to-run-stamp 2026-06-10T00-00-00Z`

the selected window must include:

1. `2026-05-20T00-00-00Z`
2. every run between the two bounds present in history
3. `2026-06-10T00-00-00Z`

This keeps the contract explicit and easy to explain.

### 6.3 Selection happens in history's newest-to-oldest space

This is the critical correctness rule for the slice.

`reporting/history/current.yaml` orders runs newest-to-oldest. Therefore:

1. locate `to-run-stamp` in the newest-to-oldest list
2. locate `from-run-stamp` in the newest-to-oldest list
3. require the newer `to` bound to appear at an equal-or-lower index than the older `from` bound
4. select `runs[to_index : from_index + 1]`
5. only after selection, reverse the chosen range oldest-to-newest for trend rendering

This avoids the silent bug where slicing in the wrong direction would produce an empty or inverted range.

### 6.4 Range stamps must validate and must exist

Required rules:

1. both requested stamps must satisfy the existing run-stamp format `%Y-%m-%dT%H-%M-%SZ`
2. both requested stamps must be present in `history.current.yaml`
3. if either validation fails, `report-trend` must fail closed with a clear error

The command should **not**:

1. clamp to the nearest visible run
2. silently skip a missing bound
3. reinterpret malformed ISO timestamps

### 6.5 Range mode and `--last` are mutually exclusive

Required rule:

1. `--last` cannot be combined with `--from-run-stamp` or `--to-run-stamp`

Reason:

1. recency windows and identity-based ranges are separate selection modes
2. allowing both would introduce ambiguous precedence rules

This must fail explicitly at CLI parse / dispatch time.

### 6.6 Packet shape stays additive

Keep the current trend packet shape and add two fields:

1. `from_run_stamp_requested`
2. `to_run_stamp_requested`

Packet intent:

1. `window_requested` continues to belong only to `--last <N>`
2. `from_run_stamp_requested` / `to_run_stamp_requested` record the explicit range request, or `null` when range mode is not used
3. `window_run_count`, `oldest_run_stamp`, `latest_run_stamp`, `runs[]`, and `intervals[]` remain scoped to the selected range

This keeps range selection auditable without overloading the count-based field.

### 6.7 Missing reporting metadata still fails closed

Range mode must preserve the current trust model.

Required rule:

1. every run inside the selected range must have `reporting_exists: true`
2. every run inside the selected range must have non-null values for `total_items`, `executed_item_count`, `approval_coverage_rate`, and `execution_completion_rate`
3. if any selected run violates that rule, `report-trend` must fail closed and name the offending run

Out-of-range runs do not matter for that invocation.

### 6.8 `report-diff` remains untouched

This slice only changes `report-trend`.

Do not:

1. add range flags to `report-diff`
2. change diff's latest/prior selection from history
3. change diff packet fields

Reason:

1. diff remains pairwise latest-vs-prior
2. trend remains the multi-run surface

## 7. Data flow

For:

- `python3 scripts/omo_debt.py report-trend --omo-dir .omo --from-run-stamp 2026-05-20T00-00-00Z --to-run-stamp 2026-06-10T00-00-00Z`

the command should:

1. load `.omo/debt/reporting/history/current.yaml`
2. validate both requested stamps
3. find both stamps inside the history packet's newest-to-oldest `runs[]`
4. select the inclusive newest-to-oldest slice between them
5. validate reporting metadata for every run inside the selected range
6. reorder that selected range oldest-to-newest
7. compute interval deltas across the selected ordered range
8. write `.omo/debt/reporting/trend/current.yaml`
9. write `.omo/debt/reporting/trend/current.md`

## 8. Error handling

Version 1 range mode should fail explicitly in these cases:

1. invalid `from-run-stamp` format
2. invalid `to-run-stamp` format
3. only one range bound supplied
4. `--last` combined with either range flag
5. either requested stamp missing from visible history
6. reversed semantic range where the requested `from` is newer than the requested `to`
7. selected run missing reporting metadata

Version 1 range mode should **not**:

1. silently swap reversed bounds
2. silently expand one bound to oldest/latest
3. silently clamp to nearest visible runs
4. skip missing-metadata runs

## 9. Testing strategy

Add focused regressions for:

1. helper-level inclusive range selection on an interior window
2. helper-level “slice in newest-to-oldest, then reverse” correctness
3. helper-level invalid stamp format
4. helper-level missing requested stamp
5. helper-level reversed semantic range
6. helper-level fail-closed behavior for missing reporting metadata inside the selected range
7. CLI-level mutual exclusion with `--last`
8. CLI-level requirement that both range bounds be provided together
9. docs/operator guidance for range mode and requested-range packet fields

Do not broaden tests into:

1. single-bound open ranges
2. owner-level trend series
3. projections or slope math

## 10. Success criteria

This slice is complete when:

1. operators can run `python3 scripts/omo_debt.py report-trend --omo-dir .omo --from-run-stamp <STAMP> --to-run-stamp <STAMP>`
2. range mode is inclusive and correctly ordered oldest-to-newest in output
3. malformed, missing, partial, or conflicting range requests fail explicitly
4. `window_requested` remains reserved for `--last <N>`
5. `from_run_stamp_requested` and `to_run_stamp_requested` are visible in the trend packet
6. canonical `.omo` verification still passes

## 11. Follow-up slices intentionally deferred

After this lands, the most natural future slices are:

1. loosening the contract later to allow explicit single-bound open ranges if operators truly need them
2. owner-level multi-run trends built on the stable count/range window contracts
3. burndown or projection analytics once the repo has enough real run history to justify them
