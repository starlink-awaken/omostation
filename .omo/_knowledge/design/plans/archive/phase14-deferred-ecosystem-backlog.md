---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P55 R1: Phase 1-13 历史执行计划归档, 当前阶段/状态以 .omo/state/system.yaml + .omo/goals/current.yaml 为准"
---
# Phase 14 deferred ecosystem backlog

> Status: completed
> Created: 2026-06-01
> Owner: governance agent draft; human ratification required before execution
> Entry gate: Phase 13 closeout GO or explicit human reprioritization
> Source refs: `phase12-program-plan.md`, `phase12-wave3-execution-plan.md`, `phase12-wave4-execution-plan.md`, `phase12-wave5-execution-plan.md`

---

## 1. Purpose

Phase 14 holds the work intentionally removed from Phase 12 during scope review. These items are valuable, but they are too large for the Phase 12 capability-ecosystem foundation. Parking them here keeps Phase 12 executable without losing the roadmap.

---

## 2. Deferred workstreams

| Workstream | Deferred items | Reason deferred |
|------------|----------------|-----------------|
| Multi-project deep absorption | memU, GitNexus, Graphify, UltraRAG, Firecrawl, MinerU, AgentLaboratory, nuwa-skill | Each is a real integration project; batching them into Phase 12 would hide risk and break one-packet-at-a-time execution |
| Architecture pattern absorption | Brain/Hands/Session, Context Core, Swarm, incremental context fetch, Compiled Truth + Timeline, Semble retrieval, code-review scenario, knowledge-search scenario, agent-collab scenario | These require design review, interface contracts, and implementation evidence after the registry/orchestrator foundation exists |
| Article knowledge expansion | 100-150 article ingestion, auto-summary, cross-article knowledge graph | Needs source quality policy, copyright/retention policy, and stable ingestion pipeline first |
| Package ecosystem expansion | Full uv/brew/npm/pip/cargo reconciliation, install/add/remove/list workflow, and dependency graph visualization | Needs Phase 12 registry schema and minimal `omo pkg` pilot before broad package mutation |
| Marketplace and external ecosystem | `omo market`, publish/install workflow, external capability ingestion | Needs security review and admission controls before external install paths are exposed |

---

## 3. Candidate wave structure

| Wave | Theme | Candidate scope |
|------|-------|-----------------|
| W1 | Integration backlog triage | Rank deferred projects by user value, maintenance risk, and interface readiness |
| W2 | Deep absorption pilots | Select 2-3 highest-value projects for Level 2/3 integration |
| W3 | Architecture pattern landing | Implement 2-3 proven patterns with tests and rollback plans |
| W4 | Ecosystem expansion | Article knowledge graph, package graph, and marketplace preview after security review |

---

## 4. Non-goals before Phase 14

- Do not deep-absorb all external projects in Phase 12.
- Do not auto-install external capabilities before admission controls exist.
- Do not treat article ingestion volume as a Phase 12 success metric.
- Do not expose a marketplace workflow without security and rollback gates.

---

## 5. Promotion criteria

Phase 14 planning can be promoted only when:

- Phase 12 delivered the capability registry, one runnable scenario, one fusion pilot, and closeout audit.
- Phase 13 metacognition remains read-only or has approved mutation controls.
- Human review confirms which deferred workstreams still matter.
- A new Phase 14 program plan maps selected work into one active packet at a time.
