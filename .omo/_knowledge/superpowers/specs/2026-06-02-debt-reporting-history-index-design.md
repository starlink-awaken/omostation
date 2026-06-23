---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P56 R2: 历史能力/过程/治理/参考/愿景文档批量归档, 当前活跃文档以各面 INDEX/SSOT 为准"
---
# Debt reporting history index design

Date: 2026-06-02
Status: approved-by-default baseline (user requested continuation; user unavailable during design approval, so proceeded with the recommended bounded slice after reviewing the newly completed reporting entrypoints layer)
Scope: add a narrow cross-run reporting foundation that introduces a canonical run-history index and prior-run resolution contract for debt reporting, without yet adding burndown math, multi-run trend analytics, or operator-facing latest-vs-prior diff output

## 1. Context

The debt-governance reporting stack now has these layers:

1. `.omo/debt/dispatch/current.yaml` plus immutable `runs/<RUN_STAMP>.yaml` handoff snapshots
2. `.omo/debt/campaign/current.yaml` plus `runs/<RUN_STAMP>/current.yaml` coordination views
3. `.omo/debt/reporting/current.yaml` plus `runs/<RUN_STAMP>/current.yaml` compact latest-run rollups
4. `.omo/debt/registry.yaml` exposes `campaign_ref` and `reporting_ref`
5. `state/system.yaml` promotes `debt_reporting_ref`
6. `sync_omo_state.py` validates registry-level generated refs and the canonical refresh flow is now `refresh -> dispatch -> campaign -> report -> sync -> verify`

That means the missing layer is no longer latest-run visibility.

The real next gap is:

> reporting has immutable run-scoped outputs, but there is still no canonical way to enumerate reporting runs, determine what the prior run is, or prepare future cross-run comparisons without implicitly depending on filesystem ordering or stale derived snapshots.

This needs to stay narrow for three reasons:

1. the live repo currently has only one dispatch/reporting run, so a direct latest-vs-prior diff would mostly emit fallback state
2. cross-run comparison must not use previously generated reporting snapshots as truth inputs if the architecture is supposed to stay direct-from-facts
3. the control plane first needs a stable run-history contract before it can safely layer diff or burndown semantics on top

## 2. Goals

This design should:

1. add one canonical history surface that enumerates known debt reporting runs in stable order
2. define how the system resolves the latest run and the immediately prior run without relying on ad-hoc globbing
3. keep dispatch runs as the canonical run identity for cross-run reporting
4. preserve the existing rule that reporting is derived, not writable truth
5. create the smallest safe foundation for a later latest-vs-prior diff slice

## 3. Non-goals

This design does not:

1. add latest-vs-prior percentage deltas or operator-facing diff output
2. add burndown charts, trend lines, or multi-run analytics
3. reorder the existing reporting packet schema
4. make cross-run reporting depend on `reporting/current.yaml` as an input source
5. add auto-regeneration coupling to `approve` or `revalidate`
6. promote new history pointers into `state/system.yaml`

## 4. Approaches considered

### A. Recommended: canonical history index first, diff later

Add one explicit run-history index surface that records the ordered set of known dispatch/reporting runs and defines prior-run resolution, while deferring actual diff math until the repo has at least two meaningful runs.

Pros:

- solves the real missing contract instead of shipping a mostly-empty comparison surface
- removes silent dependency on lexicographic filesystem ordering
- keeps dispatch runs as the canonical identity while allowing reporting runs to stay derived
- creates a stable base for later latest-vs-prior or burndown work

Cons:

- adds one more generated surface before users see a visible historical comparison
- requires a later follow-up slice to actually compute cross-run deltas

### B. Latest-vs-prior diff now

Immediately add a comparison surface between the latest run and the previous run.

Pros:

- visibly closer to management reporting
- can expose fallback behavior early when only one run exists

Cons:

- currently provides little practical value because the repo only has one run
- pressures the implementation to discover “prior” through ad-hoc directory ordering
- encourages comparing previously generated reporting snapshots instead of canonical dispatch-run facts

### C. Full history and burndown now

Jump directly to multi-run historical analytics, trends, and burndown semantics.

Pros:

- high visible ambition
- may eventually be useful for governance review

Cons:

- far too wide for the current maturity of the debt loop
- invents analytics semantics before the run-history contract is even explicit
- increases the chance of freezing the wrong cross-run model

## 5. Recommended design

Use **Approach A**.

The core decision is:

> the next increment should add a canonical debt reporting history index that enumerates known runs, orders them by dispatch `run_stamp`, and resolves prior-run relationships from dispatch identity rather than from generated reporting files, while explicitly deferring cross-run diff math until a later slice.

This sequencing is correct because:

1. the architecture already treats dispatch runs as the immutable surfaced handoff truth
2. reporting runs are derived outputs and should not become the identity anchor for history semantics
3. the repo does not yet have enough live history to justify a wider comparison layer
4. later diff/burndown work becomes much safer once “latest” and “prior” are first-class concepts

## 6. Architecture

### 6.1 Explicit command boundary

Add one explicit history command:

- `python3 scripts/omo_debt.py report-history --omo-dir .omo`

Behavior:

1. enumerate known dispatch runs
2. locate the matching reporting artifact for each run stamp when it exists
3. write one compact history index surface
4. do not compute deltas between runs in this slice

