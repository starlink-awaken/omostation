# Phase 12-14 architecture design

> Date: 2026-06-01
> Status: pre_planning design
> Scope: Phase 12 capability ecosystem foundation, Phase 13 supervised metacognition, Phase 14 deferred ecosystem expansion
> Canonical inputs: `../../plans/archive/phase12-planning-gate.md`, `../../plans/archive/phase12-program-plan.md`, `../../plans/archive/phase13-metacognition-preplanning.md`, `../../plans/archive/phase14-deferred-ecosystem-backlog.md`
> Live SSOT: `../../state/system.yaml`, `../../goals/current.yaml`, `../../tasks/active/`

---

## 1. Executive architecture

Phase 12-14 form one controlled evolution path:

| Phase | Role | Build boundary | Hard stop |
|-------|------|----------------|-----------|
| Phase 12 | Capability ecosystem foundation | Capability registry, scenario MVP, one fusion pilot, audit/redteam | No broad ecosystem absorption |
| Phase 13 | Supervised metacognition | Read-only self-assessment, proposal engine, supervised collaboration, guarded self-healing | No auto-apply by default |
| Phase 14 | Deferred ecosystem expansion | Triage and selectively execute deferred integrations, architecture patterns, package/article/marketplace expansion | No execution without a new program plan |

The architecture is intentionally staged. Phase 12 produces the capability map and traceable execution substrate. Phase 13 consumes that substrate to reason about system capability and propose improvements. Phase 14 is where the large ecosystem backlog can be reprioritized after Phase 12 has proven the foundation and Phase 13 has proven the metacognitive guardrails.

---

## 2. Control-plane principles

1. **No live promotion from plan text**: plan documents may describe a promotion, but `state/system.yaml`, `goals/current.yaml`, and `tasks/active/` may only change through a human-approved promotion task.
2. **One active packet**: Phase 12-14 must preserve the existing one-packet-at-a-time rule.
3. **Pre-planning is not execution**: all Phase 12-14 documents stay pre-planning until their entry gates pass.
4. **Deferred work is explicit**: when scope is cut, it must be listed in `phase14-deferred-ecosystem-backlog.md` or marked out of scope with a reason.
5. **Evidence before promotion**: every phase transition needs evidence pointers, not copied status claims.

---

## 3. Phase 12 detailed design

### 3.1 Components

| Component | Responsibility | Primary artifact | Evidence |
|-----------|----------------|------------------|----------|
| Capability metamodel | Define capability identity, type, protocol, entrypoint, lifecycle, and scenario tags | `.omo/standards/capability-metamodel.md` | schema validation report |
| Capability registry | Store core project capability records and sampled external capability records | `.omo/registry/` | registry index + scan report |
| Scenario contract | Define scenario inputs, capability bindings, trace format, and failure policy | `.omo/standards/capability-binding-policy.md` | scenario trace |
| Registry CLI | Provide minimal register/discover commands | `omo capability register/discover` or equivalent | CLI smoke test |
| Pilot ADR | Select exactly one P0 fusion pilot from LiteLLM or memU | `.omo/plans/archive/phase12-p0-pilot-adr.md` | ADR + rollback notes |
| Package dry-run | Report dependency deltas without mutating package managers | `omo pkg sync --dry-run` or equivalent | dry-run report |
| Audit closeout | Verify registry, scenario, pilot, backlog, and governance gates | `.omo/_knowledge/management/phase12-cross-audit.md` | audit + redteam |

### 3.2 Data flow

```text
project/source scan
  -> capability records
  -> registry validation
  -> scenario binding
  -> scenario trace
  -> pilot ADR / pilot evidence
  -> audit + redteam
  -> Phase 13 readiness + Phase 14 backlog
```

### 3.3 Required gates

| Gate | Required evidence | Blocks |
|------|-------------------|--------|
| P12 entry | Phase 11 Wave 4 closeout GO, human ratification, no Phase 12 active task | Phase 12 Wave 1 |
| W1 exit | metamodel, registry structure, core scan baseline | Wave 2 |
| W2 exit | register/discover smoke test, one scenario trace, pilot ADR | Wave 3 |
| W3 exit | selected pilot smoke test, rollback notes, package dry-run | Wave 4 |
| W4 exit | cross-audit, redteam, Phase 13 gate update, Phase 14 backlog verification | Phase 13 planning promotion |

### 3.4 Metrics

Use two metrics instead of overloading one health score:

| Metric | Meaning | Target |
|--------|---------|--------|
| `health_score` | existing system health from live SSOT | must not regress below Phase 11 closeout threshold without explicit waiver |
| `ecosystem_maturity_score` | Phase 12 capability ecosystem maturity | W1 25, W2 50, W3 75, W4 90+ |

