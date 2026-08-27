---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P55 R1: Phase 1-13 历史执行计划归档, 当前阶段/状态以 .omo/state/system.yaml + .omo/goals/current.yaml 为准"
---
# Phase 5 program plan

> **Status**: ACTIVE planning packet
> 
> **Execution rule**: this document is the Phase 5 program map, not an immediate execution source. Only **G5.0 / Wave 0** may be promoted into `.omo/tasks/active/*.yaml` after the entry gate is explicitly approved.

---

## 1. Program objective

Build Phase 5 as OMO's **process governance layer** on top of the completed Phase 4 execution-governance substrate.

## 2. Program sequencing

| Wave | Goal | Duration | Output type | Execution status |
|------|------|----------|-------------|------------------|
| Wave 0 | G5.0 Entry gate | 2-3 days | landing model + goal/task shells | next |
| Wave 1 | G5.1 Durable runtime + governance core | 2 weeks | runtime/proposal foundation | gated |
| Wave 2 | G5.2 Auto-discovery + templates | 2-3 weeks | metadata compression layer | gated |
| Wave 3 | G5.3 Skill federation | 2-3 weeks | governed AI execution layer | gated |

## 3. Wave 0 — G5.0 Entry gate

### Objective

Freeze the contracts that Phase 5 implementation cannot safely discover on the fly.

### Candidate tasks

1. **P5-W0-LANDING-MODEL-FREEZE**
   - decide `_truth/task-center/` and `_delivery/task-center/` ownership boundary
   - explicitly forbid mirrored runtime data outside owner planes
2. **P5-W0-SECRETS-OWNERSHIP-DECISION**
   - choose the `secret_ref` backing model
   - define storage, rotation, audit, and access policy
3. **P5-W0-HERMES-COMPATIBILITY-CONTRACT**
   - adopt Direction A as the default Phase 5 posture
   - freeze Hermes as ingress + memory retention, not scheduler backbone
   - define the exact residual dependencies: WeChat/IM entry, MCP memory consumption, auth fallback
4. **P5-W0-PROPOSAL-MODEL-FREEZE**
   - finalize proposal schema, state flow, governance level mapping, and audit linkage
5. **P5-W0-REVIEW-REFRESH-PACKET**
   - refresh architecture/security/ops review statuses into "absorbed / still blocking / deferred"
6. **P5-W0-GOAL-TASK-SEEDING**
   - define `G5.0` and create only the execution-ready task shells

### Evidence required

- phase5-entry-gate-checklist.md completed
- review status packet linked from knowledge plane
- explicit plane ownership table linked from design docs
- Hermes convergence decision linked to `hermes-convergence-strategy.md`

### Verification

- schema walk-through against `phase5-requirements.md`, `task-center-requirements.md`, and three review docs
- consistency check that no new shadow SSOT is introduced

### Exit criteria

1. Wave 1 can be decomposed into active tasks without unresolved ownership questions
2. secret handling is no longer an architectural placeholder
3. Hermes wording is aligned across all live docs
4. Hermes scheduler de-ownership is explicit before Wave 1 task seeding

## 4. Wave 1 — G5.1 Durable runtime + governance core

### Objective

Land the minimal governed runtime that can survive crashes and regulate truth mutations.

### Execution lane A — durable runtime

1. checkpoint schema and storage contract
2. atomic run/checkpoint recorder
3. resume scanner and killed-state policy
4. heartbeat, watchdog, queue cap, and backpressure baseline

### Execution lane B — governance core

1. proposal schema and lifecycle
2. governance level state machine
3. propose / approve / apply / list MCP tools
4. audit and verification output model

### Execution lane C — Hermes convergence transition

1. migrate cron ownership from Hermes to agentmesh scheduler
2. stop new Hermes bridge growth and define a migration path for existing bridge scripts
3. preserve WeChat/IM ingress through Gateway webhook proxy
4. document auth fallback policy for `~/.hermes/auth.json` / `.env`

### Evidence required

- runtime crash/restart evidence
- proposal lifecycle evidence
- audit log evidence
- Hermes ingress continuity evidence
- scheduler convergence evidence

### Verification

- failure drill: crash during running step
- permission drill: L3 proposal cannot execute pre-approval
- integrity drill: proposal/run/audit trace continuity

### Exit criteria

1. resumable execution works or safely fails closed
2. L2/L3 truth mutations are proposal-governed
3. no direct-write path bypasses the approved lifecycle for governed operations
4. Hermes is no longer a required scheduler dependency for new work

## 5. Wave 2 — G5.2 Auto-discovery + templates

### Objective

Compress task definition cost while preserving a single metadata truth.

### Candidate workstreams

1. frontmatter schema and parser
2. directory scan and registry reconciliation
3. blueprint/template schema
4. template instantiation and parameter override flow

### Evidence required

- registry reconciliation artifacts
- template instantiation examples
- operator guide for discovery and template use

### Exit criteria

1. script metadata stops being dual-written
2. template-instantiated tasks are traceable back to a blueprint

## 6. Wave 3 — G5.3 Skill federation

### Objective

Let AI skills run through the same governance and delivery chain as standard tasks.

### Candidate workstreams

1. skill declaration schema
2. skill/task mapping contract
3. governed skill execution bridge
4. skill delivery outputs and audit trail
5. Hermes memory MCP consumption as one supported context source

### Evidence required

- at least one governed skill execution trace
- federation mapping examples
- operator guide for skill-governed execution

### Exit criteria

1. skill execution becomes schedulable and observable
2. governed AI execution obeys the same audit and verification rules

## 7. Program-level go/no-go rules

### Go

1. Only one execution-ready wave at a time
2. Goals/tasks are seeded only when their entry gate is explicit
3. Every wave closes with verification + retrospective artifacts

### No-go

1. Do not seed Wave 1+ tasks while Wave 0 is unresolved
2. Do not let Task Center implementation outrun the secrets/proposal landing model
3. Do not use indexes as live status mirrors
4. Do not let Hermes silently remain a second scheduler/control plane

## 8. Immediate next step

Convert **Wave 0 / G5.0** into the next `.omo/tasks/active/*.yaml` packet after review.
