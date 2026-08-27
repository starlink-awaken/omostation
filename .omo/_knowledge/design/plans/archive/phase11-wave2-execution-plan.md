---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P55 R1: Phase 1-13 历史执行计划归档, 当前阶段/状态以 .omo/state/system.yaml + .omo/goals/current.yaml 为准"
---
# Phase 11 Wave 2 execution plan: Core debt assault

> Packet: P11-W2-CORE-DEBT
> Status: completed
> Entry gate: Wave 1 closeout GO (C1-C4 repaired + all inventory reports reviewed)

---

## 1. Goal

Resolve 5-phase-spanning core debt (D2/D3/D7), product/tech debt (P1/T1/T4), and complete model unification to 95%.

---

## 2. Scope & deliverables

### G11.2.1 — Cross-phase core debt

| # | Task | Deliverable | Verification |
|---|------|-------------|-------------|
| T2.1 | **D2**: CI environment setup — GitHub Actions runner + kairon all-package test configuration | `.github/workflows/phase11-ci.yml` | All 20 packages run in CI |
| T2.2 | **D3**: eu-pricing test suite — covering EU economic module (pricing models, currency, compliance) | `tests/eu-pricing/` test suite | `pytest tests/eu-pricing/` passes |
| T2.3 | **D7**: orphaned task audit + close or reassign | Orphan audit report | Zero orphaned tasks |

### G11.2.2 — Product & tech debt

| # | Task | Deliverable | Verification |
|---|------|-------------|-------------|
| T2.4 | **P1**: SharedBrain decision document — migrate/rewrite/archive recommendation with rationale | `summaries/SB-DECISION.md` | Decision documented |
| T2.5 | **P1**: SB first ≥10 tests written | SB test suite | `pytest projects/SharedBrain/tests/` passes ≥10 |
| T2.6 | **P5**: Interactive eidos define CLI — `eidos define --interactive` | CLI command | `eidos define --help` shows interactive flag |
| T2.7 | **T1**: KOS ruff 5,263→≤500 | Ruff-clean CI | `ruff check packages/kos/` ≤ 500 violations |
| T2.8 | **T4**: Hardcoded path replacement — path configuration, move to `data/` | Path config module | No hardcoded absolute paths in codebase |

### G11.2.3 — Model unification

| # | Task | Deliverable | Verification |
|---|------|-------------|-------------|
| T2.9 | OntoDerive Inference → MetaType integration | ADR + code changes | MetaType unified, ontoderive tests pass |
| T2.10 | OntoDerive Scheme → MetaType integration | ADR + code changes | MetaType unified, scheme tests pass |
| T2.11 | Minerva Relation → MetaRelationType integration | ADR + code changes | MetaRelationType unified, minerva tests pass |

---

## 3. Exit gate checklist

- [x] D2 CI environment operational (GH Actions all packages)
- [x] D3 eu-pricing tests passing
- [x] D7 zero orphaned tasks
- [x] SB decision documented + ≥10 tests written
- [x] KOS ruff ≤500
- [x] No hardcoded absolute paths remain
- [x] Model unification ≥95% (3 ADRs documented)
- [x] Wave 2 closeout recorded in `summaries/phase11-wave2-closeout.md`
- [x] Wave 3 execution plan reviewed and approved

---

## 4. Task mapping

```
P11-W2-CORE-DEBT:
  tasks:
    - T2.1 — D2 CI environment
    - T2.2 — D3 eu-pricing tests
    - T2.3 — D7 orphan cleanup
    - T2.4 — SB decision document
    - T2.5 — SB first tests
    - T2.6 — Interactive eidos define
    - T2.7 — KOS ruff ≤500
    - T2.8 — Hardcoded path replacement
    - T2.9 — OntoDerive Inference MetaType
    - T2.10 — OntoDerive Scheme MetaType
    - T2.11 — Minerva Relation MetaRelationType
```
