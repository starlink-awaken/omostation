# Phase 7 planning gate design

Date: 2026-05-31
Status: approved design baseline
Scope: planning gate + ratification packet only

## 1. Context

Phase 6 is complete. The live OMO baseline is now:

- `current_phase: 6`
- `phase_status: completed`
- `current_wave: 3`
- `next_milestone: Phase 7 planning gate`
- active queue empty

The system is ready for the next phase, but it should not jump directly into execution. Phase 7 needs a planning gate that re-establishes control boundaries, defines the next program structure, and names the first execution-ready packet without prematurely seeding it.

There is one known residual divergence item, `orphaned_tasks:1`. This design treats it as a tracked follow-up inside the planning gate instead of a blocker for the gate itself.

## 2. Goals

Phase 7 planning gate should:

1. define the Phase 7 program structure in OMO terms
2. write a ratifiable planning packet instead of starting execution immediately
3. preserve the one-execution-ready-packet rule
4. keep residual governance debt explicit and scheduled
5. make the eventual Phase 7 ratification state transition deterministic

## 3. Non-goals

This packet does not:

1. start Phase 7 execution
2. seed a new active queue entry
3. implement the first Phase 7 runtime packet
4. silently clear `orphaned_tasks:1` without explicit control judgment

## 4. Approaches considered

### A. Gate-blocker first

Clear all remaining divergence before designing Phase 7.

- Pros: cleanest baseline
- Cons: planning gate gets coupled to debt cleanup, and the phase handoff loses momentum

### B. Recommended: planning gate first, tracked follow-up

Write and ratify the Phase 7 planning packet first, but record `orphaned_tasks:1` as an explicit follow-up constraint on the first execution packet.

- Pros: preserves OMO sequencing, keeps debt visible, avoids scope creep
- Cons: carries a known debt item into the next gate

### C. Planning gate plus starter packet together

Design the planning gate and the first execution-ready packet in one move.

- Pros: fastest path to implementation
- Cons: breaks the intended separation between planning, ratification, and execution

## 5. Recommended design

Use **Approach B**.

Phase 7 should begin with a planning-only packet that produces the documents and control mutations required for later ratification, while keeping live execution closed until the planning gate is explicitly approved.

## 6. Required outputs

The planning gate should produce these artifacts:

1. `.omo/plans/phase7-planning-gate.md`
   - planning-gate objective
   - success criteria
   - explicit gate checklist
   - ratification rules
2. `.omo/plans/phase7-program-plan.md`
   - overall Phase 7 program structure
   - packet ordering
   - wave boundaries
   - exit criteria
3. `.omo/plans/phase7-starter-packet-spec.md`
   - scope for the first execution-ready packet only
   - entry/exit gates
   - deliverables and verification expectations
4. `.omo/tasks/blocked/P7-...yaml`
   - a blocked shell for the future starter packet, if needed for visibility
   - never promoted to active during planning-gate work
5. `.omo/summaries/phase7-planning-ratification.md`
   - final GO/NO-GO judgment for entering Phase 7

## 7. Control-state behavior

Before ratification:

- keep `.omo/goals/current.yaml` at `phase: 6`, `status: completed`
- keep `.omo/state/system.yaml` at `next_milestone: Phase 7 planning gate`
- keep `.omo/tasks/active/` empty

After ratification:

- transition the control plane to `Phase 7 in_progress`
- update `current_wave` only if the first execution packet is formally defined
- seed at most one execution-ready packet

## 8. Governance constraints

1. `orphaned_tasks:1` must be recorded in the planning gate as a tracked follow-up
2. no active task may be introduced while the work is still in planning-gate mode
3. the starter packet must inherit the same governed delivery path used in Phase 6
4. ratification must state whether the residual divergence is:
   - cleared
   - tolerated temporarily
   - converted into a blocker for the starter packet

## 9. Testing and verification

The planning gate implementation should be verified with documentation and control-plane regression coverage:

1. add a doc test for Phase 7 planning-gate artifacts and state invariants
2. run `.omo` control-plane regression after the packet is written
3. ensure `sync_omo_state.py` reflects the planning-gate baseline without opening the active queue
4. verify the eventual ratification packet can move the system from `Phase 6 completed` to `Phase 7 in_progress` without introducing control ambiguity

## 10. Delivery sequence

1. write the planning-gate artifacts
2. review and ratify the design
3. write the implementation plan
4. only then promote the first Phase 7 packet into execution

## 11. Success criteria

This design is successful when:

1. the repository contains an explicit Phase 7 planning gate packet
2. the control plane still shows no active execution before ratification
3. the first execution packet is defined but not prematurely activated
4. residual governance debt is visible and intentionally handled
