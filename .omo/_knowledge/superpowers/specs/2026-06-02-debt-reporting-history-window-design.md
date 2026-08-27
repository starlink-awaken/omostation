---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P56 R2: 历史能力/过程/治理/参考/愿景文档批量归档, 当前活跃文档以各面 INDEX/SSOT 为准"
---
# Debt reporting history window design

Date: 2026-06-02
Status: approved-by-default baseline (user requested continuation; user was unavailable during design approval, so this proceeds with the recommended bounded slice after `report-trend` landed)
Scope: add a narrow count-based history window override for `report-trend` so operators can generate the trend surface from the most recent N runs without introducing run-stamp ranges, owner-level multi-run trends, or projection math

## 1. Context

The debt-governance reporting stack now has these layers:

1. `.omo/debt/reporting/current.yaml` plus `runs/<RUN_STAMP>/current.yaml` for selected-run compact rollups
2. `.omo/debt/reporting/history/current.yaml` for canonical run enumeration with copied summary metadata
3. `.omo/debt/reporting/diff/current.yaml` for latest-vs-prior comparison
4. `.omo/debt/reporting/trend/current.yaml` for oldest-to-newest multi-run trend summaries

That means the control plane can already answer:

1. what one selected run looks like
2. what runs exist
3. how the latest run changed versus the prior run
4. how the full visible run history trends over time

The next missing layer is:

> operators still cannot intentionally bound the trend surface to the most recent slice of history when the run inventory grows.

This needs to stay narrow for four reasons:

1. `report-trend` already established the right metric set and oldest-to-newest rendering contract
2. the next missing capability is window selection, not richer analytics
3. run-stamp selection introduces validation and conflict rules that are wider than the first useful override
4. owner trends and burndown projections both depend on a stable trend-window contract and should not be bundled into this slice

## 2. Goals

This design should:

1. let operators request the most recent N runs for `report-trend`
2. preserve the no-flag behavior exactly as it works today
3. keep trend ordering oldest-to-newest inside the selected window
4. keep fail-closed behavior for missing reporting metadata
5. expose the requested window size in the output packet for auditability
6. leave `report-diff` untouched

## 3. Non-goals

This design does not:

1. add run-stamp range flags such as `--from-run-stamp` or `--to-run-stamp`
2. add owner-level multi-run trend series
3. add projections, slopes, burndown math, or normalized velocity metrics
4. change the four Version 1 trend metrics
5. add skip-missing semantics
6. change `report-history` ordering or contract
7. change `report-diff` selection or packet shape

## 4. Approaches considered

### A. Recommended: count-based window override with `--last N`

Add one optional CLI flag:

- `python3 scripts/omo_debt.py report-trend --omo-dir .omo --last <N>`

Behavior:

1. consume `reporting/history/current.yaml` as today
2. select the most recent N runs from the history packet's existing newest-to-oldest ordering
3. only then reorder the selected window oldest-to-newest
4. compute intervals within that bounded window only

Pros:

- minimal extension to the live trend surface
- preserves current default behavior when omitted
- matches the operator question that appears first in practice: “show me the latest few runs”
- avoids the ambiguity of stamp-based range selection

Cons:

- does not let operators ask for arbitrary interior windows
- requires care to slice before reversing the history order

### B. Wider: run-stamp range flags

Add explicit range selection such as:

- `--from-run-stamp <STAMP>`
- `--to-run-stamp <STAMP>`

Pros:

- most expressive
- allows arbitrary historical windows

Cons:

- requires format validation, existence checks, ordering rules, and conflict behavior with any count flag
- wider than the first useful override
- easy to design ambiguously while the live repo still has sparse run history

### C. Different direction: owner trends or burndown next

Skip windowing and move directly to wider analytics.

Pros:

- more visible management-facing expansion

Cons:

- owner trends need a stable window contract first
- burndown/projection math is premature with the current data density
- both would force a wider semantic jump before the trend surface can even be scoped cleanly

## 5. Recommended design

Use **Approach A**.

The core decision is:

> extend `report-trend` with one optional count-based window override, `--last N`, that selects the N most recent runs from `reporting/history/current.yaml`, preserves current behavior when omitted, and continues to fail closed on incomplete reporting metadata inside the selected window.

This sequencing is correct because:

1. it directly improves the current trend surface instead of inventing a second overlapping reporting command
2. it answers the smallest missing operator question without broadening analytics semantics
3. it gives future owner-trend or projection slices a stable, auditable window contract to build on

## 6. Architecture

### 6.1 Explicit CLI boundary

Extend the existing command:

- `python3 scripts/omo_debt.py report-trend --omo-dir .omo [--last <N>]`

Rules:

