---
plane: knowledge
type: design
status: active
freshness: 2026-05-31
maintainer: auto
---
lifecycle: contract
owner: governance-team
last-reviewed: 2026-06-23
---

# Phase 5 program architecture

> **Positioning**: This document is the Phase 5 planning packet that refines `phase5-requirements.md` v0.1 into an OMO-aligned program architecture. It keeps the strategic direction, but changes the execution shape from a single large phase spec into a gated multi-wave program.
>
> **Decision**: Use **one master program + detailed Wave 0 / Wave 1 + gated Wave 2 / Wave 3**, rather than either a single overstuffed spec or five disconnected subsystem specs.
>
> This file is now a historical program-architecture reference for an earlier phase. It may still describe valid design principles, but it is not the live authority for current phase state, active goals, or execution permission.
> Live execution truth remains `/.omo/goals/current.yaml`, `/.omo/state/system.yaml`, `/.omo/tasks/active/`, and the current project SSOT docs.

## 1. Executive judgment

Phase 5 should start now as a **planning and entry-gate program**, not as a direct implementation burst.

The core strategic move remains correct:

1. Durable execution
2. Governance pipeline
3. Script auto-discovery
4. Task templates
5. Skill federation

But the current repository reality imposes three planning constraints:

1. **Task Center is still a design package, not a landed substrate**
2. **Phase 4 closed execution governance, not process governance**
3. **Secret ownership / Hermes compatibility / proposal ownership must be frozen before runtime work starts**
4. **Hermes should be treated as an upstream capability to consume selectively, not a second scheduler backbone**

So the correct architecture is:

- **Phase 4** = execution governance hardening
- **Phase 5** = process governance formalization

## 2. Approach options

### Option A — One giant Phase 5 spec

Put all five goals, all four waves, and all subsystem details into one document and treat it as the execution source.

**Pros**
- Single place to read
- Low document count

**Cons**
- Too easy to hide unresolved seams
- Wave 1 becomes overloaded again
- Hard to decide what is execution-ready versus still gated

### Option B — Recommended: master program + detailed Wave 0 / Wave 1

Keep one master architecture and one program plan, but only fully detail:

1. **Wave 0 / Entry Gate**
2. **Wave 1 / Durable runtime + governance core**

Keep Wave 2-3 at program level until Wave 0 is approved.

**Pros**
- Matches current repo maturity
- Keeps execution boundary explicit
- Preserves strategic cohesion without overcommitting later waves

**Cons**
- Requires two-step planning discipline
- Some future details stay intentionally open

### Option C — Immediate full decomposition into five subsystem specs

Split Durable / Governance / Discovery / Templates / Federation into separate specs now.

**Pros**
- Strong isolation
- Easy ownership assignment later

**Cons**
- Premature decomposition before landing model is frozen
- High document overhead
- Risks five local optimizations without one Phase 5 contract

## 3. Chosen architecture boundary

### 3.1 Phase 5 mission

Phase 5 turns OMO from **"can execute work"** into **"can govern work end-to-end"**.

That means Phase 5 is not just "more automation". It is the phase where the system gains:

1. resumable execution
2. proposal/approval/apply/verify discipline
3. single-source task/script metadata
4. reusable work blueprints
5. schedulable AI skills on the same governance chain

### 3.2 Four-plane ownership

| Plane | Phase 5 owner data | Rule |
|------|--------------------|------|
| control | phase entry gate, rollout flags, governance level caps, current wave | control stores state and permission boundary only |
| truth | task-center registry, proposals, blueprints, skill declarations, secret refs | one owner plane only; no mirrored truth elsewhere |
| knowledge | requirements, architecture, operator guides, review packets, retrospectives | planning and decision memory |
| delivery | checkpoints, run logs, proposal execution logs, audit trails, verification artifacts | execution evidence only |

### 3.3 Non-negotiable contracts

1. **No new shadow SSOT**
   - live facts stay in live sources
   - indexes only link and explain
2. **No secret values in registry/proposals**
   - only `secret_ref`
3. **Hermes is retained as ingress + memory, not scheduler ownership**
   - WeChat/IM entry remains allowed
   - layered memory may be consumed through MCP
   - cron / bridge / task-definition ownership must converge to OMO-side components
4. **Proposal flow governs truth mutation**
   - direct mutation may remain for L0/L1-compatible operations only where explicitly allowed
5. **Trace continuity is mandatory**
   - `trace_id` or equivalent chain must connect proposal, execution, verification, and delivery outputs

## 4. Program structure

### 4.1 Wave 0 — entry gate and landing model freeze

