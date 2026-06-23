---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P56 R2: 历史设计/历史/评审/图表批量归档, 当前活跃设计以 design/INDEX.md + PANORAMA.md 为准"
---
# OMO system design baseline

> Date: 2026-06-01
> Status: reference baseline
> Canonical role: post-Phase-14 architecture baseline for planning, review, and roadmap convergence
> Converges inputs from: `../../MASTER-BLUEPRINT.md`, `../../PRODUCT-ARCH-JOURNEY.md`, `phase12-14-architecture-design.md`, `../../standards/ARCHITECTURE_CONVERGENCE.md`, `../../standards/ssot-7-domain-schema.md`, `../../standards/capability-metamodel.md`
> Live SSOT remains: `../../goals/current.yaml`, `../../state/system.yaml`, `../../tasks/active/`
> This document keeps the post-Phase-14 planning frame and roadmap boundary as historical architecture guidance. Phase labels, sequencing, and packet names here are planning-era anchors, not current execution truth.

---

## 1. Purpose

This document is the architecture baseline for the next planning cycle after Phase 14. Its job is not to replace the existing standards or phase closeouts. Its job is to give the repository one converged frame for:

1. how to read the system,
2. where the next strengthening work belongs,
3. what must remain deferred,
4. how future phases stop drifting back into unbounded expansion.

The baseline therefore acts as a planning and review contract, not a second SSOT.

---

## 2. Framework name

The unified frame is **OMO Baseline Framework (4P3V1L)**.

It has three projections:

| Projection | Meaning | Canonical question |
|------------|---------|--------------------|
| `4P` | Four planes: control, truth, knowledge, delivery | Where does this artifact belong and who owns it? |
| `3V` | Three views: system construction, system capability, user usage | What is being built, what can it do, and how is it actually experienced? |
| `1L` | One governed lifecycle loop: observe -> assess -> propose -> approve -> execute -> verify -> closeout | How does the system evolve without bypassing governance? |

The framework is intentionally small. It is not a replacement for the phase plans, the SSOT schema, or the capability metamodel. It is the lens that makes them line up.

---

## 3. Structural grammar

Inside the framework, the structural grammar stays aligned with existing architecture documents rather than inventing a new stack.

| Token | Meaning in this baseline | Primary sources |
|-------|--------------------------|-----------------|
| `00` | Governance and SSOT substrate: `.omo`, task/state/goals standards, evidence discipline | `../../standards/ssot-7-domain-schema.md`, `../../DOC-ARCH.md` |
| `P0` | Product / user entry layer: the user-facing surface of the system | `../../MASTER-BLUEPRINT.md`, `../../PRODUCT-ARCH-JOURNEY.md` |
| `I0` | Integration fabric: routing, protocol, identity, admission, and service mesh seams | `../../MASTER-BLUEPRINT.md`, `../../standards/ARCHITECTURE_CONVERGENCE.md` |
| `L1-L4` | Capability stack: contracts, composed capability, collaboration/orchestration, meta/runtime surfaces | `../../MASTER-BLUEPRINT.md`, `phase12-14-architecture-design.md` |
| `X1-X3` | Cross-cutting axes: governance policy, anti-entropy/recovery, value/adoption feedback | this baseline + linked phase plans |

P0 here means the product / user entry layer inherited from the architecture docs, **not** the governance priority label used in some review documents.

---

## 4. The four planes (`4P`)

| Plane | Owns | Must not do |
|-------|------|-------------|
| Control | current goal, live phase state, gate posture | duplicate facts already owned by truth or delivery |
| Truth | SSOT facts, standards, canonical registries, task truth | become a prose-heavy planning layer |
| Knowledge | design reasoning, retrospectives, ADRs, reference material | claim authority over live mutable facts |
| Delivery | tests, evidence, worker runs, acceptance artifacts | silently redefine planning or truth contracts |

This keeps the four-plane model as the ownership map for documents and evidence.

---

## 5. The three views (`3V`)

| View | What it asks | Typical artifacts |
|------|--------------|-------------------|
| System construction | Are boundaries, ownership, contracts, and dependencies coherent? | architecture docs, standards, program plans |
| System capability | What scenarios are possible, what is blocked, and what evidence proves it? | capability registry, scenario traces, audits, rollout evidence |
| User usage | How does a human discover, choose, confirm, execute, and recover? | product journey docs, dashboards, CLI entrypoints, walkthrough evidence |

The design error to avoid is optimizing one view while forgetting the other two. Most earlier phases strengthened construction and capability; the current gap is user usage.

---

## 6. The one governed lifecycle loop (`1L`)

The only acceptable evolution loop is:

```text
observe -> assess -> propose -> approve -> execute -> verify -> closeout
```

Planning text may describe this loop, but only approved execution artifacts may move the live system. This keeps the baseline compatible with the existing "one active packet", "evidence before promotion", and "pre-planning is not execution" rules.