---

## 4. Phase 13 detailed design

### 4.1 Components

| Component | Responsibility | Mutation allowed |
|-----------|----------------|------------------|
| Read-only metacognition report | Assess capability coverage, blind spots, confidence, and debt patterns from Phase 12 registry/evidence | No |
| Bottleneck proposal engine | Rank bottlenecks and improvement suggestions with evidence and rollback notes | No |
| Supervised collaboration planner | Suggest task collaboration envelopes and approval routes | No direct execution |
| Self-healing pilot | Rehearse rollback and incident reasoning | Dry-run only until mutation gate passes |

### 4.2 Mutation gate

Phase 13 W4 may only propose live mutation after all conditions pass:

- W1-W3 have GO closeouts.
- Human approval exists for the specific mutation.
- Operation level is classified and L2/L3 approval evidence exists when required.
- Rollback drill has been run against a fixture or dry-run target.
- The proposed mutation has an evidence envelope with source, target, expected change, rollback, and verification.

Default is proposal-only. Auto-apply remains disabled by default.

---

## 5. Phase 14 detailed design

Phase 14 is not a dumping ground. It is a deferred execution candidate pool that must be replanned.

### 5.1 Backlog taxonomy

| Category | Examples | Re-entry condition |
|----------|----------|--------------------|
| Multi-project deep absorption | GitNexus, Graphify, UltraRAG, Firecrawl, MinerU, AgentLaboratory, nuwa-skill | interface readiness + owner + rollback |
| Architecture pattern absorption | Brain/Hands/Session, Context Core, Swarm, CT+Timeline, Semble | design review + implementation spike |
| Article knowledge expansion | 100-150 article ingestion and knowledge graph | source policy + retention/copyright policy |
| Package ecosystem expansion | install/add/remove/list, package graph | security review + dry-run history |
| Marketplace/external ecosystem | `omo market`, external installs | admission controls + sandbox/rollback |

### 5.2 Phase 14 replan requirement

Before any Phase 14 task becomes active, a new Phase 14 program plan must:

- Select a small subset of the backlog.
- Define one active packet only.
- Attach risk acceptance for expedited entry if Phase 13 is bypassed.
- Include security review and rollback gates for external installs and deep absorption.

---

## 6. OMO mechanism support and required iteration

The current `.omo` mechanism supports plan registration, active task packets, state snapshots, and governance tests. It does not yet fully support Phase 12-14 without a few small mechanism upgrades.

| Mechanism gap | Required iteration | Why |
|---------------|--------------------|-----|
| Plan text can imply live SSOT edits | Add a `Promotion envelope` template under `.omo/workers/templates/` or `.omo/tasks/templates/` | Prevent free-form edits to `state/system.yaml` and `goals/current.yaml` |
| Deferred work lacks a first-class ledger | Treat `phase14-deferred-ecosystem-backlog.md` as the current `Deferred scope ledger`; later promote to `.omo/_truth/deferred-scope.yaml` if needed | Prevent cut scope from disappearing or sneaking back into Phase 12 |
| Capability records have no SSOT domain | Add registry schema in Phase 12 W1 before writing real records | Avoid ad hoc capability YAML |
| Scenario traces have no evidence schema | Add scenario trace format in Phase 12 W2 | Make scenario MVP auditable |
| Mutation proposals lack a reusable envelope | Add mutation proposal evidence schema before Phase 13 W4 | Keep metacognition supervised |

These mechanism iterations are technical support for the plan, not permission to start Phase 12 early.

---

## 7. Cross-phase review matrix

| Review dimension | Phase 12 | Phase 13 | Phase 14 |
|------------------|----------|----------|----------|
| Scope | bounded foundation | read-only first metacognition | selected deferred expansion |
| SSOT | registry/scenario evidence only; no live promotion from plan text | consumes P12 evidence; writes proposals | requires new program plan |
| Security | pilot reviewed by governance + security | approval and rollback gates | admission controls and sandboxing |
| Testing | schema, CLI smoke, scenario trace, pilot smoke, audit | deterministic report, proposal fixtures, mutation dry-run | integration tests per selected packet |
| Drift guard | Phase 14 backlog for removed scope | no auto-apply by default | no broad execution without reprioritization |

---

## 8. Non-negotiable guardrails

- Phase 12-14 must not create active tasks while Phase 11 is active.
- Phase 12 must not deep-absorb multiple external projects.
- Phase 13 must not execute live mutations by default.
- Phase 14 must not use the backlog as an execution plan.
- Archived Phase 13 material remains historical input only.
