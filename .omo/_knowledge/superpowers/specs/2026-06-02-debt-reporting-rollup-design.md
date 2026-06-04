# Debt reporting / rollup design

Date: 2026-06-02
Status: approved-by-default baseline (user requested continuation; user unavailable during clarification, so proceeded with the recommended bounded slice)
Scope: add a narrow latest-run debt reporting surface that summarizes dispatch progress for operators and leads by deriving compact rollups from dispatch, approval, and execution facts, without introducing cross-run history, SLA analytics, or new mutable workflow state

## 1. Context

The Workspace debt-governance stack now has these layers:

1. `.omo/debt/items/*.yaml` remain canonical debt truth
2. `.omo/debt/dashboard/current.yaml` summarizes debt health and review cadence
3. `.omo/debt/review-queue/current.yaml` and `.omo/debt/action-packet/current.yaml` expose next work
4. `.omo/debt/owner-routing/current.yaml` groups current work by owner
5. `.omo/debt/dispatch/current.yaml` plus `runs/<timestamp>.*` freeze surfaced handoff packets
6. `.omo/debt/approvals/<ITEM_ID>/` records gate-only approval facts
7. `.omo/debt/dispatch/executions/<RUN_STAMP>/<ITEM_ID>.yaml` records immutable execution facts
8. `.omo/debt/campaign/current.yaml` plus `runs/<RUN_STAMP>/current.yaml` expose run-level coordination state

That means the current missing layer is no longer coordination itself.

The real next gap is:

> operators can see per-item run coordination in campaign, but there is still no compact management-facing rollup that answers: how much of the latest surfaced run is approved, how much is executed, and which owners still carry the remaining work?

This should stay narrow for three reasons:

1. the system currently needs one latest-run progress summary, not a historical analytics program
2. campaign already covers per-item coordination, so reporting should compress that state rather than invent a new workflow
3. cross-run history, burndown, and SLA interpretation would introduce semantics the current governance loop does not yet need

## 2. Goals

This design should:

1. add one explicit latest-run reporting surface for dispatched debt work
2. keep reporting derived from existing dispatch, approval, and execution facts
3. clearly separate debt-health dashboard concerns from run-progress reporting concerns
4. provide compact counts and rates that are easier to scan than the full campaign packet
5. preserve a clean foundation for later cross-run reporting if it becomes necessary

## 3. Non-goals

This design does not:

1. add cross-run trend lines, burndown charts, or historical comparisons
2. add SLA windows, ageing buckets, or deadline forecasting
3. add receipt / acknowledgement workflow
4. mutate canonical debt items, approvals, executions, or campaign outputs
5. make reporting depend on previously generated `campaign/current.yaml`
6. replace the existing debt dashboard or campaign coordination packet

## 4. Approaches considered

### A. Recommended: dedicated latest-run reporting surface derived directly from facts

Add an explicit `report` command that reads the selected dispatch run plus approval and execution artifacts, reuses the existing campaign classification logic in memory, and writes a compact reporting packet.

Pros:

- gives operators and leads a compact run-progress surface without reading the full campaign packet
- avoids a stale `campaign -> report` dependency chain
- keeps reporting derived and explicit
- cleanly separates dashboard, campaign, and reporting responsibilities

Cons:

- introduces one more generated surface and one more operator command
- some fields overlap with campaign summary because the underlying facts are shared

### B. Extend campaign summary only

Do not add a new reporting surface; just add extra rates into `campaign/current.yaml`.

Pros:

- smallest code change
- avoids one extra artifact tree

Cons:

- mixes owner-facing coordination detail with management-facing rollup intent
- keeps one packet trying to serve two audiences
- does not create a clean dedicated reporting boundary for later expansion

### C. Cross-run reporting first

Jump directly to historical run-to-run rollups, trend summaries, or burn-down views.

Pros:

- visible management value
- could become useful later

Cons:

- premature before a single-run reporting seam is stabilized
- forces aggregation semantics across runs too early
- increases the risk of overbuilding a surface not yet grounded in daily operator use

## 5. Recommended design

Use **Approach A**.

The core decision is:

> The next increment should add an explicit `report` command that derives a compact latest-run reporting packet from dispatch, approval, and execution facts, reusing the same run classification logic as campaign in memory while writing a distinct reporting surface for summary counts, coverage rates, completion rates, and owner rollups, and explicitly deferring cross-run history.

This sequencing is correct because:

1. dashboard already answers debt-health and cadence questions
2. campaign already answers per-item run-coordination questions
3. reporting should now answer compact run-progress questions for the latest surfaced packet
4. deriving directly from facts avoids a second stale generated-surface hop

## 6. Architecture

### 6.1 Explicit command boundary

Add:

- `python3 scripts/omo_debt.py report --omo-dir .omo`

Optional:

- `--run-ref .omo/debt/dispatch/runs/<timestamp>.yaml`

Behavior:

