---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P55 R2: summaries/ 根目录历史快照批量归档, 当前状态以 .omo/state/system.yaml + .omo/tasks/active/ 为准"
---
# Phase 11 — Debt Progress Dashboard (T1.14)

> Generated: 2026-05-31 (local)
> 
> Purpose: unify the debt snapshot in `.omo/DEBT-ANALYSIS.md` with the Phase 11 Wave 1–4 execution plans, so every debt item has **Wave ownership**, a **status**, and a **verification gate**.

## Sources (SSOT)

- Debt snapshot: `.omo/DEBT-ANALYSIS.md`
- Program plan: `.omo/plans/archive/phase11-program-plan.md`
- Wave plans:
  - `.omo/plans/archive/phase11-wave1-execution-plan.md`
  - `.omo/plans/archive/phase11-wave2-execution-plan.md`
  - `.omo/plans/archive/phase11-wave3-execution-plan.md`
  - `.omo/plans/archive/phase11-wave4-execution-plan.md`

---

## Wave snapshot

| Wave | Packet | Plan status | Debt focus (from plans) |
|------|--------|-------------|--------------------------|
| W1 | P11-W1-SSOT-BASELINE | execution-ready | Cross-audit **C1–C4** SSOT repair + baseline inventories + **T1.14 dashboard** |
| W2 | P11-W2-CORE-DEBT | pre_planning | Cross-phase core debt (**D2/D3/D7**) + product/tech debt (**P1/P5/T1/T4**) |
| W3 | P11-W3-USER-MVP | pre_planning | User-layer MVP tooling (search/health/dashboard/identity) |
| W4 | P11-W4-EVOLUTION-BRIDGE | pre_planning | Hardening + evolution alignment (absolute paths, Hermes links, governance in CI, FastMCP) |

**Legend**
- **Owner** = Wave + Task ID(s) in Phase 11 execution plans.
- **Status** = current planning/execution state (this dashboard does not assert completion evidence unless linked).

---

## Debt register (mapped to Phase 11 waves)

### A) Cross-audit critical breaks (C1–C4) — owned by Wave 1

| ID | Debt item | Owner (Wave/Task) | Status | Verification gate |
|----|----------|-------------------|--------|-------------------|
| C1 | `state/system.yaml` inconsistent with reality (phase fields / current_phase) | W1 / T1.1 | planned | `grep "current_phase: 11" .omo/state/system.yaml` (plus consistency script as per plan) |
| C2 | `goals/current.yaml` missing/incorrect Phase 11 goals structure | W1 / T1.2 | planned | `grep -n "phase11" .omo/goals/current.yaml` (S1–S5 + 4 waves present) |
| C3 | `plans/README.md` registry/state badges inconsistent (Phase 11 not registered / wrong statuses) | W1 / T1.3 | planned | `grep -n "phase11" .omo/plans/README.md` |
| C4 | Control plane degraded / freshness stale (`freshness_score` ~70) | W1 / T1.4 | planned | `.omo/_delivery/task-center/control/current.yaml` shows `freshness_score >= 90` |

### B) Cross-phase backlog debts (D*) — owned by Wave 2 / Wave 4 (per Phase 11 plans)

| ID | Debt item | Owner (Wave/Task) | Status | Verification gate |
|----|----------|-------------------|--------|-------------------|
| D2 | CI/E2E environment requires running services; never landed in CI | W2 / T2.1 | pre_planning | Phase 11 CI runs all 17 packages (workflow added/updated as part of T2.1) |
| D3 | `eu-pricing` lacks independent test suite | W2 / T2.2 | pre_planning | `pytest tests/eu-pricing/` passes |
| D4 | Cross-repo governance: standards exist but not enforced at scale | W4 / T4.8 | pre_planning | Governance check is enforced in CI (cross-repo standard execution) |
| D6 | Hermes broken links backlog (179 baseline) | W4 / T4.5 | pre_planning | Broken links `<= 10` (Hermes audit report) |
| D7 | Orphaned tasks: audit + close/reassign | W2 / T2.3 | pre_planning | “Zero orphaned tasks” (audit report + registry clean) |

### C) Product debts (P*) — from `.omo/DEBT-ANALYSIS.md`

