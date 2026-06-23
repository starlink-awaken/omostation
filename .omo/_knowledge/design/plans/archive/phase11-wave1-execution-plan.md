---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P55 R1: Phase 1-13 历史执行计划归档, 当前阶段/状态以 .omo/state/system.yaml + .omo/goals/current.yaml 为准"
---
# Phase 11 Wave 1 execution plan: SSOT repair + baseline inventory

> Packet: P11-W1-SSOT-BASELINE
> Status: completed
> Entry gate: Phase 10 all waves closed + closeout retrospective recorded

---

## 1. Goal

Fix Phase 10 cross-audit C1-C4 critical SSOT breaks and establish system capability/user data baseline across all 4 projects.

---

## 2. Scope & deliverables

### G11.1.1 — SSOT repair (Critical C1-C4)

| # | Task | Deliverable | Verification |
|---|------|-------------|-------------|
| T1.1 | Rebuild `state/system.yaml` — add phase11 fields, verify all Phase 1-10 entries, add validation script | system.yaml updated + `scripts/check-system-consistency.sh` | `grep "current_phase: 11" system.yaml` |
| T1.2 | Create `goals/current.yaml` Phase 11 section — 5 strategic objectives + 4 waves with KPIs | goals/current.yaml updated | grep "phase11" present with all S1-S5 |
| T1.3 | Update `plans/README.md` — add Phase 11 entries + pre-planning status badges | plans/README.md updated | grep "phase11" in README |
| T1.4 | Fix control plane degrade — resolve `state_update_stale`, restore freshness ≥90 | control/current.yaml → healthy | `freshness_score ≥ 90` |

### G11.1.2 — System capability baseline audit

| # | Task | Deliverable | Format |
|---|------|-------------|--------|
| T1.5 | kairon live package inventory — per package: L1-L4 layer, test count, ruff count, health, owner | `summaries/system-capability-inventory.md` | Markdown table |
| T1.6 | SharedBrain live organ/nucleus inventory — per organ: code lines, test count, dependencies, status | `summaries/SB-ORGAN-INVENTORY.md` | Markdown table |
| T1.7 | agentmesh MCP gateway audit — tool registry status, LLM routing contract | `summaries/agentmesh-gbrain-interface-mapping.md` | Markdown report |
| T1.8 | gbrain Postgres backend + 74 MCP tool audit | (same file as T1.7) | — |
| T1.9 | Agora→OntoDerive coupling assessment — 12+ hard imports, decoupling options | `summaries/agora-ontoderive-decoupling-assessment.md` | Markdown analysis |

### G11.1.3 — User data scatter mapping

| # | Task | Deliverable |
|---|------|-------------|
| T1.10 | `data/` directory audit — subdirs, usage patterns, sizes | `summaries/user-data-scatter-report.md` |
| T1.11 | `SharedBrain/` data flow audit — data sources, consumers, formats | (same file as T1.10) |
| T1.12 | `spaces/` tenant/user manifest audit — ownership boundaries | (same file as T1.10) |
| T1.13 | `runtime/` ephemeral data audit — cleanup status, TTL | (same file as T1.10) |

---

## 3. Exit gate checklist

- [ ] system.yaml updated with Phase 11 fields + validation script committed
- [ ] goals/current.yaml has Phase 11 section (S1-S5 + 4 waves)
- [ ] plans/README.md shows Phase 11 entries (pre-planning status)
- [ ] Control plane restored to healthy (freshness ≥90)
- [ ] Cross-audit C1-C4 all marked ✅
- [ ] 6 summary reports completed (capability inventory, SB organs, interface mapping, decoupling assessment, user data scatter, debt progress dashboard)
- [ ] Wave 1 closeout documented in `summaries/phase11-wave1-closeout.md`
- [ ] Wave 2 execution plan reviewed and approved

---

## 4. Task mapping

```
P11-W1-SSOT-BASELINE:
  tasks:
    - T1.1 — system.yaml rebuild + validation script
    - T1.2 — goals/current.yaml Phase 11 section
    - T1.3 — plans/README.md registration
    - T1.4 — control plane health fix
    - T1.5 — kairon capability inventory
    - T1.6 — SB organ inventory
    - T1.7-T1.8 — agentmesh/gbrain interface mapping
    - T1.9 — Agora→OntoDerive decoupling
    - T1.10-T1.13 — user data scatter report
    - T1.14 — debt progress dashboard
```