1. without `--run-ref`, use `.omo/debt/dispatch/current.yaml` and its `latest_run_ref`
2. with `--run-ref`, derive the reporting packet for that specific dispatch run
3. the command reads existing truth; it does not mutate debt items, approvals, execution records, or campaign outputs

### 6.2 Direct-from-facts derivation

Reporting must not read `campaign/current.yaml` from disk as its input.

Instead it should:

1. load the selected dispatch run
2. resolve matching approval facts per item
3. resolve matching execution facts per item
4. reuse the same classification rules already used by campaign
5. condense that run state into a reporting packet

Implementation note:

- reusing `build_campaign_packet(...)` in memory is acceptable
- reading generated campaign artifacts as the source of truth is not

This keeps reporting aligned with the same facts as campaign while avoiding an avoidable staleness chain.

### 6.3 Distinct generated surfaces

Reporting outputs should be generated under:

- `.omo/debt/reporting/current.yaml`
- `.omo/debt/reporting/current.md`
- `.omo/debt/reporting/runs/<RUN_STAMP>/current.yaml`
- `.omo/debt/reporting/runs/<RUN_STAMP>/current.md`

Design intent:

1. `dashboard/` remains debt-health and cadence summary
2. `campaign/` remains per-owner / per-item coordination state
3. `reporting/` becomes compact run-progress rollup

### 6.4 No auto-update coupling

`approve`, `revalidate`, and `campaign` must **not** regenerate reporting automatically.

Reasons:

1. reporting is an explicit aggregate view, not an execution side effect
2. explicit regeneration matches the existing `refresh` / `dispatch` / `campaign` control pattern
3. hidden coupling between mutation commands and summary surfaces would make operator behavior harder to reason about

## 7. Reporting model

The reporting packet should remain compact.

It should contain:

1. `generated_at`
2. `dispatch_run_ref`
3. `run_stamp`
4. `summary`
5. `owners`

### 7.1 `summary`

`summary` should include at least:

1. `owner_count`
2. `total_items`
3. `state_counts`
   - `pending_approval`
   - `ready_to_execute`
   - `executed`
4. `gate_item_count`
5. `approved_gate_item_count`
6. `approval_coverage_rate`
7. `executed_item_count`
8. `execution_completion_rate`

Rate rules:

1. `approval_coverage_rate = approved_gate_item_count / gate_item_count`
2. if `gate_item_count == 0`, `approval_coverage_rate` should be `1.0`
3. `execution_completion_rate = executed_item_count / total_items`
4. if `total_items == 0`, `execution_completion_rate` should be `0.0`

### 7.2 `owners`

Each owner section should include:

1. `owner`
2. `item_count`
3. `state_counts`
4. `gate_item_count`
5. `approved_gate_item_count`
6. `approval_coverage_rate`
7. `executed_item_count`
8. `execution_completion_rate`

Version 1 should not embed every full dispatch entry again; campaign already serves that purpose.

## 8. Markdown surfacing

The Markdown packet should:

1. state the selected run and generation time
2. show compact top-level summary metrics
3. show top-level rates for approval coverage and execution completion
4. group compact rollups by owner
5. avoid re-listing every command unless a future slice explicitly needs it

This keeps reporting distinct from the more verbose campaign packet.

## 9. Error handling

The new `report` command should fail loudly if:

1. no dispatch packet exists and no `--run-ref` is provided
2. the selected dispatch run artifact does not exist
3. the selected run artifact is empty
4. the selected run has no dispatched owners or entries

Missing approval or execution artifacts are **not** errors by themselves; they are normal input for pending work and incomplete coverage.

## 10. Data flow

The intended flow becomes:

1. `refresh` derives debt-health and work-preparation outputs
2. `dispatch` freezes the latest owner-routed run
3. `approve` records gate approval when required
4. `revalidate --dispatch-run-ref <RUN_REF>` records execution evidence
5. `campaign [--run-ref <RUN_REF>]` derives detailed run coordination
6. `report [--run-ref <RUN_REF>]` derives compact run-progress rollup

This keeps the control plane layered:

1. dashboard = debt health
2. campaign = coordination detail
3. reporting = compact progress rollup

## 11. Testing strategy

The implementation plan should cover at least:

1. `report` defaults to `dispatch/current.yaml` when `--run-ref` is omitted
2. summary counts match campaign classification for the selected run
3. approval coverage is computed correctly for gate items
4. execution completion is computed correctly for all items
5. owner-level rollups compute counts and rates correctly
6. the command writes both run-scoped `runs/<RUN_STAMP>/current.*` outputs and top-level `current.*`
7. `.omo/AGENT.md` documents the reporting command and the distinction from dashboard / campaign
8. canonical verify remains green after the slice lands

## 12. Success criteria

This slice is successful when:

1. operators can inspect one compact generated surface and understand latest-run execution progress without manually scanning the full campaign packet
2. reporting remains derived from dispatch, approval, and execution facts instead of becoming new mutable truth
3. dashboard, campaign, and reporting each answer a distinct governance question
4. the system is ready for later cross-run reporting without overcommitting to historical semantics in Version 1
