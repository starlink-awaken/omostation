# Debt dispatch execution seam design

Date: 2026-06-02
Status: approved-by-default baseline (user requested continuation; user unavailable during clarification, so proceeded with the recommended bounded slice)
Scope: add a minimal execution feedback seam for dispatched `revalidate_now` debt work by binding frozen dispatch commands to a specific dispatch run and writing immutable per-run execution records, without introducing campaign objects, acknowledgement workflows, or reporting rollups

## 1. Context

The Workspace debt-governance stack now has these control surfaces:

1. `.omo/debt/items/*.yaml` remain canonical debt truth
2. `.omo/debt/review-queue/current.yaml` exposes cadence readiness
3. `.omo/debt/action-packet/current.yaml` exposes owner-neutral next actions
4. `.omo/debt/owner-routing/current.yaml` groups work by owner and adds priority flags
5. `.omo/debt/dispatch/current.yaml` plus `runs/<timestamp>.*` create immutable surfaced handoff packets
6. `.omo/debt/approvals/<ITEM_ID>/` adds an approval gate for gate-level dispatched `revalidate_now` items

That means the current bottleneck is no longer "what should happen next?", no longer "who owns this?", no longer "was the packet formally surfaced?", and no longer "was the gate item explicitly approved?"

The real next gap is:

> The system can surface and approve dispatched debt work, but it still cannot prove that a specific dispatched command was executed against a specific dispatch run.

The live dispatch packet shows why this should stay narrow:

1. there are 9 dispatched items across 4 owners
2. all 9 are currently `primary_lane: revalidate_now`
3. only one item is `gate_level: gate`, so approval remains intentionally narrow
4. once `revalidate` runs, canonical debt truth changes, but there is no immutable execution record tied back to the dispatch run

Without an execution seam, later campaign or reporting layers would mostly summarize surfaced or approved state without a real "was this run executed?" fact source.

## 2. Goals

This design should:

1. bind dispatched `revalidate` commands to a specific immutable dispatch run
2. fail closed when an operator tries to execute a stale dispatched command
3. write immutable execution records per item per dispatch run
4. keep the slice small enough to be the next bounded increment after approval
5. create the factual substrate that later campaign coordination and reporting can build on

## 3. Non-goals

This design does not:

1. add a first-class campaign object or campaign SLA windows
2. add owner acknowledgements such as `acknowledged_at`, `received_by`, or delivery receipts
3. add dashboards, rollups, burn-down summaries, or completion charts
4. generalize execution tracking for `schedule`, `close`, `reclassify`, or `escalate`
5. rewrite approval semantics or require approval for non-gate items
6. write execution state back into `.omo/debt/items/*.yaml` beyond the existing item mutation

## 4. Approaches considered

### A. Recommended: dispatch-bound execution seam for `revalidate`

Extend dispatched `revalidate` commands so they carry an explicit `dispatch_run_ref`, validate that run at execution time, and write immutable run-scoped execution records.

Pros:

- closes the real feedback gap without inventing new workflow state
- makes stale dispatch commands detectable
- creates a precise fact source for later campaign and reporting layers
- stays aligned with the current traffic shape because all dispatched items are `revalidate_now`

Cons:

- adds one new CLI argument to dispatched `revalidate`
- introduces a new immutable artifact tree for execution records

### B. Campaign coordination first

Add mutable coordination state such as queued / started / blocked / done for dispatched items.

Pros:

- looks operationally rich quickly
- can eventually help with coordination across owners

Cons:

- introduces workflow sprawl before the execution fact seam exists
- risks turning debt governance into a project-management layer
- would still lack a precise immutable execution fact per dispatch run

### C. Reporting / rollup surfaces first

Add summary surfaces over dispatched, approved, and executed work.

Pros:

- visible management surface
- likely useful later

Cons:

- mostly summarizes state rather than adding a new control boundary
- has little value until execution facts exist
- risks amplifying noisy state before the feedback loop is closed

## 5. Recommended design

Use **Approach A**.

The core decision is:

> The next increment should add a dispatch-bound execution seam for `revalidate_now` work by freezing `dispatch_run_ref` into surfaced commands, validating that run during execution, and writing immutable per-run execution records, while explicitly deferring campaign coordination and reporting rollups.

This sequencing is correct because:

1. dispatch already solved surfaced handoff
2. approval already solved the high-risk gate decision boundary
3. the next missing fact is whether a surfaced and optionally approved command actually executed against the intended run
4. campaign and reporting should build on immutable execution facts, not replace them

## 6. Architecture

### 6.1 Frozen dispatch commands become run-specific

The dispatch packet currently freezes `--reviewed-at`, but not the dispatch run identity.

Version 1 should extend dispatched `revalidate` commands to include:

- `--dispatch-run-ref .omo/debt/dispatch/runs/<timestamp>.yaml`

Example surfaced command:

- `python3 scripts/omo_debt.py revalidate --omo-dir .omo --id SB_DECOMPOSITION --reviewed-at 2026-06-10T00:00:00Z --dispatch-run-ref .omo/debt/dispatch/runs/2026-06-10T00-00-00Z.yaml`

This turns the surfaced command into an execution contract against one immutable handoff artifact.

