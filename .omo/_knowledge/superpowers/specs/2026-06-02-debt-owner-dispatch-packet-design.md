---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P56 R2: 历史能力/过程/治理/参考/愿景文档批量归档, 当前活跃文档以各面 INDEX/SSOT 为准"
---
# Debt owner dispatch packet design

Date: 2026-06-02
Status: approved-by-default baseline (user requested continuation; user unavailable during clarification, so proceeded with the recommended bounded slice)
Scope: turn the current owner-routing packet into an explicit dispatch artifact with frozen commands and immutable run records, without introducing owner acknowledgements, mutable workflow state, or transport automation

## 1. Context

The Workspace now has a four-layer debt-governance read model:

1. `.omo/debt/items/*.yaml` remain canonical debt truth
2. `.omo/debt/review-queue/current.yaml` exposes cadence readiness
3. `.omo/debt/action-packet/current.yaml` exposes owner-neutral next actions
4. `.omo/debt/owner-routing/current.yaml` groups work by owner and adds flags such as `gate_attention`, `escalation_watch`, and `initial_review_required`

That means the current bottleneck is no longer “what should happen next?” and no longer “who owns this?”

The real next gap is:

> The system can derive owner-local execution packets, but it cannot distinguish “this packet exists in the repo” from “this packet was formally surfaced as the current dispatch artifact for owners to act from.”

Two concrete problems follow from that:

1. `owner-routing/current.yaml` is a derived snapshot that gets overwritten on future refresh runs, so it does not establish a durable surfaced handoff moment
2. owner-routing entries still carry both `command_template` and `shell_command`; dispatch should collapse that into one canonical command with timestamps frozen at dispatch time

The current real owner-routing output also shows why this matters now:

1. 9 active debt items are routed across 4 owners
2. all 9 are still in `revalidate_now`
3. only 3 items carry special flags at all (`gate_attention`, `escalation_watch`, `initial_review_required`)

That means the next slice should not add more analysis layers.

It should create an explicit handoff artifact that says:

- this owner-facing packet was dispatched at time T
- here is the frozen command each owner should run from that dispatch
- here is the exact per-owner work surface that was surfaced

## 2. Goals

This design should:

1. create a formal dispatch artifact derived from the latest owner-routing packet
2. freeze dispatch-time commands so the artifact is auditable and reproducible
3. preserve owner grouping, primary lane, and priority flags from owner routing
4. create immutable per-run dispatch records so surfaced handoffs are no longer overwritten history
5. keep canonical debt truth unchanged
6. stay bounded enough to be the next debt-governance slice after owner routing

## 3. Non-goals

This design does not:

1. send packets over Slack, email, webhook, or any external transport
2. add owner acknowledgements such as `ack_at`, `received_by`, or `delivery_status`
3. add approval workflows for escalate/close/reopen
4. add campaign SLAs, retry counts, or progress rollups
5. write any dispatch back-reference into `.omo/debt/items/*.yaml`
6. infer whether an owner acted on a dispatch packet

## 4. Approaches considered

### A. Recommended: explicit dispatch command plus immutable run artifacts

Add a new `dispatch` command that consumes the latest owner-routing packet, freezes the owner-facing commands at `dispatched_at`, and writes both a latest-pointer artifact and immutable run records.

Pros:

- creates the missing surfaced-handoff boundary without mutable owner state
- separates “derive current routing” from “formally dispatch this routing”
- makes dispatch artifacts auditable because the command timestamps are frozen
- prepares a clean seam for future approval or delivery integration

Cons:

- adds a second operator action after refresh
- introduces one more generated surface and a small history directory

### B. Generate dispatch automatically during refresh

Have `refresh` also produce the dispatch packet every time.

Pros:

- cheaper to implement
- fewer commands for operators

Cons:

- collapses observation and dispatch into one step
- cannot distinguish “refreshed” from “surfaced”
- will create a new dispatch artifact on every refresh whether or not the operator intended to dispatch anything

### C. Do approval or campaign orchestration first

Skip dispatch and move straight to approval envelopes or batch/SLA orchestration.

Pros:

- expands governance surface area faster
- useful later once dispatch exists

Cons:

- misordered for the real current bottleneck
- approval has little real traffic right now because `escalate_now` is empty
- campaign rollups add summary without fixing the surfaced-handoff gap

## 5. Recommended design

Use **Approach A**.

The core decision is:

> The next increment should add an explicit debt dispatch packet, produced by a dedicated `dispatch` command from the latest owner-routing artifact, with a frozen `dispatched_at` timestamp, one canonical command per item, and immutable run records, while keeping debt truth and owner workflow state untouched.

This keeps the layering clean:

1. debt items = canonical truth
2. review queue = cadence surface
3. action packet = owner-neutral next-action surface
4. owner routing = owner-local execution surface
5. dispatch packet = formal surfaced handoff artifact

## 6. Architecture

### 6.1 Canonical truth remains unchanged

Canonical editable debt truth stays:

- `.omo/debt/registry.yaml`
- `.omo/debt/items/*.yaml`

Dispatch artifacts never become editable debt truth.

### 6.2 Owner routing remains the dispatch input

The dispatch packet should consume:

- `.omo/debt/owner-routing/current.yaml`

It should not recompute routing logic.

Its job is to:

1. freeze a handoff timestamp
2. freeze one canonical command per routed item
3. persist the surfaced owner envelopes as immutable run records
4. expose the latest dispatch surface through `current.yaml` / `current.md`