| ID | Debt item (DEBT-ANALYSIS) | Owner (Wave/Task) | Status | Verification gate |
|----|---------------------------|-------------------|--------|-------------------|
| P1 | SharedBrain: ~2.1M LOC, 0 tests — needs keep/migrate/archive decision | W2 / T2.4 + T2.5 | pre_planning | `summaries/SB-DECISION.md` exists; `pytest projects/SharedBrain/tests/` passes with `>=10` tests |
| P2 | Forge: ~1,762 LOC, 0 tests — confirm keep/archive | (not in Phase 11 plans) → suggested W2 | unassigned | Decision doc exists (keep/archive) and rationale recorded |
| P3 | KOS: “zero consumers” (no projects `import kos`) — API not validated | (not explicit) → suggested W3/W4 | unassigned | At least 1 real consumer module imports KOS (or KOS repositioned as CLI-only by decision) |
| P4 | SSOT metamodel coverage ~60% (missing relation types / rule types / mapping) | W2 / G11.2.3 (T2.9–T2.11) | pre_planning | Model unification `>=95%` (per Wave 2 exit gate) |
| P5 | Missing interactive `eidos define` (user must handwrite JSON) | W2 / T2.6 | pre_planning | `eidos define --help` shows `--interactive` |
| P6 | `viz state/graph` not using real data (demitter nodes/state) | (not in Phase 11 plans) → suggested W2 | unassigned | `eidos viz state/graph` uses real pipeline data (no demitter placeholders) |

### D) Technical debts (T*) — from `.omo/DEBT-ANALYSIS.md`

| ID | Debt item (DEBT-ANALYSIS) | Owner (Wave/Task) | Status | Verification gate |
|----|---------------------------|-------------------|--------|-------------------|
| T1 | KOS ruff ~5,263 | W2 / T2.7 (≤500) + W4 / T4.3 (≤200) | pre_planning | `ruff check packages/kos/` `<= 500` (W2), then `<= 200` (W4) |
| T2 | Minerva ruff ~955 | (not in Phase 11 plans) → suggested W4 | unassigned | `ruff check` violations reduced to an agreed ceiling (e.g., `<=200`) |
| T3 | OntoDerive ruff ~1,307 | (not in Phase 11 plans) → suggested W2/W4 | unassigned | `ruff check` violations reduced to an agreed ceiling (e.g., `<=300`) |
| T4 | Hardcoded absolute paths (e.g., PipelineStep.to_cli contains `/Users/...`) | W2 / T2.8 + W4 / T4.1 | pre_planning | No meaningful hardcoded absolute paths remain (plan uses grep for `/Users/`) |
| T5 | OntoDerive non-standard directory nesting (`engine/engine/formal/...`) | (not in Phase 11 plans) → suggested W2 | unassigned | Directory flattened; tests still pass |
| T6 | KOS CLI has 28 subparsers; most unused | (not in Phase 11 plans) → suggested W2/W4 | unassigned | CLI surface reduced and documented; deprecated commands archived |

---

## Wave ownership summary (by debt IDs)

| Wave | Debt IDs owned by plan | Notes |
|------|------------------------|-------|
| W1 | C1 C2 C3 C4 + T1.14 (this doc) | W1 also produces inventory reports; not tracked as debt IDs here |
| W2 | D2 D3 D7 + P1 P4 P5 + T1 T4 | Per Wave 2 exit gate: CI + tests + SB decision/tests + KOS ruff + no absolute paths + model unification |
| W3 | (none explicitly tagged as “debt” in plan) | W3 is capability growth; may implicitly create first “KOS consumer” via user tools |
| W4 | D4 D6 + T1 (≤200) + T4 (0 absolute paths) | W4 is hardening/governance + evolution bridge |

---

## Open gaps (actionable)

These items are **explicitly present in `.omo/DEBT-ANALYSIS.md`** but **not currently named as tasks** in the Phase 11 wave plans above (recommend adding explicit tasks if they must land in Phase 11):

- P2 Forge decision (keep/archive)
- P3 KOS “zero consumers” resolution approach (make a consumer, or formalize CLI-only positioning)
- P6 `viz state/graph` real data source
- T2/T3/T5/T6 cleanup targets (ruff + directory normalization + CLI surface)

