# Debt approval seam design

Date: 2026-06-02
Status: approved-by-default baseline (user requested continuation; user unavailable during clarification, so proceeded with the recommended bounded slice)
Scope: add a minimal approval boundary for high-risk dispatched debt actions, starting with gate-level `revalidate_now` items only, without introducing owner acknowledgements, campaign state, or reporting rollups

## 1. Context

The Workspace debt-governance stack now has a five-layer read model:

1. `.omo/debt/items/*.yaml` remain canonical debt truth
2. `.omo/debt/review-queue/current.yaml` exposes cadence readiness
3. `.omo/debt/action-packet/current.yaml` exposes owner-neutral next actions
4. `.omo/debt/owner-routing/current.yaml` groups work by owner and adds priority flags
5. `.omo/debt/dispatch/current.yaml` plus `runs/<timestamp>.*` create an explicit surfaced handoff artifact with frozen commands

That means the current bottleneck is no longer “what should happen next?”, no longer “who owns this?”, and no longer “has this packet been formally surfaced?”

The real next gap is:

> The system can now surface immutable owner-facing dispatch packets, but it still cannot prove that a high-risk dispatched action was explicitly approved before mutating canonical debt truth.

Current real signals show why this should stay narrow:

1. the live dispatch packet contains 9 items across 4 owners
2. all 9 are currently `primary_lane: revalidate_now`
3. only one currently dispatched item is `gate_level: gate` (`SB_DECOMPOSITION`)
4. special flags exist (`gate_attention`, `escalation_watch`, `initial_review_required`), but there is still no approval record, no receipt, and no owner-written state

That means the next slice should not jump to full campaign machinery or generic workflow tracking.

It should add the smallest possible control-plane seam that says:

- this high-risk dispatched action was approved at time T
- this approval applies to immutable dispatch run R
- this action may now mutate debt truth

## 2. Goals

This design should:

1. add an explicit approval record for high-risk debt actions
2. bind each approval to an immutable dispatch run, not a floating latest pointer
3. enforce approval at execution time before mutating gate-level debt items
4. stay narrow enough to be the next bounded increment after dispatch
5. keep canonical debt truth and owner routing unchanged

## 3. Non-goals

This design does not:

1. add acknowledgements such as `ack_at`, `received_by`, or `delivery_status`
2. add owner progress tracking, campaign SLA windows, or batch orchestration
3. add trend dashboards or historical reporting rollups
4. require approval for every dispatched debt item
5. write approval metadata back into `.omo/debt/items/*.yaml`
6. add transport automation (Slack, email, webhook)

## 4. Approaches considered

### A. Recommended: per-item approval seam for gate-level revalidate actions

Create a per-item approval record for dispatched gate-level `revalidate_now` actions and enforce it as a pre-flight check inside `python3 scripts/omo_debt.py revalidate`.

Pros:

- matches the current real traffic shape because only one dispatched item is actually gate-level
- adds a true decision record before mutation without introducing workflow sprawl
- gives later campaign/reporting slices a reliable control-plane event to build on
- keeps approval semantics explicit and auditable because each record points at a dispatch run artifact

Cons:

- introduces one more operator step for gate items
- adds a small approval directory and one extra CLI command

### B. Approve an entire dispatch run at once

Allow one approval record for the whole latest dispatch packet.

Pros:

- simpler to describe
- fewer artifacts

Cons:

- over-approves low-risk items that should not need control-plane friction
- couples approval to 9 items even though only 1 item currently justifies it
- makes future per-item audit harder because the approval unit is too coarse

### C. Skip approval and do campaign/reporting first

Move directly to campaign orchestration or reporting after dispatch.

Pros:

- adds visible management surfaces quickly
- may feel more operationally useful at first glance

Cons:

- campaign/reporting would mostly summarize state without adding a new decision boundary
- there is still no explicit authorization record for the one gate-level action that matters
- risks creating mutable status layers before the control seam exists

## 5. Recommended design

Use **Approach A**.

The core decision is:

> The next increment should add a minimal approval seam for gate-level dispatched revalidation actions only, implemented as per-item approval records bound to immutable dispatch runs and enforced by a pre-flight guard in `omo_debt.py revalidate`, while leaving campaign, acknowledgements, and reporting for later slices.

This sequencing is correct because:

1. dispatch already solved the surfaced-handoff boundary
2. only gate-level items currently justify stronger governance
3. campaign/reporting need a decision record if they are going to mean more than summary decoration

## 6. Architecture

### 6.1 Canonical truth remains unchanged

Canonical editable debt truth stays:

- `.omo/debt/registry.yaml`
- `.omo/debt/items/*.yaml`

Approval artifacts are not canonical debt truth.

### 6.2 Approval records bind to immutable dispatch runs

Approval must point to:

- `.omo/debt/dispatch/runs/<timestamp>.yaml`

Approval must not point to:

- `.omo/debt/dispatch/current.yaml`