### 6.2 Execution records are run-scoped and immutable

Successful dispatched execution records should live under:

- `.omo/debt/dispatch/executions/<RUN_STAMP>/<ITEM_ID>.yaml`

Where `<RUN_STAMP>` is derived from the immutable dispatch run filename, for example:

- `.omo/debt/dispatch/executions/2026-06-10T00-00-00Z/SB_DECOMPOSITION.yaml`

There is no `current.yaml` for executions in Version 1.

The immutable records are the source of truth for execution feedback.

### 6.3 Campaign remains deferred

This slice intentionally does **not** introduce:

- campaign objects
- progress percentages
- blocked / resumed / deferred states
- owner coordination threads

Later campaign coordination may use execution records as factual inputs, but it must not be required for the execution seam to stay coherent.

## 7. CLI contract

### 7.1 `revalidate` gets an optional run-binding flag

Add:

- `--dispatch-run-ref`

Behavior:

1. if the item is being executed from a surfaced dispatch packet, the command should include `--dispatch-run-ref`
2. if the item currently appears in the latest dispatch packet as `primary_lane: revalidate_now` and no `--dispatch-run-ref` is provided, fail closed and tell the operator to use the surfaced dispatch command
3. if the item does not currently require dispatch-bound execution, legacy local `revalidate` without run binding may continue to work

This preserves compatibility for non-dispatched local maintenance while making surfaced execution explicit and auditable.

### 7.2 Approval remains a separate pre-flight seam

If the dispatched item is gate-level and approval is required:

1. approval must still exist
2. `approval_scope` must remain `execute_revalidate`
3. `approval.dispatch_run_ref` must match the supplied `--dispatch-run-ref`

Approval does not move into execution records; it remains its own control seam.

## 8. Execution record model

Each execution record should contain exactly:

1. `item_id`
2. `dispatch_run_ref`
3. `action`
4. `reviewed_at`

Where:

- `action` is fixed to `revalidate` in Version 1
- `reviewed_at` reuses the operator-supplied `--reviewed-at` value that already mutates canonical debt truth

Version 1 should not add:

- executor identity
- notes
- status transitions
- retry counts
- aggregate completion fields
- cross-item linkage

## 9. Enforcement rules

### 9.1 Dispatch run validation

Before `revalidate` mutates a debt item under dispatch-bound execution, it should:

1. load the supplied dispatch run artifact
2. verify the item exists in that run artifact
3. verify the item is a dispatched `primary_lane: revalidate_now` entry in that run
4. load `.omo/debt/dispatch/current.yaml`
5. verify the supplied `dispatch_run_ref` matches `current.latest_run_ref`

If any of those checks fail, the command must exit loudly before changing the debt item.

This makes stale surfaced commands fail closed after a newer dispatch run supersedes them.

### 9.2 Execution record write

After the existing item mutation succeeds:

1. write the immutable execution record under `.omo/debt/dispatch/executions/<RUN_STAMP>/<ITEM_ID>.yaml`
2. fail closed on accidental overwrite

The execution record is written only after mutation succeeds, so it remains a truthful record of completed execution rather than intent.

### 9.3 Re-execution policy

Version 1 should treat duplicate execution records for the same `(dispatch_run_ref, item_id)` as an error.

If a new dispatch run is generated, the prior run remains immutable history and a new execution record may be written only against the new run.

## 10. Operator surfacing

Version 1 keeps operator surfacing minimal:

1. dispatch YAML and Markdown packets now show explicit `--dispatch-run-ref`
2. execution evidence lives under `.omo/debt/dispatch/executions/<RUN_STAMP>/`
3. `.omo/AGENT.md` should explain:
   - when `--dispatch-run-ref` is required
   - why stale dispatched commands fail closed
   - where execution evidence is written

Version 1 does not need:

- a global execution dashboard
- a campaign summary page
- reporting rollups

## 11. Data flow

The intended flow becomes:

1. `refresh` derives review and action surfaces
2. `dispatch` freezes owner-routed commands into an immutable run packet
3. `approve` records gate approval when required
4. `revalidate --dispatch-run-ref <RUN_REF>` validates dispatch binding and approval
5. canonical debt truth updates
6. immutable execution evidence is written for that run/item pair

That closes the surfaced → approved → executed chain without introducing higher-order workflow machinery.

## 12. Testing strategy

The implementation plan should cover at least:

1. dispatched commands now include `--dispatch-run-ref`
2. `revalidate` fails when a dispatched item omits `--dispatch-run-ref`
3. `revalidate` fails when `--dispatch-run-ref` does not match the latest dispatch run
4. gate items still require matching approval for the same run
5. successful dispatched execution writes one immutable execution record
6. duplicate execution record attempts fail closed
7. `.omo/AGENT.md` documents the new execution seam

## 13. Success criteria

This slice is successful when:

1. surfaced dispatch commands are bound to a specific immutable run
2. stale dispatched `revalidate` commands cannot execute silently
3. each successful dispatched execution produces immutable run-scoped evidence
4. approval semantics remain unchanged for gate items, but compose cleanly with the new execution seam
5. the system is ready for later campaign coordination or reporting to build on real execution facts rather than inferred state
