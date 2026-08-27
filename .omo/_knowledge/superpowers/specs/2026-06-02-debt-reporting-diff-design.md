---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P56 R2: 历史能力/过程/治理/参考/愿景文档批量归档, 当前活跃文档以各面 INDEX/SSOT 为准"
---
# Debt reporting diff design

Date: 2026-06-02
Status: approved-by-default baseline (user requested continuation; user unavailable during design approval, so proceeded with the recommended bounded slice after the reporting history index landed)
Scope: add a narrow latest-vs-prior debt reporting diff surface that compares top-level summary metrics between the latest run and the immediately prior run, without yet adding owner-level deltas, burndown semantics, or wider trend analytics

## 1. Context

The debt-governance reporting stack now has these layers:

1. `.omo/debt/reporting/current.yaml` plus `runs/<RUN_STAMP>/current.yaml` for latest-run compact rollups
2. `.omo/debt/registry.yaml` and `state/system.yaml` for reporting discovery
3. `.omo/debt/reporting/history/current.yaml` for canonical run enumeration with `latest_run_stamp` and `prior_run_stamp`

That means the control plane can now answer:

1. what the current reporting packet says
2. what reporting runs exist
3. which run is latest and which run is prior

The next missing layer is:

> operators and leads can resolve the latest/prior run pair, but there is still no explicit surface that answers how the current run changed versus the immediately previous run.

This should stay narrow for four reasons:

1. the history index already solved run discovery, so the next step is comparison, not more indexing
2. owner-level deltas introduce set-difference semantics that are wider than the first useful diff slice
3. the current repo still has only one live run, so Version 1 must treat “no prior run yet” as a first-class normal state
4. cross-run diff must preserve the existing direct-from-facts rule and must not turn generated reporting snapshots into truth inputs

## 2. Goals

This design should:

1. add one explicit latest-vs-prior diff command and generated surface
2. use the history index only to select the latest/prior run pair
3. re-derive both runs from dispatch, approval, and execution facts before computing deltas
4. compare summary-only metrics for the first diff version
5. make “no prior run yet” a valid machine-readable diff state rather than a command failure
6. reserve schema space for a future owner-level diff slice without breaking the first packet shape

## 3. Non-goals

This design does not:

1. add owner-level deltas in Version 1
2. add burndown charts, trend lines, or multi-run comparisons beyond latest vs prior
3. make the diff command accept explicit `--latest-run` / `--prior-run` overrides
4. compare generated `reporting/runs/<RUN_STAMP>/current.yaml` snapshots as the authoritative input
5. fold diff content into `reporting/history/current.yaml`
6. promote a diff pointer into `state/system.yaml`

## 4. Approaches considered

### A. Recommended: summary-only diff as a distinct surface

Add one explicit `report-diff` command that uses the history index to resolve the latest/prior run pair, re-derives both reporting packets from facts, and writes a separate diff packet containing top-level summary comparisons only.

Pros:

- finally makes the history index operationally useful
- keeps the first diff slice small enough to validate even while the repo still has only one live run
- preserves the direct-from-facts architecture rule
- avoids overloading history with a second responsibility

Cons:

- defers owner-level detail to a later slice
- requires one more generated reporting surface

### B. Wider: summary + owner-level diff now

Add summary deltas and per-owner deltas in the same first diff slice.

Pros:

- more management-facing detail immediately
- may reduce the need for a later owner-specific follow-up

Cons:

- owner membership can change across runs, which introduces new/removed-owner semantics too early
- much harder to validate cleanly while the repo still has only one run
- increases schema and testing complexity for the first diff boundary

### C. Narrower: selection seam only

Add an explicit latest/prior selector helper or operator surface, but still do not emit a diff packet.

Pros:

- very safe
- extremely small

Cons:

- duplicates value the history index already largely provides
- still leaves the user without a direct comparison surface
- not the highest-value next step anymore

## 5. Recommended design

Use **Approach A**.

The core decision is:

> the next increment should add a distinct `report-diff` surface under `reporting/diff/current.*` that selects the latest/prior run pair from the reporting history index, re-derives both reporting packets from dispatch/approval/execution facts, and compares summary-only metrics while treating `no_prior_run` as a valid packet state and reserving `owners: null` for a later owner-level diff slice.

This sequencing is correct because:

1. history already established stable run selection
2. summary-only diff gives visible value without the complexity of owner-set comparison
3. a distinct diff surface keeps history, reporting, and comparison concerns separate
4. explicit `no_prior_run` packets let the command join the canonical pipeline immediately, even before a second run exists

## 6. Architecture

### 6.1 Explicit command boundary

Add:

- `python3 scripts/omo_debt.py report-diff --omo-dir .omo`

Behavior:

1. load `.omo/debt/reporting/history/current.yaml`
2. resolve `latest_run_stamp` and `prior_run_stamp`
3. if `prior_run_stamp` is present, re-derive reporting packets for both runs from facts and compute the diff
4. if `prior_run_stamp` is null, write a valid `no_prior_run` diff packet
5. do not mutate debt items, approvals, executions, reporting current, or history current

### 6.2 Run selection comes from history, not from ad-hoc discovery

The diff command should use the history index only for pair selection:

