# Debt reporting owner diff design

Date: 2026-06-02
Status: approved-by-default baseline (user requested continuation; user was unavailable during design approval, so this proceeds with the recommended bounded slice after the summary-only diff layer landed)
Scope: extend the existing latest-vs-prior `report-diff` surface with owner-level diff output for shared owners, while explicitly surfacing added/removed owners and continuing to defer burndown, wider trend analytics, and full owner-set migration semantics

## 1. Context

The debt-governance reporting stack now has these layers:

1. `.omo/debt/reporting/current.yaml` plus `runs/<RUN_STAMP>/current.yaml` for latest-run compact rollups
2. `.omo/debt/reporting/history/current.yaml` for canonical latest/prior run selection
3. `.omo/debt/reporting/diff/current.yaml` for summary-only latest-vs-prior comparison

That means the control plane can already answer:

1. what the latest reporting packet says
2. what the prior reporting run is
3. how top-level summary metrics changed between the latest and prior runs

The next missing layer is:

> the diff surface can show that the run changed, but it still cannot answer which owners improved, regressed, or changed membership across runs.

This needs to stay narrow for four reasons:

1. the current diff surface already established the right command and run-selection contract, so this slice should extend that surface rather than invent a parallel artifact
2. owner entries in reporting are emitted as lists, so Version 1 owner diff must explicitly key by owner identity and not silently depend on list position
3. owner membership can change between runs, but the first owner diff slice should surface that change without yet inventing full per-owner migration analytics
4. the live repo still has only one checked-in run, so correctness must be proven through synthetic prior-run fixtures rather than by widening the live contract too aggressively

## 2. Goals

This design should:

1. keep `python3 scripts/omo_debt.py report-diff --omo-dir .omo` as the single diff command
2. preserve the existing summary diff contract unchanged
3. replace `owners: null` with a deterministic owner diff block whenever `diff_status == diff_available`
4. compute metric deltas only for owners present in both latest and prior runs
5. explicitly surface owners added in the latest run and removed since the prior run
6. make owner matching deterministic by owner identity rather than list position
7. keep `no_prior_run` as a valid state with `owners: null`

## 3. Non-goals

This design does not:

1. add burndown, trend, or multi-run owner analytics
2. add per-owner explanations, rationale text, or workflow state beyond metric deltas
3. compute partial deltas for owners that exist in only one run
4. add explicit `--latest-run` / `--prior-run` overrides
5. split owner diff into a separate `owner-diff` command or artifact
6. promote owner diff pointers into `state/system.yaml`

## 4. Approaches considered

### A. Recommended: shared-owner metrics plus explicit added/removed owner lists

Extend the existing `report-diff` packet so that, when a prior run exists, `owners` becomes a structured object containing:

1. `compared` — metric deltas for owners present in both runs
2. `added` — name-only owner entries present only in the latest run
3. `removed` — name-only owner entries present only in the prior run

Pros:

- keeps the diff surface unified
- prevents silent omission when owner membership changes
- stays bounded because only shared owners receive full metric comparison
- preserves room for richer owner-set semantics later

Cons:

- changes the `owners` field from reserved `null` to a real object for `diff_available`
- requires both YAML and Markdown renderers to grow in the same slice

### B. Narrower: shared-owner metrics only

Compute owner deltas only for owners present in both runs and ignore newly added or removed owners entirely.

Pros:

- smallest immediate implementation
- easy to explain

Cons:

- silently hides governance-relevant owner-set changes
- can make the diff appear complete when it is not
- produces misleading output if a synthetic or future live run changes owner membership

### C. Wider: full owner-set semantics now

Extend `report-diff` with shared-owner deltas plus detailed analytics for added/removed owners, owner-count shifts, and richer owner migration interpretation.

Pros:

- highest management-facing completeness
- may reduce later follow-up work

Cons:

- too wide for the first owner diff increment
- invents semantics before there is evidence they are needed
- makes testing and operator guidance broader than necessary

## 5. Recommended design

Use **Approach A**.

The core decision is:

> keep `report-diff` as the only cross-run comparison surface, preserve the existing summary diff block, and extend `owners` into a deterministic owner diff object that computes metric deltas only for shared owners while explicitly listing added and removed owners.

This sequencing is correct because:

1. the summary-only diff slice already proved the command boundary and history-based pair selection
2. owner-level visibility is now the highest-value missing detail
3. silently dropping added/removed owners would make the diff operationally misleading
4. a bounded shared-owner comparison still keeps the slice much smaller than burndown or richer owner migration analytics

## 6. Architecture

### 6.1 Keep `report-diff` as the single diff surface

Do not add a new command.

Continue to use:

- `python3 scripts/omo_debt.py report-diff --omo-dir .omo`

Behavioral rule:

1. history remains selector-only
2. reporting packets for latest and prior runs are still re-derived from dispatch, approval, and execution facts
3. summary diff stays exactly as it is today
4. owner diff is added into the existing packet under `owners`

This keeps all latest-vs-prior comparison in one artifact instead of forcing operators or future automation to join multiple diff files.

### 6.2 Deterministic owner identity matching

Owner comparison must never depend on reporting list order.

Required matching rule:

1. build `latest_by_owner` from `latest_packet["owners"]`
2. build `prior_by_owner` from `prior_packet["owners"]`
3. compare by the `owner` string key
4. sort all output owner lists lexicographically by owner name

The implementation must **not**:

1. zip owner lists by index
2. rely on dispatch YAML ordering staying identical across runs
3. silently reorder output based on incidental source ordering

