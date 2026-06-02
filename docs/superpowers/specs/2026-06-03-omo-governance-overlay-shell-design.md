# OMO governance overlay shell design

Date: 2026-06-03
Status: approved-by-user-default execution mode (user unavailable; proceed with the established default of direct spec/plan/execution)
Scope: create a separate governance overlay phase/program that manages future roadmap, milestones, and autonomous execution policy without mutating or polluting the existing numbered phase lane

## 1. Context

The current `.omo` system already has a strong execution substrate:

1. numbered phase state in `.omo/state/system.yaml`
2. current goals in `.omo/goals/current.yaml`
3. canonical task truth in `.omo/tasks/`
4. promotion / approval governance on top of planned → active flow

What is still missing is a **separate control lane** for “what comes next”:

1. future roadmap packaging
2. milestone sequencing across multiple future phases
3. debt + planned + newly discovered work intake into one governance queue
4. an explicit autonomous execution policy for how OMO should keep iterating until target outcomes are reached

Today those concerns are scattered across:

1. `MASTER-BLUEPRINT.md`
2. phase program plans
3. debt surfaces
4. planned task packets
5. ad hoc roadmap reasoning in session state

That makes future planning possible, but not yet **governed as a first-class OMO lane**.

## 2. Problem statement

The user asked for three things at once:

1. use OMO to manage future milestones / roadmap / implementation tasks
2. do not pollute the current numbered phase
3. run with maximum autonomous execution, self-iterating through issues until the target state is reached

This is broader than a single helper command. It spans:

1. control-plane packaging
2. truth-plane intake
3. autonomous execution policy
4. reporting / operating surfaces

So this should be decomposed.

## 3. Decomposition

Treat this as a three-step program, not one giant change:

### Subproject A — Governance overlay shell (**this spec**)

Create the separate governance lane itself:

1. its identity and state
2. its roadmap registry
3. its intake rules
4. its autopilot policy contract
5. its operator-facing status surface

### Subproject B — Governance autopilot execution loop

After the shell exists, add the active loop that:

1. selects the next eligible roadmap item
2. maps it to concrete planned/active work
3. drives promotion / approval / verification
4. requeues blocked work with explicit reasons

### Subproject C — Governance trend / closeout analytics

Once the loop exists, add:

1. progress burndown
2. milestone drift detection
3. autopilot effectiveness reporting
4. closeout criteria

This spec intentionally covers **Subproject A only**, because it is the minimum correct foundation for the user’s request.

## 4. Goals

This slice should:

1. create a governance overlay that is separate from `current_phase`
2. allow future work intake from three sources:
   - new roadmap items
   - existing `tasks/planned/`
   - debt/watchlist items
3. define an explicit autopilot policy for what OMO may do automatically
4. produce one canonical governance status surface for operators
5. preserve task SSOT by referencing existing task/debt IDs instead of duplicating task truth

## 5. Non-goals

This slice does not:

1. replace the numbered phase system
2. rewrite `.omo/tasks/` schema
3. fully implement the autonomous execution loop
4. auto-close all future roadmap items
5. merge all existing phase docs into a new mega-plan

## 6. Approaches considered

### A. Reuse the current numbered phase lane

Behavior:

1. put future roadmap governance directly into Phase 17 / current phase files
2. add more milestones to the existing phase artifacts

Pros:

- no new structure

Cons:

- directly violates the user request not to pollute the current phase
- mixes “current execution phase” with “meta-governance of future work”
- makes future planning harder to reason about

This approach is rejected.

### B. Recommended: create a separate governance overlay program

Behavior:

1. keep `current_phase` and existing numeric phases unchanged
2. add a dedicated governance overlay lane with its own state and roadmap registry
3. let that lane reference existing task/debt SSOT rather than duplicating truth

Pros:

- satisfies the user’s separation requirement
- keeps the current phase clean
- gives OMO one explicit place to manage future roadmap and autonomy policy

Cons:

- introduces one more governance surface
- requires clear anti-duplication rules

### C. Docs-only roadmap governance

Behavior:

1. add one roadmap document and manually maintain it

Pros:

- smallest possible delta

Cons:

- not machine-operable
- cannot support real autopilot execution
- drifts quickly from task truth

This approach is rejected.

## 7. Recommended design

Use **Approach B**.

The core decision is:

> create a dedicated governance overlay program inside `.omo` that references existing task/debt truth, owns the roadmap + milestone ordering for future work, and defines the autonomous execution policy that later OMO slices will enforce.

The key principle is:

> **separate control, shared truth**

Meaning:

1. roadmap / milestone governance gets its own lane
2. concrete work still points back to canonical `.omo/tasks/*` and debt surfaces
3. no second task SSOT is introduced

