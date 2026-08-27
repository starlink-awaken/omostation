---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P56 R2: 历史能力/过程/治理/参考/愿景文档批量归档, 当前活跃文档以各面 INDEX/SSOT 为准"
---
# Debt review action packet design

Date: 2026-06-02
Status: approved-by-default baseline (user unavailable; proceeded with recommended option)
Scope: turn the existing `.omo` debt review queue into an explicit operator action packet that recommends the next governance action per debt item without introducing a workflow state machine or automatic mutation

## 1. Context

The Workspace now has a working debt cadence layer:

1. `.omo/debt/items/*.yaml` remain canonical debt truth
2. `.omo/debt/review-queue/current.yaml` exposes due-now, escalation, upcoming, and unscheduled work
3. `.omo/debt/reviews/current.md` gives a human-readable review packet
4. stale-evidence detection and priority ordering are already implemented

That means the next bottleneck is no longer visibility. It is actionability.

The current queue and review pack still leave an operator with a repeated follow-up question:

> “I can see that this item is due or escalated — but what is the next governance action I should take right now?”

In the current output:

- due-now items and escalation candidates are visible
- stale evidence is visible
- unscheduled items are visible

But the system still does not explicitly transform those signals into a bounded, operator-facing action surface such as:

- revalidate this item now
- reschedule this item now
- escalate this item now
- continue mitigation and review later

The next slice should therefore stay on the read-model side and make the queue executable for humans before introducing timers, daemons, or a larger workflow engine.

## 2. Goals

This design should:

1. generate an explicit next-action packet from the current debt review queue
2. keep `.omo/debt/items/*.yaml` as the only mutable debt truth
3. tell an operator what action class each item belongs to right now
4. surface the suggested command or action envelope needed to progress each item
5. preserve existing queue and review-pack outputs rather than replacing them
6. stay small enough to fit as the next bounded debt-governance slice

## 3. Non-goals

This design does not:

1. add automatic mutation during refresh
2. introduce background scheduling or cron-like automation
3. add a persisted review state machine
4. replace the existing review queue as the generic cadence surface
5. redesign debt scoring, entropy formulas, or gate semantics

## 4. Approaches considered

### A. Recommended: separate action packet derived from the queue

Add a new generated surface that takes the review queue as input and produces operator-facing action lanes plus suggested commands.

Pros:

- cleanly separates “what is due?” from “what should I do next?”
- keeps queue logic and action logic distinct
- easiest to extend later into automation without mutating current debt truth

Cons:

- adds one more generated output surface
- requires a second layer of read-model rules

### B. Expand the existing review pack only

Keep all action guidance inside `.omo/debt/reviews/current.md` without a new structured output.

Pros:

- minimal file growth
- cheapest short-term implementation

Cons:

- harder for tooling to consume
- mixes generic cadence reporting with action routing
- weak foundation for later automation

### C. Persist review sessions as first-class state

Create review-session objects that track assignment, action state, deferrals, and decisions.

Pros:

- strongest long-term workflow model
- good fit for collaboration later

Cons:

- too large for the next iteration
- prematurely introduces mutable workflow state

## 5. Recommended design

Use **Approach A**.

The core decision is:

> The next increment should add an action packet that converts queue signals into explicit next-action lanes and suggested commands, while keeping all source-of-truth state in the debt items and existing CLI actions.

This keeps the layering clean:

1. debt items = canonical truth
2. review queue = cadence/readiness surface
3. action packet = operator next-step surface

## 6. Architecture

### 6.1 Canonical truth remains unchanged

Canonical editable truth stays:

- `.omo/debt/registry.yaml`
- `.omo/debt/items/*.yaml`

No action packet entry becomes a thing operators edit directly.

### 6.2 Queue remains the input contract

`.omo/debt/review-queue/current.yaml` remains the generic queue contract.

Its job continues to be:

- classify due-now work
- classify escalation candidates
- classify upcoming work
- expose summary counts

### 6.3 New generated action packet

Add a new generated surface:

- `.omo/debt/action-packet/current.yaml`

Optional human-readable companion:

- `.omo/debt/action-packet/current.md`

Role:

- transform queue signals into explicit recommended next actions
- group work into operator triage lanes
- expose suggested command invocations using existing debt CLI actions

