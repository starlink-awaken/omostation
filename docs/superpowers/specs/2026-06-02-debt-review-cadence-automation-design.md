# Debt review cadence automation design

Date: 2026-06-02
Status: approved-through-interactive-design
Scope: turn the Workspace `.omo` debt ledger from a visible review backlog into an executable cadence system with deterministic review queues, escalation candidates, and operator-facing review packets

## 1. Context

The Workspace `.omo` debt mechanism now has a solid first-class foundation:

1. `.omo/debt/registry.yaml` is the canonical debt index
2. `.omo/debt/items/*.yaml` are first-class debt objects
3. `state/system.yaml` carries derived debt summary fields rather than the full ledger
4. `scripts/omo_debt.py refresh` produces dashboard and review-pack outputs
5. freshness and stale-evidence logic now account for missing refs, missing review timestamps, and referenced file mtimes newer than `last_reviewed_at`

That means the mechanism is no longer blocked on basic modeling. The current gap is operational:

1. debt review cadence is visible, but not yet actionable as a first-class execution surface
2. the current dashboard can show overdue items, but does not yet produce a structured queue that operators can work from directly
3. all currently registered debts may drift into the same “overdue” bucket without stronger prioritization or escalation routing

The next step is therefore not “more debt metrics.” It is to turn review cadence into an explicit governance output layer that closes the loop between:

- debt item truth
- review timing
- escalation routing
- operator review actions

## 2. Goals

This design should:

1. create a deterministic machine-readable review queue derived from canonical debt items
2. preserve `.omo/debt/items/*.yaml` as the only editable debt truth
3. separate immediate review work from future upcoming work and escalation candidates
4. make review prioritization predictable across owners and future automation
5. keep the solution compatible with the existing `refresh`, `revalidate`, `schedule`, `escalate`, `close`, and `reopen` actions
6. remain small enough to fit naturally into the current debt-governance mechanism without introducing a new heavyweight workflow engine

## 3. Non-goals

This design does not:

1. add a second source of truth for debt state outside `.omo/debt/items/*.yaml`
2. introduce a full review-state workflow such as `queued -> in_review -> approved -> deferred`
3. auto-mutate debt items during refresh
4. redesign debt scoring or entropy formulas beyond what queue classification requires
5. implement notifications, background jobs, or external scheduling integrations in this round

## 4. Approaches considered

### A. Recommended: queue + review packet derived at refresh time

Extend the existing refresh pipeline so it produces:

- a structured review queue
- a richer operator review packet
- deterministic escalation candidate classification

Pros:

- aligns with the current ledger-first architecture
- preserves debt items as the only mutable truth
- keeps operator entrypoints simple
- adds immediate value without a new state machine

Cons:

- queue state is regenerated, not persisted as an independent workflow
- operators still execute actions manually after reading the queue

### B. Workflow state machine first

Introduce a separate review state on each debt item, then build queue views from those states.

Pros:

- strongest long-term workflow model
- supports richer collaboration later

Cons:

- too much complexity for the current maturity level
- would force new lifecycle semantics before the execution surface has stabilized

### C. Policy segmentation first

Start by defining different cadence policies by severity, dimension, and gate level before adding new review surfaces.

Pros:

- can become more accurate long term
- useful for later governance refinement

Cons:

- adds policy complexity before operators have a clean execution queue
- does not directly solve the immediate “all items are overdue, what do I do next?” problem

## 5. Recommended design

Use **Approach A**.

The core design decision is:

> The next debt-governance increment should make cadence executable by generating a deterministic review queue and review packet from ledger truth, while keeping all mutable state in the debt items themselves.

This keeps the current system architecture clean:

1. debt item YAML remains canonical truth
2. queue and review packet are generated read models
3. operators act through existing commands
4. system state remains a compact summary shell

## 6. Architecture

### 6.1 Canonical truth stays unchanged

The canonical truth remains:

- `.omo/debt/registry.yaml`
- `.omo/debt/items/*.yaml`

No queue entry should ever become the thing operators edit by hand. Any actual mutation still happens by updating the underlying debt item through controlled actions.

### 6.2 New generated queue surface

Add a new generated output:

- `.omo/debt/review-queue/current.yaml`

Role:

- machine-readable execution queue for debt review cadence
- compact enough for tooling, scripts, and future automation
- safe to regenerate from canonical debt truth at any time

### 6.3 Existing generated review pack remains

Continue to generate:

- `.omo/debt/reviews/current.md`

Role:

- human-readable operational packet
- review ordering and escalation visibility for operators
- a narrative surface that complements the machine-readable queue

### 6.4 Dashboard remains compact

`.omo/debt/dashboard/current.yaml` should continue to hold only summary metrics and compact top-level cadence indicators such as:

- overdue counts
- overdue ids
- next review queue preview

It should not become the full queue contract.

## 7. Queue model

The review queue should expose at least these top-level sections:

1. `due_now`
2. `upcoming`
3. `escalation_candidates`
4. `unscheduled`
5. `summary`

### 7.1 `due_now`

Contains open debt items whose `next_review_at <= now`.

Purpose:

- tells operators which items should be reviewed immediately

