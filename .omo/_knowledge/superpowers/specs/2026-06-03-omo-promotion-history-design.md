---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P56 R2: 历史能力/过程/治理/参考/愿景文档批量归档, 当前活跃文档以各面 INDEX/SSOT 为准"
---
# OMO promotion history surface design

Date: 2026-06-03
Status: approved-by-user-default execution mode (user explicitly waived intermediate review gates and requested direct spec/plan/execution)
Scope: add a canonical history/current surface for task promotion envelopes so operators and later governance slices stop reading raw `workers/runs/*-promotion-*.yaml` files directly

## 1. Context

The planned-to-active promotion workflow is now live:

1. `python3 scripts/omo_worker.py task promote-eval <TASK_ID> --omo-dir .omo`
2. `python3 scripts/omo_worker.py task promote-apply <TASK_ID> --promoted-by <ACTOR> --now <ISO8601> --omo-dir .omo`
3. promotion creates immutable envelope artifacts under `.omo/workers/runs/`
4. promoted pending packets record the envelope ref in `handoff_refs`

That closed the queue-mutation gap, but it left the next governance gap open:

> where is the canonical surface for "what promotions have happened"?

Right now the only source is raw filesystem discovery:

1. glob `.omo/workers/runs/*-promotion-*.yaml`
2. infer ordering from file names
3. open each file ad hoc

That is acceptable for a first rehearsal, but it is not a stable governance surface. The next slices (approval-gated promotion, promotion diff, promotion dashboards, active-queue explainability) should not depend on filesystem folklore.

## 2. Why this slice now

The natural follow-up after promotion V1 could have gone in two directions:

1. expand promotion behavior again (for example approval-gated promotion)
2. solidify the promotion facts that already exist

The current queue makes the choice clear:

1. all remaining Phase 17 planned packets are `L1` / `human_approval_required: false`
2. approval-gated packets currently sit in deeper future phases (`P19+`, `P21+`, `P24+`)
3. so an approval-required promotion slice would mostly add mechanics without a real near-term rehearsal candidate

Because of that, the smallest correct next step is to solidify promotion facts first.

## 3. Goals

This design should:

1. create one canonical promotion history surface for operators and future automation
2. keep raw promotion envelopes in `.omo/workers/runs/` as the truth source
3. derive a stable `latest` / `prior` / ordered-history view without hand-sorting filenames
4. support the existing ORPHANED rehearsal envelope immediately
5. stay narrow enough for one implementation plan

## 4. Non-goals

This design does not:

1. redesign the promotion workflow itself
2. add approval-required promotion execution yet
3. add promotion diff / burndown / trend semantics
4. add bulk promotion of multiple packets
5. make `state/system.yaml` the full promotion history source
6. mutate or rewrite existing immutable promotion envelopes

## 5. Approaches considered

### A. Productize the full promotion CLI immediately

Behavior:

1. add `promotion-list`, `promotion-show`, `promotion-diff`, `promotion-history`, and maybe rollback/read APIs now

Pros:

- comprehensive UX on day one
- less likely to need new subcommands later

Cons:

- too much scope for the current moment
- mixes discovery, analytics, and governance behavior into one slice
- would force design decisions on diff/history semantics before we need them

This approach is deferred.

### B. Recommended: add one explicit history materialization surface

Behavior:

1. keep promotion envelopes immutable in `.omo/workers/runs/`
2. add one explicit command to scan them and materialize a canonical history packet
3. write one YAML surface plus one Markdown operator view

Pros:

- minimal new behavior
- immediately useful for the existing ORPHANED promotion
- gives later slices a stable resolver surface instead of raw globbing

Cons:

- still requires a separate future slice for richer history analytics
- operators must refresh the surface explicitly in Version 1

### C. Put promotion history directly into `state/system.yaml`

Behavior:

1. extend `state/system.yaml` with promotion counts, latest promotion metadata, and maybe full history

Pros:

- one less file tree to read
- state sync already exists

Cons:

- overloads state with detailed delivery facts
- encourages future slices to treat global state as an analytics database
- makes history retention and ordering rules harder to reason about

This approach is rejected.

## 6. Recommended design

Use **Approach B**.

The core decision is:

> add one explicit promotion-history materializer under the existing `task` CLI that scans immutable promotion envelopes, derives a canonical ordered history surface, and writes `.omo/workers/promotion/current.yaml` plus `.md`.

This is the smallest correct next step because:

1. it turns one-off raw artifacts into a stable governance surface
2. it avoids coupling promotion detail into global state
3. it creates a clean base for later approval/diff/reporting slices

## 7. Architecture

### 7.1 Stay inside `scripts/omo_worker.py task`

Do not create a new top-level CLI.

Add one new read-side command:

1. `python3 scripts/omo_worker.py task promotion-history --omo-dir .omo`

Why this boundary:

1. promotion mutation already lives under `task`
2. the history surface is about task-promotion governance, not generic worker dispatch
3. a single read-side subcommand is enough for Version 1

### 7.2 Raw envelopes remain the truth source

Immutable envelopes under `.omo/workers/runs/*-promotion-*.yaml` remain the authoritative fact records.

The new history surface is:

1. derived
2. refreshable
3. allowed to be regenerated from raw envelopes

This matches the existing pattern already used in debt reporting history.

### 7.3 Add a dedicated derived surface under `.omo/workers/promotion/`

Write:

1. `.omo/workers/promotion/current.yaml`
2. `.omo/workers/promotion/current.md`

Version 1 does **not** need immutable history snapshots under `runs/`. The immutable source already exists in `workers/runs/`.

### 7.4 Canonical YAML contract

`current.yaml` should look like:

```yaml
generated_at: "<ISO8601>"
latest_promotion_id: "ORPHANED-TASKS-STRUCTURED-REGISTRY-promotion-2026-06-03T00-00-00Z"
latest_promotion_ref: ".omo/workers/runs/ORPHANED-TASKS-STRUCTURED-REGISTRY-promotion-2026-06-03T00-00-00Z.yaml"
prior_promotion_id: null
prior_promotion_ref: null
promotion_count: 1
promotions:
  - promotion_id: "ORPHANED-TASKS-STRUCTURED-REGISTRY-promotion-2026-06-03T00-00-00Z"
    promotion_ref: ".omo/workers/runs/ORPHANED-TASKS-STRUCTURED-REGISTRY-promotion-2026-06-03T00-00-00Z.yaml"
    task_id: "ORPHANED-TASKS-STRUCTURED-REGISTRY"
    promoted_at: "2026-06-03T00:00:00Z"
    promoted_by: "copilot-cli"
    task_ref_before: ".omo/tasks/planned/ORPHANED-TASKS-STRUCTURED-REGISTRY.yaml"
    task_ref_after: ".omo/tasks/active/ORPHANED-TASKS-STRUCTURED-REGISTRY.yaml"
    approval_required: false
    approval_ref: null
    target_phase: 17
```

Rules:

1. entries are ordered newest-to-oldest by `promoted_at`
2. `latest_*` points to the first entry
3. `prior_*` points to the second entry or `null`
4. every entry is a compact projection of the raw envelope, not a second full copy

### 7.5 Markdown view is operator-facing, not truth-facing

`current.md` should be a compact readable summary:

```md
# Task Promotion History

Generated at: 2026-06-03T00:00:00Z
Latest promotion: ORPHANED-TASKS-STRUCTURED-REGISTRY-promotion-2026-06-03T00-00-00Z
Prior promotion: none

## Promotion: ORPHANED-TASKS-STRUCTURED-REGISTRY-promotion-2026-06-03T00-00-00Z

task_id=ORPHANED-TASKS-STRUCTURED-REGISTRY
promotion_ref=.omo/workers/runs/ORPHANED-TASKS-STRUCTURED-REGISTRY-promotion-2026-06-03T00-00-00Z.yaml
task_ref_after=.omo/tasks/active/ORPHANED-TASKS-STRUCTURED-REGISTRY.yaml
approval_required=no
target_phase=17
```

The Markdown file is for navigation and review only. YAML remains the canonical derived surface.

### 7.6 Materialization is explicit in Version 1

Version 1 should **not** silently auto-refresh promotion history from `promote-apply`.

Instead:

1. `task promotion-history` is the explicit materializer
2. operators can run it after one or more promotions
3. the current ORPHANED envelope can be backfilled immediately by running the command once

Why keep it explicit:

1. smaller implementation
2. easier to verify and debug
3. avoids mixing mutation and analytics refresh in the same path

### 7.7 Fail closed on malformed envelope input

If a promotion envelope is malformed or missing required fields, the materializer must exit non-zero and refuse to write a partial `current.yaml`.

Required fields for ingestion:

1. `promotion_id`
2. `task_id`
3. `promoted_at`
4. `promoted_by`
5. `task_ref_before`
6. `task_ref_after`
7. `approval.required`
8. `approval.approval_ref`
9. `phase_gate.target_phase`

This prevents later slices from quietly building on incomplete promotion facts.

## 8. Data flow

The intended Version 1 flow is:

1. operator runs `python3 scripts/omo_worker.py task promotion-history --omo-dir .omo`
2. the command scans `.omo/workers/runs/*-promotion-*.yaml`
3. each envelope is loaded and validated for the compact history contract
4. entries are sorted newest-to-oldest by `promoted_at`
5. `.omo/workers/promotion/current.yaml` and `.md` are written atomically

This makes promotion history discoverable without making raw run files the user-facing read surface.

## 9. Error handling

History generation must fail closed on ambiguity.

Examples:

1. malformed YAML -> reject
2. missing required promotion fields -> reject
3. duplicate `promotion_id` values -> reject
4. invalid `promoted_at` timestamp -> reject
5. no promotion envelopes present -> write a valid empty surface, not a command failure

The empty-surface case should look like:

```yaml
generated_at: "<ISO8601>"
latest_promotion_id: null
latest_promotion_ref: null
prior_promotion_id: null
prior_promotion_ref: null
promotion_count: 0
promotions: []
```

## 10. Testing

The implementation plan should include tests for:

1. empty history renders a valid zero-count surface
2. the ORPHANED rehearsal envelope is ingested into `current.yaml` correctly
3. multiple promotion envelopes are sorted newest-to-oldest by `promoted_at`
4. malformed envelope input fails closed and does not write partial output
5. docs record the new `task promotion-history` workflow

## 11. Risks and mitigations

### Risk 1: derived history drifts from raw promotion truth

Mitigation:

1. raw envelopes remain immutable truth
2. the history surface is always regenerable
3. the materializer projects only a compact subset of fields

### Risk 2: future slices start reading `state/system.yaml` instead of the promotion surface

Mitigation:

1. keep detailed promotion facts out of `state/system.yaml`
2. document `.omo/workers/promotion/current.yaml` as the canonical read surface

### Risk 3: Version 1 history surface grows into analytics too early

Mitigation:

1. keep only `latest`, `prior`, `count`, and ordered entries
2. explicitly defer diff/trend/reporting semantics

## 12. Decision summary

The approved default direction is:

1. do not expand promotion behavior again yet
2. do not overload `state/system.yaml`
3. add one explicit `task promotion-history` materializer
4. write `.omo/workers/promotion/current.yaml` + `.md`
5. use raw promotion envelopes in `workers/runs/` as the immutable truth source

That is the smallest slice that turns promotion from "a file move with an artifact" into a reusable governance fact surface.