**Purpose**: make Phase 5 executable without mixing design assumptions into runtime work.

**What freezes here**

1. Task Center plane landing model
2. secret ownership model
3. Hermes convergence boundary
4. proposal entity shape and governance levels
5. Phase 5 initial goals/tasks seeding policy

**Outputs**

- entry gate checklist
- refreshed review status
- Wave 1 execution-ready packet

### 4.2 Wave 1 — durable runtime + governance core

Wave 1 stays one wave, but runs in two execution lanes:

#### Lane A — durable runtime

1. checkpoint schema
2. atomic checkpoint/run writing
3. restart scan and resume policy
4. queue/backpressure/watchdog baseline

#### Lane B — governance core

1. proposal schema
2. proposal lifecycle
3. governance level state machine
4. MCP surface for propose/approve/apply/list
5. audit and verification chain

#### Lane C — Hermes convergence transition

1. migrate cron ownership away from Hermes into agentmesh scheduling
2. stop new `~/.hermes/scripts/` bridge growth
3. define Task Center as the receiving side for task-definition ownership
4. preserve WeChat/IM entry continuity during scheduler convergence

**Wave 1 exit**

- crash/restart can recover or safely mark killed state
- L2/L3 truth mutations cannot bypass the proposal path
- verification evidence exists for both runtime and governance lanes
- Hermes is no longer the scheduler backbone, but ingress continuity remains intact

### 4.3 Wave 2 — auto-discovery + templates

Wave 2 focuses on definition compression:

1. script frontmatter schema
2. directory scan and registry reconciliation
3. blueprint/template model
4. template instantiation flow

**Wave 2 exit**

- script metadata becomes single-sourced
- repetitive YAML drops materially
- drift between script metadata and registry becomes detectable and repairable

### 4.4 Wave 3 — skill federation

Wave 3 connects AI-native skills into the same governed execution system:

1. skill declaration schema
2. skill-to-task mapping rules
3. governed execution bridge
4. delivery evidence for skill runs
5. Hermes memory consumption path through MCP as a reference substrate for skill context

**Wave 3 exit**

- skill execution becomes schedulable
- governed AI execution produces the same audit and delivery trace as non-AI tasks

## 5. Proposed goal model

| Goal | Meaning | Status recommendation |
|------|---------|-----------------------|
| G5.0 | Entry gate and landing model freeze | first execution-ready goal |
| G5.1 | Durable runtime + governance core | gated until G5.0 exit |
| G5.2 | Auto-discovery + templates | gated until G5.1 exit |
| G5.3 | Skill federation | gated until G5.2 exit |

This keeps Phase 5 aligned with the existing OMO pattern:

- goals/current.yaml expresses the current wave
- only the current execution-ready goal should seed `tasks/active/`
- later goals stay in plan/design, not in fake active state

## 6. Cross-cutting risk decisions

### 6.1 Security

Phase 5 must treat the red-team findings as design inputs, not later patches:

1. subprocess calls stay `shell=False`
2. HMAC validation must use safe compare
3. secret storage must be explicit before webhook/proposal features land
4. high-risk child execution must define isolation posture up front

### 6.2 Reliability

Wave 1 must absorb the SRE critical findings:

1. atomic write everywhere for checkpoints and run records
2. watchdog + heartbeat for scheduler health
3. backpressure and queue caps as part of baseline, not nice-to-have

### 6.3 Convergence

The convergence audit remains a hard rule:

1. no mirrored dynamic counters in indexes
2. no new owner ambiguity across planes
3. no design package that outruns repo reality without an explicit landing rule

### 6.4 Hermes-specific convergence

Hermes is now planned under **Direction A** from `hermes-convergence-strategy.md`:

1. keep Hermes for WeChat/IM ingress and memory value
2. remove Hermes from scheduler backbone ownership
3. migrate bridge/task-definition ownership toward Task Center
4. use Hermes memory through MCP instead of treating Hermes as a second control plane

## 7. Verification and retrospective model

Every Phase 5 wave should end with four packets:

1. **design packet** — what was intended
2. **delivery packet** — what artifacts were produced
3. **verification packet** — what tests and failure drills passed
4. **retrospective packet** — what changed in the operating model

That means Phase 5 is not complete when code exists; it is complete when the four-plane story is closed.

## 8. Recommended next action

Proceed with **Wave 0 only**.

Do **not** seed Wave 1 runtime tasks into `tasks/active/` until:

1. entry gate checklist is green
2. Task Center ownership semantics are frozen
3. Hermes Direction A wording is reflected across the live planning packet
4. the current reviews are refreshed to show which findings are already absorbed and which remain blocking
