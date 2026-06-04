# Phase 6 program plan

> **Status**: ACTIVE planning packet
>
> **Execution rule**: this document is the Phase 6 master program map. Only **`G6.1 / Wave 1`** is execution-ready after ratification; `G6.2` and `G6.3` stay gated until their predecessor packet closes with an explicit GO.

---

## 1. Program objective

Complete Phase 6 as OMO's **runtime realization phase**: convert the frozen durable/governance/discovery/skill seams into a real governed runtime without reopening shadow-control-plane debt.

## 2. Program sequencing

| Wave | Goal | Duration | Output type | Execution status |
|------|------|----------|-------------|------------------|
| Wave 1 | `G6.1` durable + governance runtime core | 1-2 weeks | execution substrate + governance mutation path | execution-ready |
| Wave 2 | `G6.2` discovery + templates | 1-2 weeks | metadata compression layer | gated |
| Wave 3 | `G6.3` skill federation | 1-2 weeks | governed AI execution layer | gated |

## 3. Ratified baseline

1. `phase6-pre-gate-governance-2026-05-31.md` remains the governance decision source.
2. `phase6-entry-hardening-closeout.md` remains the entry GO packet for security, reliability, and mechanism debt.
3. Phase 6 starts only after those two artifacts are accepted together as the pre-runtime baseline.

## 4. Wave 1 — `G6.1` durable + governance runtime core

### Objective

Land the minimum runtime that can execute, recover, and mutate governed truth through one auditable path.

### Execution lanes

1. **Durable runtime**
   - checkpoint schema and step recorder
   - resume scanner and killed/recovery policy
   - heartbeat, watchdog, queue cap, and backpressure
2. **Governance runtime**
   - proposal schema + lifecycle
   - governed mutation path for truth-affecting operations
   - approval/apply/list surfaces
3. **Audit continuity**
   - proposal → execution → verification → delivery trace chain
4. **Scheduler convergence**
   - Hermes no longer owns scheduling for new work
   - ingress compatibility remains explicit only where required

### Exit criteria

1. crash/restart either resumes safely or fails closed
2. L2/L3 truth mutation cannot bypass the proposal flow
3. audit evidence links proposal, runtime, verification, and delivery
4. new runtime work no longer depends on Hermes as scheduler owner

## 5. Wave 2 — `G6.2` discovery + templates

### Objective

Reduce task-definition cost without creating a second metadata truth.

### Gate to enter

1. `G6.1` closes with explicit GO
2. runtime/governance path is already the single execution chain
3. directory scan/template work preserves SSOT ownership

## 6. Wave 3 — `G6.3` skill federation

### Objective

Run AI-native skills through the same governed runtime and evidence chain as normal tasks.

### Gate to enter

1. `G6.2` already provides the definition-compression substrate
2. runtime core and template machinery are stable enough to host skills
3. skill execution can inherit the same audit and verification rules

## 7. Program-level go/no-go rules

### Go

1. only one execution-ready packet at a time
2. only `G6.1` may appear in `.omo/tasks/active/` at Phase 6 start
3. every packet must close with verification, retrospective, and explicit GO/NO-GO

### No-go

1. do not seed `G6.2` or `G6.3` while `G6.1` is unresolved
2. do not let discovery/templates introduce mirrored live metadata
3. do not let skill federation bypass runtime/governance/audit rules
4. do not let Hermes silently remain a second scheduler backbone

## 8. Immediate next step

Execute **`phase6-wave1-execution-plan.md`** through the single active packet seeded by the ratification packet.