1. read `latest_run_stamp`
2. read `prior_run_stamp`
3. read the corresponding `dispatch_run_ref` values from `runs[]`

The history index is therefore:

1. the canonical selector
2. not the source of diff metric values

This keeps the history layer focused on run identity while preventing diff logic from drifting back to glob-based discovery.

### 6.3 Direct-from-facts recomputation

Once the run pair is selected, the diff command must re-derive both reporting packets from facts.

It should:

1. load the selected dispatch runs by `dispatch_run_ref`
2. resolve matching approval facts for each run
3. resolve matching execution facts for each run
4. rebuild both reporting packets in memory using the existing campaign/reporting derivation path
5. compute deltas from those fresh in-memory packets

It must **not** treat:

1. `reporting/history/current.yaml`
2. `reporting/runs/<RUN_STAMP>/current.yaml`

as authoritative metric sources for the diff itself.

### 6.4 Distinct generated surfaces

Diff outputs should be generated under:

1. `.omo/debt/reporting/diff/current.yaml`
2. `.omo/debt/reporting/diff/current.md`

Design intent:

1. `reporting/current.*` remains one selected run's compact rollup
2. `reporting/history/current.*` remains run enumeration and pair selection
3. `reporting/diff/current.*` becomes the cross-run comparison surface

### 6.5 Valid no-prior-run packet

If `prior_run_stamp` is null in the history index, `report-diff` should still write a valid packet.

That packet should:

1. set `diff_status: no_prior_run`
2. include the resolved `latest_run_stamp`
3. keep `prior_run_stamp: null`
4. leave comparison fields as null or empty according to the diff schema
5. render Markdown that clearly says the baseline has not yet been established

This keeps the command pipeline-safe and machine-readable.

### 6.6 Owner-level deferral with schema reservation

Version 1 should not compute owner-level deltas.

However, the packet should reserve:

- `owners: null`

This makes the future owner-diff extension additive rather than schema-breaking.

### 6.7 Exclude `owner_count` from Version 1 diff

Do **not** include `owner_count` in the first diff surface.

Reason:

1. a changed owner count without owner identity is not actionable
2. once owner-level diff exists, owner-count change can be understood in context
3. excluding it now keeps the summary diff focused on directly actionable operational signals

## 7. Diff model

The diff packet should stay compact and explicit.

It should contain:

1. `generated_at`
2. `diff_status`
3. `latest_run_stamp`
4. `prior_run_stamp`
5. `latest_dispatch_run_ref`
6. `prior_dispatch_run_ref`
7. `summary_diff`
8. `owners`

### 7.1 `diff_status`

Allowed values:

1. `diff_available`
2. `no_prior_run`

### 7.2 `summary_diff`

`summary_diff` should include:

1. `total_items`
2. `state_counts`
   - `pending_approval`
   - `ready_to_execute`
   - `executed`
3. `gate_item_count`
4. `approved_gate_item_count`
5. `approval_coverage_rate`
6. `executed_item_count`
7. `execution_completion_rate`

Each field should use the same comparison shape:

1. `latest`
2. `prior`
3. `delta`

Example:

```yaml
summary_diff:
  total_items:
    latest: 9
    prior: 9
    delta: 0
  approval_coverage_rate:
    latest: 1.0
    prior: 0.0
    delta: 1.0
```

For `no_prior_run`:

1. `latest` is still populated from the re-derived latest reporting packet
2. `prior` is null
3. `delta` is null

### 7.3 `owners`

In Version 1:

- `owners: null`

This field is intentionally reserved for a later owner-level diff slice.

## 8. Markdown surfacing

The Markdown packet should:

1. state whether the diff is `diff_available` or `no_prior_run`
2. show the selected latest/prior run stamps
3. show one compact summary block for the compared metrics
4. make it obvious when a prior baseline is not yet available
5. avoid owner-level tables or per-item re-listing

This keeps the first diff surface readable and intentionally narrow.

## 9. Error handling

The slice should fail loudly when:

1. `reporting/history/current.yaml` is missing
2. the history packet is empty or malformed
3. `latest_run_stamp` is missing
4. a run selected by history cannot be resolved to a matching `dispatch_run_ref`
5. re-derivation of either selected run fails because required dispatch, approval, or execution inputs are inconsistent

The slice should **not** fail just because `prior_run_stamp` is null.

That is a valid `no_prior_run` state, not an error.

## 10. Testing strategy

The implementation plan should cover at least:

1. `report-diff` fails when history current is missing
2. `report-diff` writes a valid `no_prior_run` packet when history has only one run
3. `report-diff` writes a valid diff packet when two runs exist
4. the diff uses summary fields beyond what the history index copies, proving it re-derived from facts rather than reading only history metadata
5. `owners` is present and null in Version 1
6. `.omo/AGENT.md` documents `report-diff` and the `reporting/diff/current.*` surface
7. canonical `bash bin/verify-omo.sh` remains green

## 11. Success criteria

This slice is successful when:

1. operators can generate one explicit latest-vs-prior diff packet
2. the diff packet is still valid when only one run exists
3. history remains the canonical selector, not the diff content container
4. the diff is computed from fresh fact re-derivation, not from stale generated snapshots
5. the design stays narrow enough that owner-level diff and burndown remain separate follow-up slices
