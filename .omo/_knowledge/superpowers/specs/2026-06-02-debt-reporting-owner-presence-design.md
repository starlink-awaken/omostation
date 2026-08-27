---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P56 R2: 历史能力/过程/治理/参考/愿景文档批量归档, 当前活跃文档以各面 INDEX/SSOT 为准"
---
# Debt reporting owner presence design

Date: 2026-06-02
Status: approved-by-default baseline (user requested continuation; user was unavailable during the clarifying step, so this proceeds with the recommended bounded slice)
Scope: extend `report-trend` with a narrow additive `owner_presence` block that explains which owners were excluded from shared-owner trends over the selected window, without introducing sparse null-filled owner series, without claiming owner migration semantics, and without jumping to burndown / projection math

## 1. Context

The reporting stack now supports:

1. selected-run compact reporting
2. history index
3. latest-vs-prior diff with owner-level added/removed/shared semantics
4. multi-run summary trends
5. bounded trend windows by `--last <N>` and explicit run ranges
6. shared-owner-only owner trend series inside `report-trend`

That means the current trend packet can already answer:

1. how summary metrics evolve across a selected window
2. how stable shared owners evolve across that same selected window

What it still cannot answer is:

> when owners are excluded from shared-owner trends, who were they, and how did they appear at the edges of the selected window?

The current `owners_excluded_count` already hints at this missing visibility. A consumer can see that some owners were excluded, but cannot tell:

1. which owners they were
2. whether they only existed at the start of the window
3. whether they only existed at the end of the window
4. whether they were intermittent inside the window

This slice should stay narrow because:

1. the missing question is owner-window presence, not full sparse series analytics
2. pairwise latest-vs-prior owner set changes are already covered by `report-diff`
3. burndown, projection, and slope math are still materially wider than the next operator need

## 2. Goals

This design should:

1. stay inside `report-trend`
2. keep shared-owner trend series untouched
3. explain excluded owners over the selected window with deterministic, window-scoped fields
4. avoid overclaiming owner migration or rename semantics
5. preserve full-history / `--last <N>` / explicit run-range selection rules
6. remain additive and easy to test

## 3. Non-goals

This design does not:

1. introduce sparse per-owner null-filled time series
2. add `appeared` / `disappeared` enums with system-global meaning
3. infer owner migration or owner rename semantics
4. change `report-diff`
5. add burndown, projection, or slope math
6. move owner detail into `report-history`

## 4. Approaches considered

### A. Recommended: additive `owner_presence` block inside `report-trend`

Behavior:

1. keep the existing shared-owner `owners` block unchanged
2. add a parallel top-level `owner_presence` block
3. only summarize excluded owners — owners present somewhere in the selected window but not in every run
4. for each excluded owner, report deterministic window-scoped presence fields

Pros:

- smallest safe follow-on to shared-owner trends
- complements `owners_excluded_count` directly
- reuses already-loaded selected run owner packets
- avoids sparse-series complexity

Cons:

- overlaps conceptually with `report-diff` when the selected window is only two runs
- adds a second owner-related block to the trend packet

### B. Wider: sparse owner trend series for all owners in the selected window

Behavior:

1. union owner names across the selected window
2. emit null-filled per-owner series wherever a run lacks that owner

Pros:

- richer analytics
- no owner is hidden

Cons:

- much wider contract
- requires null/gap semantics throughout `runs[]` and `intervals[]`
- increases ambiguity and testing surface substantially

### C. Skip owner presence and jump to burndown / projection

Pros:

- potentially more visible high-level reporting value

Cons:

- bypasses an already-visible contract gap (`owners_excluded_count`)
- requires larger modeling decisions before the operator need is clearly proven
- higher risk of inventing analytics without enough grounded primitives

## 5. Recommended design

Use **Approach A**.

The core decision is:

> extend `report-trend` with a parallel `owner_presence` block that reports window-scoped presence facts for excluded owners only, while leaving shared-owner series in `owners` unchanged and explicitly avoiding sparse null-filled owner trends.

This is the smallest correct next step because:

1. it answers the question created by the current `owners_excluded_count`
2. it stays within the same selected window and same command surface
3. it does not force a commitment to sparse-series semantics
4. it remains easy to test with deterministic window-relative facts

## 6. Architecture

### 6.1 Command boundary stays unchanged

Continue to use:

- `python3 scripts/omo_debt.py report-trend --omo-dir .omo`
- `python3 scripts/omo_debt.py report-trend --omo-dir .omo --last <N>`
- `python3 scripts/omo_debt.py report-trend --omo-dir .omo --from-run-stamp <STAMP> --to-run-stamp <STAMP>`

No new command should be introduced.

### 6.2 `owner_presence` is parallel to `owners`, not nested inside it

The trend packet should gain a top-level additive block:

```yaml
owner_presence:
  presence_status: presence_available
  window_run_count: 4
  entries:
    - owner: omo-governance
      run_count: 2
      first_window_run: 2026-05-20T00-00-00Z
      last_window_run: 2026-06-01T00-00-00Z
      in_first_window_run: true
      in_last_window_run: false
```

This block should remain parallel to `owners` because:

1. `owners` remains about shared-owner metric series
2. `owner_presence` is an audit view for excluded owners
3. mixing both concerns into the same block would make the `owners` contract harder to reason about

### 6.3 `owner_presence` activates only when owner trend inputs activate

Rules:

1. when `owners` is `null`, `owner_presence` is also `null`
2. when `owners.owners_trend_status` is `owners_trend_available` or `no_shared_owners`, `owner_presence` is present
3. when no excluded owners exist, `owner_presence.presence_status` is `no_excluded_owners` and `entries` is empty
4. when excluded owners exist, `owner_presence.presence_status` is `presence_available`

This keeps activation guards aligned with the same selected-window owner inputs already used for shared-owner trends.

### 6.4 Excluded owners are defined relative to the selected window

An excluded owner is:

1. present in at least one selected run
2. absent from at least one selected run

It is **not**:

1. a system-global "new owner"
2. a system-global "removed owner"
3. evidence of owner migration

All semantics in this block are explicitly relative to the currently selected trend window.

### 6.5 Per-entry fields stay window-scoped and deterministic

Each `owner_presence.entries[]` item should contain:

1. `owner`
2. `run_count`
3. `first_window_run`
4. `last_window_run`
5. `in_first_window_run`
6. `in_last_window_run`

Additionally, `owner_presence.window_run_count` should echo the denominator for the whole block.

These fields are enough to answer the minimal operator questions:

1. how often this owner appeared in the selected window
2. whether it existed at the start of the selected window
3. whether it existed at the end of the selected window
4. the first and last selected run in which it appeared

### 6.6 No `appeared` / `disappeared` enum in Version 1

Do **not** add derived labels like:

1. `appeared`
2. `disappeared`
3. `intermittent`

Reason:

1. those labels easily overclaim system-global semantics
2. for example, `in_first_window_run: false` and `in_last_window_run: true` only means the owner appears later inside the selected window; it does **not** prove the owner globally "appeared" in the system

Consumers can derive their own labels from the raw window-scoped booleans if needed.

### 6.7 Keep `owners_excluded_count` where it already lives

Do **not** move or duplicate `owners_excluded_count` in this slice.

Rules:

1. `owners_excluded_count` remains inside `owners`
2. `owner_presence` should not add a second count field
3. callers can cross-check `len(owner_presence.entries)` against `owners.owners_excluded_count`

This avoids a breaking change to the just-landed owner-trend contract and avoids two counters describing the same thing.

### 6.8 Two-run overlap with `report-diff` is acceptable but must be documented

When `window_run_count == 2`, `owner_presence` will conceptually overlap with `report-diff` owner added/removed semantics.

That overlap is acceptable because:

1. `report-diff` remains pairwise latest-vs-prior
2. `report-trend` remains a selected-window surface
3. the fields here stay window-scoped facts, not diff labels

Docs should explicitly note that this overlap exists for two-run windows.

## 7. Data flow

For any selected trend window:

1. reuse the existing selected oldest-to-newest run list
2. reuse the already-loaded selected per-run reporting packets
3. compute the union of owner names across the selected runs
4. compute the shared-owner intersection as today
5. derive excluded owners as `union - shared`
6. for each excluded owner, scan selected runs in oldest-to-newest order and record the minimal presence fields
7. sort `owner_presence.entries` by owner name

## 8. Error handling

This slice does not add a new data source, so the existing owner-input trust model remains:

1. if selected run owner inputs are missing or malformed, `report-trend` still fails closed before owner blocks are emitted
2. empty excluded-owner sets are valid and should not fail
3. missing shared-owner trends due to `insufficient_history` still yield `owners: null` and `owner_presence: null`

## 9. Testing strategy

Write tests in this order:

1. helper RED: one excluded owner present only in the first selected run
2. helper RED: one excluded owner present only in the last selected run
3. helper RED: one excluded owner present only in middle runs
4. helper RED: no excluded owners -> `presence_status: no_excluded_owners`
5. helper RED: `owner_presence is null` when `owners is null`
6. CLI RED: `report-trend --last 2` surfaces `owner_presence.entries[]` for an owner excluded from shared-owner trends
7. docs RED: `.omo/AGENT.md` must state that `owner_presence` is window-scoped and does not imply migration / rename / global appearance semantics

## 10. Success criteria

This slice is complete when:

1. `report-trend` keeps the existing shared-owner trend contract unchanged
2. `owner_presence` appears as a deterministic parallel block when owner inputs are active
3. `owner_presence.entries[]` is sorted and window-scoped
4. no new enum or sparse-series semantics are introduced
5. docs explicitly warn that these are selected-window facts, not system-global lifecycle claims
6. focused and canonical `.omo` verification remain green