If approval were tied to `current.yaml`, a later dispatch could silently change what was approved.

### 6.3 Approval scope stays item-local

Approval artifacts should live under:

- `.omo/debt/approvals/<ITEM_ID>/current.yaml`
- `.omo/debt/approvals/<ITEM_ID>/records/<timestamp>.yaml`

`current.yaml` is the latest approval pointer for that item.

`records/<timestamp>.yaml` is the immutable history for that item.

This keeps the seam small, item-local, and easy to enforce in CLI code.

### 6.4 New command boundary

Keep refresh and dispatch as:

- `python3 scripts/omo_debt.py refresh --omo-dir .omo --now 2026-06-10T00:00:00Z`
- `python3 scripts/omo_debt.py dispatch --omo-dir .omo --now 2026-06-10T00:00:00Z`

Add an explicit approval command:

- `python3 scripts/omo_debt.py approve --omo-dir .omo --id SB_DECOMPOSITION --approved-by omo-governance --scope execute_revalidate --approved-at 2026-06-10T01:00:00Z`

Approval should load the latest dispatch packet, find the matching item, resolve its immutable `latest_run_ref`, and create the item-local approval record bound to that run.

## 7. Approval trigger rules

Version 1 should require approval only when all of the following are true:

1. the dispatched item exists in the latest dispatch packet
2. `primary_lane == revalidate_now`
3. `gate_level == gate`

Version 1 should not trigger approval from:

1. `escalation_watch`
2. `initial_review_required`
3. `escalation_candidates`
4. owner name
5. severity alone

This is important because current escalation-like signals are broader than the actual control boundary and would otherwise force approval onto all 9 items.

## 8. Approval artifact model

Each item-local approval `current.yaml` should contain exactly:

1. `item_id`
2. `approved_by`
3. `approved_at`
4. `dispatch_run_ref`
5. `approval_scope`

Where:

- `approval_scope` is an enum with:
  - `execute_revalidate`
  - `promote_lifecycle`
  - `escalate`

Version 1 should use `execute_revalidate` only.

The immutable record under `records/<timestamp>.yaml` should use the same payload.

Version 1 should not add:

- free-form notes
- status transitions
- revoke state
- retry counts
- review comments

## 9. Enforcement rules

### 9.1 Revalidate pre-flight

Before `python3 scripts/omo_debt.py revalidate --id <ITEM>` mutates a debt item, it should:

1. load the debt item
2. determine whether that item requires approval under the trigger rules above
3. if approval is required, load:
   - latest dispatch packet: `.omo/debt/dispatch/current.yaml`
   - approval pointer: `.omo/debt/approvals/<ITEM_ID>/current.yaml`
4. verify that:
   - the approval exists
   - `approval_scope == execute_revalidate`
   - `dispatch_run_ref` matches the latest dispatch packet’s `latest_run_ref`

If any of those checks fail, the command should exit loudly before modifying the debt item.

### 9.2 Approval command validation

The new `approve` command should fail loudly if:

1. the latest dispatch packet does not exist
2. the requested item is not present in the latest dispatch packet
3. the item is not a gate-level `revalidate_now` item
4. an immutable approval record already exists for the requested `approved_at` timestamp

### 9.3 Drift policy

If a new dispatch run is generated after approval and before execution, the prior approval becomes stale automatically because `dispatch_run_ref` no longer matches the latest dispatch packet.

That means gate revalidation must be re-approved against the new dispatch run.

## 10. Markdown and operator surfacing

Version 1 does not need a global approval dashboard.

The operator-visible surfaces can stay minimal:

1. approval YAML artifacts under `.omo/debt/approvals/<ITEM_ID>/`
2. `.omo/AGENT.md` documentation explaining:
   - when approval is required
   - how to run `approve`
   - why approval points to immutable dispatch runs
   - why stale approvals must not auto-carry forward

## 11. Error handling and policy

1. approval enforcement must fail closed, not silently bypass
2. missing approval for a gate-level revalidation must produce a clear error telling the operator which approval file is expected
3. approval should never be inferred from `approved_by` strings inside history notes or dispatch markdown
4. approval artifacts must stay append-only at the record level
5. approval should remain optional for non-gate items in version 1

## 12. Testing and verification

The implementation plan should cover:

1. pure approval-trigger helper tests
2. approval artifact creation tests
3. revalidate guard tests proving gate items fail without approval and pass with matching approval
4. stale-approval mismatch tests when dispatch changes
5. CLI tests for `approve`
6. docs regression for `.omo/AGENT.md`
7. canonical `bash bin/verify-omo.sh`

## 13. Success criteria

This design is successful when:

1. a gate-level dispatched revalidation cannot mutate debt truth without an explicit approval record
2. approval records bind to immutable dispatch runs, not floating latest pointers
3. non-gate revalidation items remain executable without unnecessary governance friction
4. the new control seam stays narrow and does not introduce campaign/acknowledgement state
5. the system is now ready for later campaign/reporting slices to build on top of real authorization events
