---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P56 R2: 历史能力/过程/治理/参考/愿景文档批量归档, 当前活跃文档以各面 INDEX/SSOT 为准"
---
# Debt campaign coordination design

Date: 2026-06-02
Status: approved-by-default baseline (user requested continuation; user unavailable during clarification, so proceeded with the recommended bounded slice)
Scope: add a narrow latest-run campaign coordination surface for dispatched debt work by deriving one explicit run-progress view from dispatch, approval, and execution artifacts, without introducing acknowledgements, SLA windows, or cross-run reporting rollups

## 1. Context

The Workspace debt-governance stack now has these layers:

1. `.omo/debt/items/*.yaml` remain canonical debt truth
2. `.omo/debt/review-queue/current.yaml` exposes cadence readiness
3. `.omo/debt/action-packet/current.yaml` exposes owner-neutral next actions
4. `.omo/debt/owner-routing/current.yaml` groups work by owner and priority flags
5. `.omo/debt/dispatch/current.yaml` plus `runs/<timestamp>.*` create explicit surfaced handoff packets
6. `.omo/debt/approvals/<ITEM_ID>/` adds a gate-only approval seam
7. `.omo/debt/dispatch/executions/<RUN_STAMP>/<ITEM_ID>.yaml` records dispatched execution facts

That means the current bottleneck is no longer "what should happen next?", no longer "who owns this?", no longer "was this surfaced?", no longer "was the gate item approved?", and no longer "did a specific dispatched command execute against a specific run?"

The real next gap is:

> The system now has all the facts needed for run-level coordination, but operators still lack one bounded surface that answers: for the latest dispatch run, which items are pending approval, which are ready to execute, and which have already executed?

The live state explains why this should stay narrow:

1. the current dispatch packet still contains 9 `revalidate_now` items across 4 owners
2. only one item is gate-level, so approval remains an exception rather than a general workflow state
3. execution evidence now exists as first-class artifacts, so coordination can be derived instead of hand-maintained
4. campaign/reporting were intentionally deferred until execution facts existed

That means the next slice should not jump to cross-run rollups or receipt workflows.

It should add the smallest possible coordination layer that says:

- for run `R`, these items still need approval
- for run `R`, these items are ready to execute
- for run `R`, these items already executed

## 2. Goals

This design should:

1. derive a run-scoped coordination surface from existing dispatch, approval, and execution facts
2. make the latest dispatch run easy for operators to inspect without reading several artifact trees manually
3. avoid introducing duplicate truth or mutating canonical debt items
4. keep update triggers explicit rather than coupling campaign state to `revalidate`
5. create a clean foundation for later reporting or broader campaign workflow

## 3. Non-goals

This design does not:

1. add owner acknowledgement receipts such as `acknowledged_at` or `received_by`
2. add SLA windows, escalation timers, or overdue campaign alerts
3. add cross-run history charts, burndown metrics, or trend rollups
4. add blocked / resumed / deferred workflow states
5. write status fields back into `.omo/debt/items/*.yaml`
6. auto-regenerate campaign outputs during `approve` or `revalidate`

## 4. Approaches considered

### A. Recommended: explicit latest-run campaign command

Add an explicit `campaign` command that reads the latest dispatch run (or an explicitly provided run ref), derives one run-progress surface, and writes a machine-readable plus Markdown coordination packet.

Pros:

- keeps the coordination layer derived from real facts instead of adding new mutable truth
- gives operators a single bounded surface for the current run
- keeps update timing explicit and auditable
- matches the current traffic shape because all current dispatched items are `revalidate_now`

Cons:

- introduces one more generated surface and one more operator command
- campaign outputs may become stale between executions until regenerated

### B. Latest-run progress plus acknowledgement receipts

Add a coordination surface plus explicit owner receipt state.

Pros:

- seems more operationally complete
- could become useful later if transport or human handoff becomes first-class

Cons:

- adds a new mutable workflow seam before it is needed
- receipt state is not grounded in any existing transport or delivery mechanism
- would expand the slice beyond the current execution-fact gap

### C. Reporting / rollup first

Skip campaign coordination and build reporting over approvals and execution evidence.

Pros:

- visible management surface
- useful later

Cons:

- mostly summarizes state rather than improving run-level operator coordination
- cross-run reporting is premature before a single-run coordination surface exists
- increases pressure to invent aggregation semantics too early

## 5. Recommended design

Use **Approach A**.

The core decision is:

> The next increment should add an explicit `campaign` command that derives a latest-run coordination packet from dispatch, approval, and execution artifacts, classifies each dispatched item into `pending_approval`, `ready_to_execute`, or `executed`, and writes run-scoped current outputs plus a convenience latest pointer, while deferring receipts and cross-run reporting.

This sequencing is correct because:

1. dispatch, approval, and execution seams already define the factual inputs
2. operators still need a bounded "what remains in this run?" surface
3. campaign coordination should be a derived view first, not a new source of truth
4. reporting becomes more meaningful after a run-level coordination surface exists

## 6. Architecture

### 6.1 Explicit command boundary

Add:

- `python3 scripts/omo_debt.py campaign --omo-dir .omo`

Optional:

- `--run-ref .omo/debt/dispatch/runs/<timestamp>.yaml`

Behavior:

1. without `--run-ref`, use `.omo/debt/dispatch/current.yaml` and its `latest_run_ref`
2. with `--run-ref`, derive the campaign packet for that specific dispatch run
3. the command reads existing truth; it does not mutate debt items, approval records, or execution records

This keeps campaign generation explicit, repeatable, and auditable.

### 6.2 Derived surfaces, not duplicate truth

Campaign outputs should be generated under:

- `.omo/debt/campaign/current.yaml`
- `.omo/debt/campaign/current.md`
- `.omo/debt/campaign/runs/<RUN_STAMP>/current.yaml`
- `.omo/debt/campaign/runs/<RUN_STAMP>/current.md`

Design intent:

1. the run-scoped `runs/<RUN_STAMP>/current.*` files preserve the latest known coordination state for that run
2. the top-level `current.*` files are a convenience pointer for the latest run only
3. immutable truth remains in:
   - `dispatch/runs/<timestamp>.*`
   - `approvals/<ITEM_ID>/`
   - `dispatch/executions/<RUN_STAMP>/<ITEM_ID>.yaml`

Campaign outputs are derived coordination views, not canonical truth.

### 6.3 No auto-update coupling

`approve` and `revalidate` must **not** regenerate campaign outputs automatically.

Reasons:

1. campaign is an aggregate coordination view, not an execution side effect
2. explicit regeneration matches the existing architecture pattern (`refresh`, `dispatch`, now `campaign`)
3. this avoids hidden cross-concern coupling inside mutation commands

## 7. Classification model

Every dispatched `revalidate_now` entry in the selected run must classify to exactly one state:

1. `pending_approval`
2. `ready_to_execute`
3. `executed`

Rules:

### 7.1 `pending_approval`

Use when:

1. the dispatch entry is gate-level under the existing approval trigger rule
2. there is no matching approval record for that item and run

Important:

- this is **not** `blocked`
- it means the run has not yet received the required approval fact

### 7.2 `ready_to_execute`

Use when:

1. the item has no execution record for the selected run
2. and either:
   - the item is not gate-level, or
   - the item is gate-level and has a matching approval record

This is the normal "work remains" state for the run.

### 7.3 `executed`

Use when:

1. `.omo/debt/dispatch/executions/<RUN_STAMP>/<ITEM_ID>.yaml` exists
2. and its `dispatch_run_ref` matches the selected run

No additional workflow state is required in Version 1.

## 8. Packet model

The machine-readable campaign packet should contain:

1. `generated_at`
2. `dispatch_run_ref`
3. `run_stamp`
4. `source_dispatch_ref`
5. `summary`
6. `owners`

Where:

### 8.1 `summary`

Should include at least:

1. `owner_count`
2. `total_items`
3. `state_counts`
   - `pending_approval`
   - `ready_to_execute`
   - `executed`

### 8.2 `owners`

Each owner section should include:

1. `owner`
2. `item_count`
3. `state_counts`
4. `entries`

Each entry should preserve operator-relevant fields already present in dispatch, plus:

1. `campaign_state`
2. `dispatch_run_ref`
3. `execution_record_ref` when the item is executed

Version 1 should not add:

- assignee fields
- receipt fields
- retry counters
- SLA metadata
- run-to-run comparisons

## 9. Markdown operator surfacing

The Markdown packet should:

1. state the selected run and generation time
2. show top-level counts for `pending_approval`, `ready_to_execute`, and `executed`
3. group entries by owner
4. within each owner, group entries by campaign state

This keeps the surface aligned with owner routing while making campaign progress easier to scan.

## 10. Error handling

The new `campaign` command should fail loudly if:

1. no dispatch packet exists and no `--run-ref` is provided
2. the selected dispatch run artifact does not exist
3. the selected run artifact is empty
4. the selected run has no dispatched owners or entries

If approval or execution artifacts are missing, that is **not** an error condition by itself; it is normal input for `pending_approval` or `ready_to_execute`.

## 11. Data flow

The intended flow becomes:

1. `refresh` derives review and action surfaces
2. `dispatch` freezes the latest owner-routed run
3. `approve` records gate approval when required
4. `revalidate --dispatch-run-ref <RUN_REF>` records execution evidence
5. `campaign [--run-ref <RUN_REF>]` derives the latest coordination packet from those existing facts

This gives operators a bounded run-progress surface without creating a new mutable workflow core.

## 12. Testing strategy

The implementation plan should cover at least:

1. `campaign` defaults to `dispatch/current.yaml` when `--run-ref` is omitted
2. gate item without matching approval is classified `pending_approval`
3. gate item with matching approval but no execution record is classified `ready_to_execute`
4. non-gate item without execution evidence is classified `ready_to_execute`
5. item with matching execution record is classified `executed`
6. the command writes both run-scoped `runs/<RUN_STAMP>/current.*` outputs and top-level `current.*`
7. `.omo/AGENT.md` documents the campaign command and state meanings

## 13. Success criteria

This slice is successful when:

1. operators can inspect one generated surface and understand the latest run state without manually joining dispatch, approval, and execution artifacts
2. campaign outputs remain derived from existing facts rather than becoming a new source of truth
3. gate approval remains modeled as `pending_approval` until matching approval exists
4. executed items are grounded only in immutable execution records
5. the system is ready for later receipt workflows or reporting layers without having overbuilt them into Version 1