1. `--last` is optional
2. `--last` must be an integer greater than or equal to 1
3. omitted `--last` means the full visible history, preserving current behavior exactly

No new command should be introduced.

### 6.2 Window selection happens before oldest-to-newest reordering

This is the critical correctness rule for the slice.

The history packet orders runs newest-to-oldest. Therefore:

1. `report-trend --last N` must first take the newest N entries from `history_packet["runs"]`
2. only after that selection should trend reorder the chosen window oldest-to-newest
3. interval deltas must be computed from that reordered bounded window

This prevents the silent bug where slicing after reversal would accidentally return the oldest N runs instead of the most recent N runs.

### 6.3 Packet shape stays additive

Keep the current trend packet shape and add one field:

- `window_requested`

Packet intent:

1. `window_requested` records the requested count override, or `null` when no override was supplied
2. `window_run_count` continues to mean the actual number of runs present in the selected window
3. `oldest_run_stamp`, `latest_run_stamp`, `runs[]`, and `intervals[]` are all scoped to the selected window

This preserves backward readability while making the selection choice explicit.

### 6.4 Insufficient history remains a valid bounded state

Windowing does not change the existing `insufficient_history` contract.

Required behavior:

1. if the selected window contains fewer than two runs, write a valid packet with `trend_status: insufficient_history`
2. keep `intervals: []`
3. continue rendering Markdown that says the trend baseline is not yet established

Examples:

1. no flag and only one run exists -> unchanged current behavior
2. `--last 5` with only one run available -> still `insufficient_history`
3. `--last 2` with exactly two runs available -> `trend_available`

### 6.5 Missing reporting metadata still fails closed

Windowing must not introduce skip semantics.

Required rule:

1. every run inside the selected window must have `reporting_exists: true`
2. every run inside the selected window must have non-null values for `total_items`, `executed_item_count`, `approval_coverage_rate`, and `execution_completion_rate`
3. if any selected run violates that rule, `report-trend` must fail closed and name the offending run

Out-of-window runs do not matter for that invocation.

This preserves the current trust model while keeping window selection narrow and predictable.

### 6.6 `report-diff` remains untouched

This slice only changes `report-trend`.

Do not:

1. add window flags to `report-diff`
2. change how diff resolves latest/prior from history
3. change diff packet fields

Reason:

1. diff is pairwise latest-vs-prior by design
2. mixing trend-window semantics into diff would blur the reporting layer boundaries

## 7. Data flow

For `python3 scripts/omo_debt.py report-trend --omo-dir .omo --last 3`:

1. load `.omo/debt/reporting/history/current.yaml`
2. take the first 3 entries from the history packet's newest-to-oldest `runs[]`
3. validate all selected entries still satisfy the trend metadata contract
4. reorder those selected entries oldest-to-newest
5. compute interval deltas across the selected ordered window
6. write `.omo/debt/reporting/trend/current.yaml`
7. write `.omo/debt/reporting/trend/current.md`

## 8. Error handling

Version 1 windowing should fail explicitly in these cases:

1. missing reporting history packet -> existing `FileNotFoundError`
2. empty reporting history packet -> existing `ValueError`
3. invalid `--last` value such as `0` or negative -> CLI argument validation failure
4. selected run missing reporting metadata -> `ValueError` naming the offending run

Version 1 windowing should **not**:

1. silently clamp `--last` upward from invalid values
2. skip missing runs
3. reinterpret `--last` as a run-stamp range

If `--last` is larger than available history, the command should succeed and behave like “use all visible runs.”

## 9. Testing strategy

Add focused regressions for:

1. helper-level selection of the most recent N runs, not the oldest N runs
2. helper-level no-flag behavior parity with the current full-history contract
3. helper-level `--last` larger than available history behaving like the no-flag case
4. helper-level fail-closed behavior when a selected run has missing reporting metadata
5. CLI-level `report-trend --last N` output shape and status
6. docs/operator guidance for the new optional flag and packet field

Do not broaden tests into:

1. run-stamp ranges
2. owner trends
3. projections or slope math

## 10. Success criteria

This slice is complete when:

1. operators can run `python3 scripts/omo_debt.py report-trend --omo-dir .omo --last <N>`
2. omitted `--last` produces the same result as current behavior
3. bounded windows use the most recent N runs, ordered oldest-to-newest in output
4. `window_requested` is visible in the packet
5. incomplete selected runs still fail closed
6. canonical `.omo` verification still passes

## 11. Follow-up slices intentionally deferred

After this lands, the most natural future slices are:

1. run-stamp range selection if operators truly need interior historical windows
2. owner-level multi-run trends built on the stable window contract
3. burndown or projection analytics once the repo has enough real run history to justify them