## 8. Information model

### 8.1 Control-plane state

Add one dedicated governance overlay state file:

1. `.omo/_control/governance-overlay/current.yaml`

This file should track:

1. `overlay_id`
2. `status`
3. `autopilot_mode`
4. `intake_scope`
5. `current_milestone`
6. `next_milestone`
7. `success_target`
8. `updated_at`

Recommended defaults for this user request:

1. `autopilot_mode: full_omo_autopilot`
2. `intake_scope: future_planned_debt`
3. `status: active`

### 8.2 Truth-plane roadmap registry

Add one roadmap registry file:

1. `.omo/_truth/governance-overlay/roadmap.yaml`

This file should contain ordered roadmap items, each with:

1. `id`
2. `type` (`milestone`, `task-bundle`, `debt-bundle`, `phase-bridge`)
3. `title`
4. `priority`
5. `status`
6. `depends_on`
7. `source_refs`
8. `target_refs`
9. `success_criteria`

`target_refs` must point to existing SSOT surfaces where possible, for example:

1. `.omo/tasks/planned/<TASK>.yaml`
2. `.omo/debt/registry.yaml`
3. `.omo/debt/dashboard/current.yaml`
4. phase plans / program plans

### 8.3 Autopilot policy contract

Add one policy file:

1. `.omo/_truth/governance-overlay/autopilot-policy.yaml`

It should explicitly define:

1. what OMO may do automatically
2. what still requires a human gate
3. how blocked work is requeued
4. what “keep iterating until target reached” means operationally

For this user request, the default policy should be:

1. governance selection can be automatic
2. promotion / dispatch / verification can be automatic when risk rules allow
3. high-risk or explicit approval-required work still respects existing approval gates
4. failures must create explicit blocked or retryable records, never silent drops

## 9. Operator surface

Add one generated governance status surface:

1. `.omo/workers/governance-overlay/current.yaml`
2. `.omo/workers/governance-overlay/current.md`

The status packet should answer:

1. what milestone is active now?
2. what future items are queued?
3. which items are eligible for automatic execution?
4. which items are blocked, and why?
5. what should OMO do next?

Minimum fields:

1. `overlay_id`
2. `generated_at`
3. `current_milestone`
4. `next_milestone`
5. `eligible_count`
6. `blocked_count`
7. `autopilot_candidates[]`
8. `blocked_items[]`
9. `next_action`

## 10. Intake rules

The overlay should intake from three streams:

1. **future roadmap** — new milestones and roadmap items discovered from strategy / user direction
2. **planned queue** — existing `.omo/tasks/planned/*.yaml`
3. **debt/watchlist** — debt registry and dashboard items that materially block future milestones

But intake must remain pointer-based:

1. roadmap registry stores refs, not duplicated task payloads
2. debt bundles store refs, not copied debt bodies
3. execution still resolves to the existing task/debt SSOT

## 11. Autonomous execution contract

This slice does not implement the full loop yet, but it must define it clearly.

The future autopilot cycle should be:

1. refresh governance overlay status
2. choose the highest-priority eligible roadmap item
3. resolve item to existing task/debt refs
4. run promotion / dispatch / approval / verification using existing OMO mechanisms
5. if blocked, write a blocked reason and requeue
6. continue until the overlay milestone success criteria are met

The important design choice is:

1. the overlay decides **what to pursue next**
2. existing OMO task/promotion/approval mechanisms still decide **how concrete work executes safely**

## 12. Error handling

Fail closed:

1. missing referenced tasks or debt items must surface as invalid refs
2. roadmap items with unresolved dependencies must remain blocked
3. autopilot must never silently skip invalid or missing targets
4. no duplicate task truth should be written into the overlay registry

## 13. Testing

The implementation plan should include tests for:

1. overlay state loading and schema expectations
2. roadmap registry ordering and dependency filtering
3. status surface generation from roadmap + task/debt refs
4. explicit handling of missing refs / blocked dependencies
5. docs coverage for the new governance overlay lane

## 14. Rollout

Rollout should happen in bounded order:

1. create the overlay shell files and docs
2. seed the initial roadmap registry from:
   - future roadmap direction
   - existing planned queue
   - active debt/watchlist blockers
3. generate the first governance overlay status surface
4. only then add the autonomous execution loop in a follow-up slice

## 15. Success criteria

This shell is successful when:

1. there is a separate governance overlay lane inside `.omo`
2. future roadmap / milestones are managed there instead of being mixed into the current phase
3. the overlay references real task/debt truth without duplication
4. there is one canonical status surface showing what OMO should do next
5. the system is ready for a later autopilot loop slice