### 7.2 `upcoming`

Contains open debt items whose `now < next_review_at <= now + review_window`.

For this design slice, use a single global default:

- `review_window = 7 days`

Purpose:

- gives the near-term pipeline instead of collapsing everything into overdue work only

### 7.3 `escalation_candidates`

Contains open debt items that deserve stronger governance attention during review.

An item qualifies if any of the following is true:

1. `gate_level == gate` and the item is overdue
2. overdue duration passes the configured escalation threshold
3. the item is both overdue and stale-evidence flagged
4. the item has critical severity and is overdue

For this design slice, use a single global default:

- `escalation_threshold = 3 days overdue`

Later policy segmentation may replace these two fixed defaults with per-dimension or per-severity rules, but this round should not add that policy layer yet.

### 7.4 `unscheduled`

Contains open debt items with no `next_review_at`.

Purpose:

- exposes cadence gaps explicitly instead of silently hiding them from the queue

### 7.5 `summary`

The queue should include compact aggregates such as:

- counts by section
- counts by severity
- counts by gate level
- counts by owner

This is intended for quick routing and later automation, not as a replacement for full metrics.

## 8. Queue entry shape

Each queue entry should include enough context to act without rereading the raw item file first.

Required fields:

- `id`
- `title`
- `owner`
- `severity`
- `dimension`
- `subdimension`
- `lifecycle_state`
- `gate_level`
- `next_review_at`
- `last_reviewed_at`
- `stale_evidence`
- `overdue_by`
- `affected_roots`

Optional derived fields:

- `priority_reason`
- `escalation_reason`

The queue entry should not copy the entire debt item history or full ref lists. It is a routing surface, not a second canonical object.

## 9. Ordering and prioritization

Queue sections must be deterministic.

Recommended sort order within `due_now` and `escalation_candidates`:

1. higher `gate_level`
2. higher `severity`
3. larger overdue duration
4. lexical `id`

Recommended sort order within `upcoming`:

1. earlier `next_review_at`
2. higher `severity`
3. lexical `id`

Recommended sort order within `unscheduled`:

1. higher `severity`
2. lexical `id`

This gives stable outputs and predictable operator expectations across refreshes.

Severity ordering for this round is fixed as:

- `critical > high > medium > low`

## 10. Review packet design

`reviews/current.md` should expand from summary reporting into a stronger operator review packet.

It should contain at least these sections:

1. `## Watchlist`
2. `## Gate Debts`
3. `## Due Now`
4. `## Escalation Candidates`
5. `## Upcoming Window`
6. `## Unscheduled Debts`
7. existing retro sections such as newly registered / closed / drifted / escalated / reopened

Each queue-oriented section should show the key routing reason, for example:

- overdue since timestamp
- escalation trigger
- missing schedule

The packet is still generated output and remains non-editable truth.

## 11. CLI and refresh behavior

### 11.1 Refresh remains the generator

Keep `python3 scripts/omo_debt.py refresh --omo-dir .omo --now ...` as the main generator.

Extend it to produce:

1. dashboard summary
2. review queue YAML
3. review packet Markdown

### 11.2 No implicit mutation

`refresh` must not:

1. auto-escalate items
2. auto-schedule items
3. auto-revalidate items
4. auto-close items

It should classify and surface work, not mutate debt truth silently.

### 11.3 Existing commands remain the action layer

Operators should continue to act through explicit commands such as:

- `schedule`
- `revalidate`
- `escalate`
- `close`
- `reopen`

That preserves auditability and avoids hiding governance decisions inside read-model generation.

## 12. Error handling and policy

### 12.1 Missing `next_review_at`

If an open item has no `next_review_at`, it must appear in `unscheduled`.

It should not be silently excluded from cadence outputs.

### 12.2 Invalid timestamps

If a queue-relevant timestamp is invalid, refresh should fail loudly rather than skip the item.

### 12.3 Missing owner

Items with missing owners may still appear in the queue, but should be marked clearly so ownership gaps remain visible.

For this round, normalize the rendered queue value to:

- `owner: unowned`

### 12.4 Closed items

Closed items should not appear in active queue sections.

### 12.5 Regeneration safety

Because queue and packet are derived outputs, deleting or regenerating them must not lose debt truth.

## 13. Testing and verification

The design should add focused regression coverage for:

1. queue generation and section classification
2. deterministic ordering within each queue section
3. overdue vs upcoming boundary behavior
4. escalation candidate classification
5. unscheduled item surfacing
6. closed-item exclusion
7. invalid timestamp failure behavior
8. packet sections that correspond to queue semantics

Verification should continue to rely on the canonical `.omo` chain after implementation:

1. refresh debt surfaces
2. sync `.omo` state
3. run `bash bin/verify-omo.sh`

## 14. Success criteria

This design is successful when:

1. operators can refresh debt outputs and receive a stable machine-readable review queue
2. the queue separates immediate work, upcoming work, escalation candidates, and unscheduled debt clearly
3. the review packet presents the same routing picture in human-readable form
4. no new editable debt truth is introduced outside `.omo/debt/items/*.yaml`
5. cadence automation improves execution readiness without forcing a heavyweight workflow model