This is a correctness requirement, not just a formatting preference.

### 6.3 `owners` contract by diff status

When `diff_status == no_prior_run`:

1. keep `owners: null`
2. keep the current valid no-prior-run packet behavior

When `diff_status == diff_available`:

1. `owners` must be a populated object, never `null`
2. empty owner sections are represented by empty lists, not missing fields

This removes the ambiguous state where `diff_available` exists but `owners` still looks unimplemented.

### 6.4 Shared-owner-only metric comparison

For owners present in both runs, compute the same operational metrics already used in latest-run reporting:

1. `item_count`
2. `state_counts.pending_approval`
3. `state_counts.ready_to_execute`
4. `state_counts.executed`
5. `gate_item_count`
6. `approved_gate_item_count`
7. `approval_coverage_rate`
8. `executed_item_count`
9. `execution_completion_rate`

Each metric uses the same `latest` / `prior` / `delta` contract already used by `summary_diff`.

### 6.5 Explicit added/removed owner visibility

Owners that exist in only one run are not diffed metrically in Version 1, but they must still be surfaced.

Rules:

1. owners present in latest but absent in prior appear under `owners.added`
2. owners present in prior but absent in latest appear under `owners.removed`
3. these lists are name-only entries in Version 1
4. they do not carry metric deltas yet

This keeps the slice bounded while preventing silent omission of structure-changing events.

### 6.6 Markdown parity with YAML

The human-readable surface must evolve in the same slice as the machine-readable packet.

`render_reporting_diff_markdown(...)` should therefore:

1. keep the current summary diff section
2. add a shared-owner section that prints compared owner deltas in deterministic order
3. add explicit added-owner and removed-owner sections when those lists are non-empty
4. keep the `no_prior_run` message when there is no prior baseline

The `.md` surface must not lag behind the `.yaml` contract.

## 7. Owner diff model

The top-level diff packet remains:

1. `generated_at`
2. `diff_status`
3. `latest_run_stamp`
4. `prior_run_stamp`
5. `latest_dispatch_run_ref`
6. `prior_dispatch_run_ref`
7. `summary_diff`
8. `owners`

### 7.1 `owners`

When `diff_status == diff_available`, `owners` should contain:

1. `compared`
2. `added`
3. `removed`

Example shape:

```yaml
owners:
  compared:
    - owner: commerce-governance
      item_count:
        latest: 3
        prior: 2
        delta: 1
      state_counts:
        pending_approval:
          latest: 0
          prior: 1
          delta: -1
        ready_to_execute:
          latest: 2
          prior: 1
          delta: 1
        executed:
          latest: 1
          prior: 0
          delta: 1
      gate_item_count:
        latest: 1
        prior: 1
        delta: 0
      approved_gate_item_count:
        latest: 1
        prior: 0
        delta: 1
      approval_coverage_rate:
        latest: 1.0
        prior: 0.0
        delta: 1.0
      executed_item_count:
        latest: 1
        prior: 0
        delta: 1
      execution_completion_rate:
        latest: 0.3333333333
        prior: 0.0
        delta: 0.3333333333
  added:
    - owner: new-owner
  removed:
    - owner: old-owner
```

### 7.2 `owners.compared`

Each entry must include:

1. `owner`
2. `item_count`
3. `state_counts.pending_approval`
4. `state_counts.ready_to_execute`
5. `state_counts.executed`
6. `gate_item_count`
7. `approved_gate_item_count`
8. `approval_coverage_rate`
9. `executed_item_count`
10. `execution_completion_rate`

Each metric uses:

1. `latest`
2. `prior`
3. `delta`

### 7.3 `owners.added` and `owners.removed`

Each entry contains only:

1. `owner`

This intentionally keeps Version 1 small while preserving additive room for later owner-set semantics.

### 7.4 Continue excluding `owner_count`

Do not add `owner_count` back through the owner diff side door.

Reason:

1. `added` and `removed` already explain owner-set change more concretely
2. raw owner-count deltas are less actionable than explicit owner identities
3. keeping `owner_count` out avoids duplicative or confusing signals

## 8. Testing and verification strategy

The owner diff slice should be proven through focused synthetic tests before canonical verify.

Required unit coverage:

1. shared-owner metric deltas are computed correctly
2. owner ordering differences between latest and prior packets do not affect matching correctness
3. added and removed owners are surfaced explicitly
4. `no_prior_run` continues to keep `owners: null`
5. Markdown renders compared, added, and removed owner sections

Required CLI/integration coverage:

1. `report-diff` still requires the history packet
2. `report-diff` re-derives both runs from facts rather than trusting history metadata
3. synthetic prior-run fixtures can prove added/removed/shared owner cases through run-scoped dispatch inputs

Canonical verify remains:

1. focused diff/doc suites
2. `bash bin/verify-omo.sh`

## 9. Operator impact

Operator guidance in `.omo/AGENT.md` should change from:

1. `owners: null` reserved for later

to:

1. summary diff remains part of `report-diff`
2. owner-level diff now appears under `owners.compared`
3. owner additions and removals appear under `owners.added` and `owners.removed`
4. burndown and wider trend analytics remain deferred

## 10. Why this is the right next slice

This is the smallest useful next step because it:

1. preserves the already-correct history and summary diff architecture
2. adds the next missing management-facing detail without inventing broader analytics
3. fixes the biggest correctness risk for owner diff up front: identity matching by owner key rather than list order
4. avoids the false confidence that would come from silently ignoring added or removed owners
5. keeps later burndown or richer owner-set semantics as separate bounded slices