The command is explicit for the same reason `campaign` and `report` are explicit:

1. history is an aggregate management surface, not an execution side effect
2. keeping it explicit avoids hidden coupling across the governance loop
3. operators can intentionally refresh it after `report`

### 6.2 Canonical run identity

Cross-run reporting identity must remain anchored on the dispatch run, not the reporting artifact.

Canonical identity rules:

1. `run_stamp` comes from the dispatch run identity
2. run ordering is by `run_stamp`, not by `generated_at`
3. reporting artifacts are attached evidence for that run, not the source of ordering truth
4. if a reporting artifact is missing for a known dispatch run, the history index should surface the gap explicitly instead of silently omitting the run

This avoids the staleness problem where comparison semantics accidentally depend on when `report` happened to be regenerated.

### 6.3 Generated surfaces

History outputs should be generated under:

1. `.omo/debt/reporting/history/current.yaml`
2. `.omo/debt/reporting/history/current.md`

This slice does **not** need immutable per-history-run snapshots yet because the history surface is itself a regenerated index over immutable dispatch/reporting runs.

Design intent:

1. `reporting/runs/<RUN_STAMP>/current.yaml` remains the per-run rollup
2. `reporting/history/current.yaml` becomes the canonical run enumeration surface
3. a future `report-diff` or `report-history --compare` layer can read the history index to resolve latest/prior

### 6.4 Prior-run resolution contract

The history index should define prior-run relationships directly in the output model.

Minimum contract:

1. identify the `latest_run_stamp`
2. identify the `prior_run_stamp` when one exists
3. include an ordered list of runs from newest to oldest
4. expose whether each run has a matching reporting artifact

If only one run exists:

1. `latest_run_stamp` is set
2. `prior_run_stamp` is `null`
3. the surface remains valid and informative
4. later diff commands can fail closed or emit an explicit no-prior-run message based on this contract

### 6.5 No derived-snapshot-as-input rule

This slice should make the future comparison rule explicit now:

1. latest-vs-prior diff must re-derive from dispatch, approval, and execution facts for both selected runs
2. pre-generated `reporting/runs/<RUN_STAMP>/current.yaml` is valid evidence/output but not the authoritative computation input
3. the history index may point at those reporting artifacts for convenience, but it must not redefine them as truth

This preserves the architectural rule already established for latest-run reporting.

## 7. History model

The history packet should remain compact.

It should contain:

1. `generated_at`
2. `latest_run_stamp`
3. `prior_run_stamp`
4. `run_count`
5. `runs`

### 7.1 `runs`

Each run entry should include at least:

1. `run_stamp`
2. `dispatch_run_ref`
3. `reporting_ref`
4. `reporting_exists`
5. `report_generated_at`
6. `total_items`
7. `executed_item_count`
8. `approval_coverage_rate`
9. `execution_completion_rate`

Field intent:

1. `dispatch_run_ref` is the canonical identity anchor
2. `reporting_ref` is a convenience pointer to the derived rollup when present
3. the summary fields are copied from the per-run reporting output only as index metadata, not as historical analytics
4. the index remains readable without opening every per-run file

### 7.2 Ordering rules

The `runs` array should be sorted by `run_stamp` descending.

Validation rules:

1. if two runs have the same `run_stamp`, generation should fail loudly
2. malformed run-stamp directories should fail loudly rather than being skipped silently
3. `prior_run_stamp` must refer to the second entry in the ordered list when `run_count >= 2`

## 8. Error handling

The slice should fail loudly when:

1. a dispatch run cannot be parsed into a valid `run_stamp`
2. duplicate run stamps are detected
3. a reporting artifact exists but does not match the indexed run stamp
4. the history command cannot determine a stable newest-to-oldest ordering

The slice should not fail just because a known dispatch run lacks a reporting artifact.

Instead:

1. keep the run in the index
2. set `reporting_exists: false`
3. leave `reporting_ref` empty or null
4. omit copied summary metrics for that run

That missing-artifact state is useful control-plane signal rather than a reason to erase the run from history.

## 9. Testing strategy

The implementation plan should cover at least:

1. history generation with one run
2. history generation with two runs in correct descending order
3. `prior_run_stamp` is null for one run and set for two runs
4. missing reporting artifact is surfaced explicitly, not silently skipped
5. malformed or duplicate run stamps fail loudly
6. `.omo/AGENT.md` documents the new `report-history` operator surface and states that it is the canonical prerequisite for later cross-run diff work
7. canonical `bash bin/verify-omo.sh` remains green

## 10. Success criteria

This slice is successful when:

1. operators can generate a single canonical history view over known reporting runs
2. the control plane can resolve latest and prior run stamps without filesystem folklore
3. the history surface keeps dispatch runs as the authoritative run identity
4. the design leaves cross-run diff and burndown as separate follow-up slices instead of smuggling them into this contract

## 11. Follow-up after this slice

If this lands cleanly, the next natural slice becomes:

1. latest-vs-prior diff based on the history index and prior-run resolver

That later slice should:

1. select `latest_run_stamp` and `prior_run_stamp` from `reporting/history/current.yaml`
2. re-derive both runs from dispatch, approval, and execution facts
3. emit explicit comparison output only when two valid runs exist
4. still defer wider burndown or trend analytics