### 6.3 New command boundary

Keep refresh as:

- `python3 scripts/omo_debt.py refresh --omo-dir .omo --now 2026-06-10T00:00:00Z`

Add a dedicated dispatch command:

- `python3 scripts/omo_debt.py dispatch --omo-dir .omo --now 2026-06-10T00:00:00Z`

Refresh remains observational.

Dispatch becomes the explicit surfacing step.

### 6.4 New generated outputs

Add:

- `.omo/debt/dispatch/current.yaml`
- `.omo/debt/dispatch/current.md`
- `.omo/debt/dispatch/runs/<timestamp>.yaml`
- `.omo/debt/dispatch/runs/<timestamp>.md`

`current.*` are the latest surfaced dispatch packet.

`runs/<timestamp>.*` are immutable historical run records.

### 6.5 Registry discoverability

Extend the debt registry with:

- `dispatch_ref: .omo/debt/dispatch/current.yaml`

The latest dispatch packet itself should include `latest_run_ref` so tooling can navigate to the immutable run artifact.

## 7. Dispatch packet model

The latest dispatch YAML should include at least:

1. `dispatched_at`
2. `source_owner_routing_ref`
3. `source_owner_routing_generated_at`
4. `latest_run_ref`
5. `owners`
6. `summary`

Each owner envelope should include at least:

- `owner`
- `dispatched_at`
- `item_count`
- `entries`

Each dispatch entry should include at least:

- `id`
- `title`
- `owner`
- `primary_lane`
- `recommended_action`
- `reason`
- `priority_flags`
- `command`
- `next_review_at`
- `last_reviewed_at`
- `overdue_by`
- `gate_level`
- `severity`

The dispatch entry should not include:

- `command_template`
- `shell_command`
- `suggested_command`

Dispatch should collapse the owner-routing command contract into one canonical field: `command`.

## 8. Command freezing rules

### 8.1 Revalidate entries

For `revalidate_now`, dispatch should take the owner-routing `command_template` and substitute:

- `<RUN_AT>` -> `dispatched_at`

Example:

- owner routing template: `python3 scripts/omo_debt.py revalidate --omo-dir .omo --id SB_DECOMPOSITION --reviewed-at <RUN_AT>`
- dispatch command: `python3 scripts/omo_debt.py revalidate --omo-dir .omo --id SB_DECOMPOSITION --reviewed-at 2026-06-10T00:00:00Z`

### 8.2 Schedule entries

For `schedule_now`, dispatch should use the already concrete owner-routing `shell_command`.

### 8.3 Manual lanes

For non-CLI actions such as `continue_mitigation` or `watch_only`, dispatch should carry the owner-routing `shell_command` exactly as-is.

### 8.4 Validation

Dispatch should fail loudly if:

1. a required placeholder such as `<RUN_AT>` remains unresolved
2. a routed item lacks both `command_template` and `shell_command`
3. the frozen command still contains shell-time expansion such as `$(date ...)` for a revalidation dispatch

## 9. Run-record rules

### 9.1 Latest packet

`dispatch/current.yaml` and `dispatch/current.md` should always mirror the latest dispatch run.

### 9.2 Immutable run packet

Each dispatch command invocation should additionally write:

- `.omo/debt/dispatch/runs/<timestamp>.yaml`
- `.omo/debt/dispatch/runs/<timestamp>.md`

The timestamp should be normalized from `dispatched_at` into a filename-safe format such as:

- `2026-06-10T00-00-00Z`

### 9.3 Duplicate timestamp policy

If a dispatch run file already exists for the requested timestamp, the dispatch command should fail loudly rather than silently overwrite the historical artifact.

## 10. Markdown output design

`dispatch/current.md` and each run `.md` should include:

1. dispatch timestamp
2. source owner-routing timestamp
3. owner count
4. total dispatched item count

Then render one section per owner:

1. `## Owner: <owner>`
2. a one-line summary with item count and dominant lane
3. each item as:
   - id
   - reason
   - priority flags
   - frozen command

The run Markdown and latest Markdown may share the same body shape.

## 11. Error handling and policy

1. dispatch must fail if `.omo/debt/owner-routing/current.yaml` does not exist
2. dispatch must fail if the owner-routing packet is missing required fields such as `generated_at`, `owners`, or `summary`
3. ownerless entries remain visible as `unowned`
4. closed items must never appear in dispatch packets
5. dispatch must remain fully derived and must not mutate debt items or owner-routing inputs

## 12. Testing and verification

The implementation plan should cover:

1. pure dispatch builder tests for command freezing and run-ref creation
2. duplicate-timestamp failure tests
3. unknown/missing command metadata failure tests
4. CLI tests for the new `dispatch` subcommand
5. output tests for dispatch `current.yaml` / `current.md`
6. docs regression for `.omo/AGENT.md`
7. canonical `bash bin/verify-omo.sh`

## 13. Success criteria

This design is successful when:

1. the system can prove a dispatch packet was formally surfaced at a specific `dispatched_at` timestamp
2. each dispatch entry contains exactly one canonical command and no unresolved placeholders
3. revalidation dispatch commands are frozen to `dispatched_at`, not runtime shell expansion
4. the latest dispatch packet can be read quickly while immutable run files preserve surfaced history
5. no owner acknowledgement or mutable workflow state is required for the packet to stay coherent
