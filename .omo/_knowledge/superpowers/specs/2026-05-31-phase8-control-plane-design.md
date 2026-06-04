# Phase 8 control plane design

Date: 2026-05-31
Status: approved design baseline
Scope: planning gate + Wave 1 starter packet definition

## 1. Context

Phase 7 is complete. The system can already:

1. preload live context into a request flow
2. bridge complex requests into governed task packets
3. persist positive confirmation as durable evidence
4. emit accounting and freshness artifacts

What it still cannot do reliably is decide **before execution** whether a request should proceed, degrade, pause, or stop. Phase 8 closes that gap.

## 2. Goals

Phase 8 should:

1. convert Phase 7 visibility into enforceable runtime control
2. add a single control decision path for budget and freshness
3. keep the one-execution-ready-packet rule intact
4. carry Hermes/storage/cross-repo debt as gated follow-up rather than letting Wave 1 absorb everything

## 3. Non-goals

Phase 8 Wave 1 does not:

1. solve every Hermes convergence issue
2. re-open completed Phase 7 packets
3. add broad new product features outside operational control
4. turn cross-repo governance into the first execution packet

## 4. Approaches considered

### A. Recommended: control-first hardening

Start with budget and freshness control because Phase 7 already provides the signals that Phase 8 needs to enforce.

- Pros: immediate operational leverage, smallest starter packet, directly upgrades the runtime from “visible” to “controllable”
- Cons: deeper architecture debt remains gated for later waves

### B. Convergence-first refoundation

Start with Hermes and storage seams before adding any control logic.

- Pros: reduces structural debt earlier
- Cons: delays the most immediate system-level improvement; weak short-term proof of value

### C. Governance-surface expansion

Start with cross-repo contracts and blocked connector review.

- Pros: improves workspace consistency
- Cons: does not fix the core “can see but cannot stop” runtime problem

## 5. Recommended design

Use **Approach A**.

Phase 8 should add a **runtime control brain** in front of the existing experience loop. The budget report and freshness report become inputs to a governed control decision that can:

1. allow execution
2. degrade execution
3. pause for review
4. block execution

Wave 1 should prove this control path with one execution-ready starter packet only:

- `P8-W1-BUDGET-FRESHNESS-CONTROL`

## 6. Required outputs

Phase 8 planning gate should produce:

1. `.omo/plans/phase8-planning-gate.md`
2. `.omo/plans/phase8-program-plan.md`
3. `.omo/plans/phase8-starter-packet-spec.md`
4. `.omo/tasks/done/P8-r0-phase8-planning-gate.yaml`
5. `.omo/tasks/active/P8-w1-budget-freshness-control.yaml`
6. `.omo/summaries/phase8-planning-ratification.md`
7. `docs/superpowers/plans/2026-05-31-phase8-control-plane.md`

Wave 1 implementation should then add:

1. failing regression tests for control decisions
2. budget/freshness control logic inside the existing OMO experience runtime
3. a persisted control decision artifact
4. at least one governed request path that exercises the control logic

## 7. Control-state behavior

Before ratification:

1. Phase 7 remains completed
2. active queue remains empty
3. `next_milestone` remains `Phase 8 planning gate`

After ratification:

1. control plane moves to `Phase 8 in_progress`
2. `current_wave` becomes `1`
3. exactly one execution-ready packet becomes active
4. Waves 2 and 3 remain gated

## 8. Wave structure

### G8.0 / Wave 0 — planning gate and control freeze

Ratify the phase, define success metrics, and seed one starter packet.

### G8.1 / Wave 1 — budget and freshness control plane

Add the runtime decision path that turns budget/freshness signals into allow/degrade/review/block outcomes.

### G8.2 / Wave 2 — Hermes and storage convergence

Use the Phase 8 control baseline to close the highest-value Hermes and storage trust seams.

### G8.3 / Wave 3 — cross-repo governance and blocked-surface ratification

Propagate the new control posture into key workspace contracts and re-ratify blocked connector posture.

## 9. Success criteria

This design is successful when:

1. Phase 8 is live with one active Wave 1 packet
2. the repo contains an explicit Wave 1 control-plane packet
3. Wave 1 can prove at least one request path is governed by budget/freshness policy before execution
4. deeper debt is still explicit, but not mixed into the starter packet
