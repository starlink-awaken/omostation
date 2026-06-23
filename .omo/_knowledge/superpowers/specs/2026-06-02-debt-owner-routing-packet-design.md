---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P56 R2: 历史能力/过程/治理/参考/愿景文档批量归档, 当前活跃文档以各面 INDEX/SSOT 为准"
---
# Debt owner routing packet design

Date: 2026-06-02
Status: approved-by-default baseline (user requested continuation; proceeded with the recommended bounded slice)
Scope: turn the existing `.omo` debt action packet into an owner-routed execution surface that groups work by owner, preserves one primary next action per item, and adds execution-safe command guidance without introducing mutable workflow state or delivery automation

## 1. Context

The Workspace now has a working debt-governance read-model stack:

1. `.omo/debt/items/*.yaml` remain canonical debt truth
2. `.omo/debt/review-queue/current.yaml` exposes cadence and escalation readiness
3. `.omo/debt/action-packet/current.yaml` exposes one primary next action per item
4. refresh stays read-only with respect to debt truth

That means the current bottleneck is no longer visibility and no longer basic action classification.

The real current output shows:

1. all 9 active debt items currently land in `revalidate_now`
2. those 9 items are split across 4 owners:
   - `sharedbrain-governance`: 4
   - `omo-governance`: 3
   - `platform-governance`: 1
   - `commerce-governance`: 1
3. the action packet still reads like a single global operator console rather than an execution surface that tells each owner exactly what belongs to them

That creates the next operator question:

> “I can see the next action, but which owner should actually work which set of items, and what packet should they act from?”

There are also two tightly-coupled issues that become more important once work is routed to owners:

1. `revalidate_now` commands currently embed the packet generation timestamp literally, which is unsafe if the packet is executed later
2. items with `last_reviewed_at: null` should not be presented exactly like ordinary periodic revalidation work

The next slice should therefore stay on the read-model side, add explicit owner routing, and tighten the operator command contract before introducing delivery, approval, or mutable assignment state.

## 2. Goals

This design should:

1. group the current action packet into deterministic owner-facing routing sections
2. preserve one primary next action per item rather than reintroducing action ambiguity
3. tell each owner what their current debt workload is and in what order to look at it
4. add execution-safe command guidance for owner-facing packets
5. distinguish never-reviewed work from periodic revalidation work
6. remain fully derived from existing debt truth, review queue, and action packet state
7. stay small enough to be the next bounded debt-governance slice

## 3. Non-goals

This design does not:

1. introduce mutable assignment state such as `acknowledged_at`, `assigned_to`, or packet status
2. deliver packets over Slack, email, webhooks, or any other transport
3. add approval workflows, deferral workflows, or review-session state machines
4. change debt scoring, entropy formulas, or canonical debt item ownership fields
5. replace the action packet as the owner-neutral next-action surface
6. split team owners into sub-owners or infer individuals from team labels

## 4. Approaches considered

### A. Recommended: owner routing packet derived from the action packet

Add one more derived surface that groups action-packet entries by owner and highlights owner-local execution order, summaries, and attention flags.

Pros:

- directly addresses the real current bottleneck: actionability is global, but execution responsibility is per owner
- preserves the current layering cleanly: debt truth -> queue -> action packet -> owner routing
- stays read-only and low-risk
- creates a natural bridge to later delivery or approval workflows without forcing them now

Cons:

- adds another generated output layer
- requires a small command-contract tightening so routed commands stay safe to run later

### B. Action-campaign summary only

Keep a single global campaign view grouped by lane and severity, but add higher-level summaries rather than owner routing.

Pros:

- cheaper than owner routing
- useful for governance leads who want a portfolio-level picture

Cons:

- does not solve the current “who acts on what” problem
- still leaves owners translating a global packet into local work manually

### C. Persisted review sessions or assignment state

Add mutable workflow objects that track assignees, acknowledgements, deferrals, and progress.

Pros:

- strongest long-term collaboration model
- enables later automation and accountability workflows

Cons:

- too large for the next slice
- crosses from read model into mutable workflow state
- requires new concurrency, lifecycle, and SSOT decisions before it is safe

## 5. Recommended design

Use **Approach A**.

The core decision is:

> The next increment should add an owner routing packet that is fully derived from the current action packet, groups entries by owner, and provides execution-safe command guidance plus lightweight attention flags, while keeping canonical debt truth and workflow state unchanged.

This keeps the layering coherent:

1. debt items = canonical truth
2. review queue = cadence/readiness surface
3. action packet = owner-neutral next-action surface
4. owner routing packet = owner-facing execution surface

## 6. Architecture

### 6.1 Canonical truth remains unchanged

Canonical editable truth stays:

- `.omo/debt/registry.yaml`
- `.omo/debt/items/*.yaml`

No owner routing entry is ever hand-edited.

### 6.2 Action packet remains the routing input

The owner routing packet should take `.omo/debt/action-packet/current.yaml` as its direct input contract.

Its job is not to re-decide the primary lane for each item.

Its job is to:

1. group items by `owner`
2. preserve the existing primary lane per item
3. add owner-local summaries and attention flags
4. emit safer execution guidance for routed work

### 6.3 New generated owner-routing surface

Add new generated outputs:

- `.omo/debt/owner-routing/current.yaml`
- `.omo/debt/owner-routing/current.md`

The YAML is the machine-readable owner routing contract.

The Markdown file is the human-readable execution packet for operators and governance leads.

### 6.4 Registry discoverability

Extend the debt registry with:

- `owner_routing_ref: .omo/debt/owner-routing/current.yaml`

The Markdown companion remains a convention beside the YAML, as with other generated surfaces.

## 7. Owner routing model