Phase 15 is the phase that operationalizes this loop.

---

## 7. What to strengthen next

The baseline does not say "expand everything." It says strengthen the following in sequence:

| Priority | Baseline slice | Delivery vehicle | Why |
|----------|----------------|------------------|-----|
| 1 | `00 + X1` governance substrate and policy tests | Phase 15 | The system already has evidence but still needs policy-grade enforcement and draft boundaries |
| 2 | `X2` anti-entropy, rollback, and recovery rehearsal | Phase 15 | Future autonomy without recovery would be brittle and unsafe |
| 3 | `I0` identity, protocol, and scenario routing consistency | Phase 15 -> Phase 16 | Product convergence depends on stable integration seams |
| 4 | `P0` product-surface convergence | Phase 16, after Phase 15 closes | The retrospective showed this is the biggest user-facing gap, but it must inherit Phase 15 guardrails |
| 5 | `L1-L4` contract consistency across the capability stack | Continuous; evidence in Phase 15, surface reuse in Phase 16 | Prevents the product layer from sitting on fragmented contracts |
| 6 | `X3` value and adoption feedback | Phase 16+ | Productization only matters if user value is visible and measurable |

---

## 8. Expansion boundary

The baseline must constrain expansion, not rationalize more of it.

The deferred-scope ledger remains `../../plans/archive/phase14-deferred-ecosystem-backlog.md`. That file is the only authoritative list of deferred ecosystem work and re-entry conditions.

This baseline only fixes the rule:

- broad external ecosystem absorption stays deferred,
- marketplace / install workflows stay deferred,
- unsupervised auto-mutation stays deferred,
- massive content ingestion stays deferred,
- uncontrolled multi-space or multi-product expansion stays deferred,

until a later phase re-enters them through the existing deferred ledger and a new approved program plan.

---

## 9. Roadmap anchored to the baseline

### Phase 15 — governance operating loop consolidation

| Item | Baseline decision |
|------|-------------------|
| Primary goal | Operationalize `1L` on top of `00`, `I0`, `X1`, and `X2` |
| Candidate packets | `P15-W1-EVIDENCE-LEDGER`, `P15-W2-POLICY-AS-TESTS`, `P15-W3-PROPOSAL-COMPILER`, `P15-W4-RECOVERY-DASHBOARD` |
| Hard stop | No `P0` product-surface work during Phase 15 |

### Phase 16 — product surface convergence

| Item | Baseline decision |
|------|-------------------|
| Primary goal | Converge `P0` on top of the guardrails Phase 15 produced |
| Candidate packets | `P16-W1-JOURNEY-BASELINE`, `P16-W2-SCENARIO-SHELL`, `P16-W3-UNIFIED-SURFACE-MVP`, `P16-W4-ADOPTION-CLOSEOUT` |
| Hard stop | No ecosystem-expansion laundering under a product label |

### Phase 17+

| Item | Baseline decision |
|------|-------------------|
| Primary goal | Resume bounded expansion only after governance loop and product surface both have closeout evidence |
| Candidate packets | `P17-W1-BOUNDED-FEDERATION`, `P17-W2-SELECTIVE-EXPANSION`, `P17-W3-VALUE-LOOP-CONSOLIDATION` |
| Hard stop | No resumption of broad expansion without Phase 15 policy baseline and Phase 16 adoption evidence |

---

## 10. Guardrails

1. **No shadow SSOT**: this baseline points to standards and ledgers; it does not replace them.
2. **No duplicate deferred ledger**: deferred ecosystem truth remains in `phase14-deferred-ecosystem-backlog.md`.
3. **No phase laundering**: Phase 15 cannot quietly do Phase 16 work; Phase 16 cannot quietly reopen Phase 14 expansion.
4. **No registry equals permission**: discovery or capability records never imply install or mutation permission.
5. **No pre-planning equals execution**: plans, designs, and baselines stay read-only until a live packet is promoted.
6. **One active packet** remains the execution model.

---

## 11. Artifact mapping

| Need | Canonical artifact |
|------|--------------------|
| Live phase / milestone | `../../state/system.yaml`, `../../goals/current.yaml` |
| Deferred ecosystem scope | `../../plans/archive/phase14-deferred-ecosystem-backlog.md` |
| Capability record grammar | `../../standards/capability-metamodel.md` |
| SSOT / write ownership rules | `../../standards/ssot-7-domain-schema.md` |
| Phase 12-14 architecture precedent | `phase12-14-architecture-design.md` |
| Phase 15 governance-loop plan | `../../plans/phase15-autonomous-governance-preplanning.md` |
| Phase 16 product-surface shell | `../../plans/phase16-product-surface-convergence-preplanning.md` |

This document is the new planning baseline for post-Phase-14 roadmap work. Older documents remain inputs and historical context, not competing canon.