## 7. Action model

The action packet should group open items into lanes such as:

1. `revalidate_now`
2. `schedule_now`
3. `escalate_now`
4. `continue_mitigation`
5. `watch_only`

### 7.1 `revalidate_now`

Use when:

- the item is stale-evidence flagged
- and it is currently due or escalated

Suggested command shape:

- `python3 scripts/omo_debt.py revalidate --omo-dir .omo --id <ID> --reviewed-at <ISO8601>`

### 7.2 `schedule_now`

Use when:

- the item is open
- and has no `next_review_at`

Suggested command shape:

- `python3 scripts/omo_debt.py schedule --omo-dir .omo --id <ID> --next-review-at <ISO8601>`

### 7.3 `escalate_now`

Use when:

- the item is overdue beyond threshold
- or is gate-level and overdue
- or is critical and overdue

Suggested command shape:

- `python3 scripts/omo_debt.py escalate --omo-dir .omo --id <ID> --gate-level gate`

### 7.4 `continue_mitigation`

Use when:

- the item is already `in_progress` or `mitigated`
- and still appears in due-now or escalation work

Suggested action:

- keep the existing mitigation owner engaged
- then revalidate or reschedule after material progress

### 7.5 `watch_only`

Use when:

- the item is upcoming but not yet due
- or due but not yet deserving action stronger than review awareness

Suggested action:

- leave the item in the cadence surface without triggering mutation now

## 8. Action packet entry shape

Each action packet entry should include at least:

- `id`
- `title`
- `owner`
- `severity`
- `gate_level`
- `current_lane`
- `recommended_action`
- `reason`
- `suggested_command`
- `next_review_at`
- `stale_evidence`
- `overdue_by`

The packet should not duplicate full item history or full evidence lists.

## 9. Routing rules

Use a deterministic first-match routing model:

1. if item is unscheduled → `schedule_now`
2. else if stale-evidence and due/escalated → `revalidate_now`
3. else if escalation candidate and `gate_level != gate` → `escalate_now`
4. else if lifecycle state is `in_progress` or `mitigated` and due → `continue_mitigation`
5. else → `watch_only`

This ordering is important because the packet must recommend one primary next action per item.

In particular, `revalidate_now` has higher precedence than `escalate_now` because stale evidence must be refreshed before the next gate decision is treated as trustworthy.

## 10. Output design

### 10.1 YAML packet

`action-packet/current.yaml` should include:

- `generated_at`
- `defaults`
- `lanes`
- `summary`

`lanes` should map lane name to ordered entries.

### 10.2 Markdown packet

`action-packet/current.md` should include:

1. `## Revalidate Now`
2. `## Schedule Now`
3. `## Escalate Now`
4. `## Continue Mitigation`
5. `## Watch Only`

Each entry should include:

- id
- reason
- suggested command

## 11. CLI and refresh behavior

Keep `python3 scripts/omo_debt.py refresh --omo-dir .omo --now 2026-06-10T00:00:00Z` as the generator.

Extend refresh to additionally generate:

1. `.omo/debt/action-packet/current.yaml`
2. `.omo/debt/action-packet/current.md`

Refresh must still remain read-only with respect to debt truth.

## 12. Error handling and policy

1. If action routing depends on invalid timestamps, refresh should fail loudly
2. If a suggested command cannot be made specific, the packet should still emit the lane and a human-readable reason
3. Closed items must never appear in active action lanes
4. Ownerless items should remain visible as `unowned`

## 13. Testing and verification

The next implementation plan should cover:

1. pure routing tests for lane assignment
2. command-string generation tests
3. refresh output tests for YAML + Markdown action packet generation
4. docs regression for `.omo/AGENT.md` if the action packet becomes part of operator guidance
5. canonical `bash bin/verify-omo.sh` after implementation

## 14. Success criteria

This design is successful when:

1. operators can refresh debt outputs and see a primary next action for each open item
2. the packet distinguishes revalidation, scheduling, escalation, mitigation continuation, and watch-only work
3. queue and action packet stay derived from the same underlying debt truth
4. no automatic mutation or workflow state machine is introduced
5. the next debt-governance slice increases actionability without reopening cadence architecture