The owner-routing YAML should include:

1. `generated_at`
2. `source_action_packet_ref`
3. `defaults`
4. `owners`
5. `summary`

`owners` should be an ordered list of owner packets.

Each owner packet should include at least:

- `owner`
- `summary`
- `entries`

Each owner entry should include at least:

- `id`
- `title`
- `owner`
- `primary_lane`
- `recommended_action`
- `reason`
- `priority_flags`
- `command_template`
- `shell_command`
- `next_review_at`
- `last_reviewed_at`
- `stale_evidence`
- `overdue_by`
- `gate_level`
- `severity`

The routing packet should not duplicate full history, full evidence lists, or full mitigation refs.

## 8. Ordering and grouping rules

### 8.1 Owner ordering

Owners should be ordered by:

1. highest-risk item they currently own
2. total routed item count descending
3. owner name ascending

Highest-risk item ranking should prefer:

1. any owner with `gate_attention`
2. then critical severity
3. then more `revalidate_now`
4. then greater overdue duration

### 8.2 Entry ordering inside each owner

Entries inside an owner packet should preserve the current action-packet priority order:

1. primary lane priority
2. gate level
3. severity
4. overdue duration descending
5. debt id

Primary lane priority should be:

1. `revalidate_now`
2. `schedule_now`
3. `escalate_now`
4. `continue_mitigation`
5. `watch_only`

## 9. Attention-flag rules

The owner routing packet keeps one primary action per item and adds secondary attention flags to prevent important context from being hidden.

Use the following derived flags:

1. `initial_review_required`
   - when `last_reviewed_at` is missing
2. `gate_attention`
   - when `gate_level == gate`
3. `escalation_watch`
   - when the item is overdue beyond `escalation_threshold_days` but the primary lane is still `revalidate_now`
4. `active_mitigation`
   - when the primary lane is `continue_mitigation`

These flags do not create extra lanes and do not replace the primary action.

They exist to preserve the “one primary next step” rule while still surfacing operational nuance.

## 10. Command guidance policy

### 10.1 Problem being fixed

Owner-routed packets must not embed a stale literal review timestamp that later gets written as if it were the real review time.

### 10.2 Required command fields

For owner-routed entries, emit two execution fields:

1. `command_template`
   - a literal template using placeholders such as `<RUN_AT>`
2. `shell_command`
   - a directly runnable shell example for humans

For `revalidate_now`, the fields should look like:

- `command_template`: `python3 scripts/omo_debt.py revalidate --omo-dir .omo --id <ID> --reviewed-at <RUN_AT>`
- `shell_command`: `python3 scripts/omo_debt.py revalidate --omo-dir .omo --id <ID> --reviewed-at $(date -u +%Y-%m-%dT%H:%M:%SZ)`

For `schedule_now`, the fields should be:

- `command_template`: `python3 scripts/omo_debt.py schedule --omo-dir .omo --id <ID> --next-review-at <NEXT_REVIEW_AT>`
- `shell_command`: a directly runnable command that uses the packet's deterministic recommended next-review timestamp

For non-CLI actions such as `continue_mitigation`, `shell_command` should be a human-readable `manual: ...` instruction rather than a fake executable command.

### 10.3 Action-packet compatibility

The implementation should extend the action packet to emit execution-safe command metadata and then reuse that metadata from owner routing, because the unsafe timestamp issue is not unique to owner routing.

## 11. Markdown output design

`owner-routing/current.md` should start with a global summary:

1. generated time
2. owner count
3. total routed items
4. counts by primary lane

Then render one section per owner:

1. `## Owner: <owner>`
2. short summary line with total items and lane counts
3. grouped entries under subsections:
   - `### Revalidate Now`
   - `### Schedule Now`
   - `### Escalate Now`
   - `### Continue Mitigation`
   - `### Watch Only`

Each entry should include:

- debt id
- reason
- attention flags
- shell command or human-readable action text

If an owner has no items in a subsection, that subsection should be omitted to keep the Markdown compact.

## 12. Refresh behavior

Keep `python3 scripts/omo_debt.py refresh --omo-dir .omo --now 2026-06-10T00:00:00Z` as the generator entrypoint.

Extend refresh to additionally generate:

1. `.omo/debt/owner-routing/current.yaml`
2. `.omo/debt/owner-routing/current.md`

Refresh must remain read-only with respect to debt truth.

## 13. Error handling and policy

1. ownerless entries must remain visible as `unowned`
2. closed items must never appear in owner-routing outputs
3. if an item has an unknown primary lane, refresh should fail loudly rather than silently bucket it
4. if command templates cannot be made specific, the packet should still emit a human-readable action reason
5. `initial_review_required` must be surfaced whenever `last_reviewed_at` is missing

## 14. Testing and verification

The implementation plan should cover:

1. pure owner-grouping tests for `scripts/omo_debt_owner_routing.py`
2. ordering tests for owners and entries
3. attention-flag tests, especially `initial_review_required` and `gate_attention`
4. command-template and shell-command tests for execution-safe revalidation guidance
5. refresh output tests for owner-routing YAML + Markdown generation
6. docs regression for `.omo/AGENT.md`
7. canonical `bash bin/verify-omo.sh`

## 15. Success criteria

This design is successful when:

1. every item in the action packet appears in exactly one owner section in the owner-routing packet
2. owner packets make it obvious what each owner should review now without consulting the global packet first
3. primary lanes remain deterministic and unchanged by owner routing
4. never-reviewed items are visibly distinct from periodic revalidation work
5. revalidation guidance is execution-safe and no longer depends on the packet generation timestamp being the true review time
6. refresh remains fully derived and read-only, with no workflow state machine introduced
