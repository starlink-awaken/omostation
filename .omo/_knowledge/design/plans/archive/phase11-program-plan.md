# Phase 11 program plan: Capability & user layer enablement

> Status: completed
> Theme: System capability & user layer enablement
> Pre-requisite: Phase 10 all waves closed, health_score ≥90
> Created: 2026-06-01
> Derived from: `layer-capability-user-planning.md` v2, `phase10-cross-audit.md`, `DEBT-ANALYSIS.md`, `INSIGHTS-AND-ROADMAP.md`

---

## 1. Phase objective

Phase 10 established cross-root operating rule unification. **Phase 11 upgrades from "rule unification" to "capability enablement"** — converting the architecture foundation (3-layer knowledge pipeline, 4-plane governance, normalized rules) into:

- **System capability layer**: Stable modules, deliverable interfaces, resolved cross-phase debt
- **User layer**: Operable tools, visible value, structured identity, centralized data access

### Strategic objectives

| ID | Objective | Link |
|----|-----------|------|
| S1 | **SSOT repair** — Resolve 4 Critical cross-audit findings from Phase 10 | C1-C4 |
| S2 | **Capability standardization** — live kairon package inventory, SharedBrain organ/nucleus inventory, agentmesh/gbrain interface alignment | Capability wave 1 |
| S3 | **Core debt assault** — D2 CI env / D3 eu-pricing tests / P1 SB decision / T1 KOS ruff / T4 hardcoded paths | Cross-phase core debt |
| S4 | **User layer MVP** — Centralized data index, basic Web dashboard, FTS5 search, structured identity | User wave 2/3 |
| S5 | **Production readiness start** — v0.2 roadmap items (absolute paths elimination, FastMCP migration, KOS indexer hardening) | Long-term evolution |

---

## 2. Wave structure

### Wave 1 — SSOT repair + baseline inventory
- Goal: Fix Phase 10 cross-audit C1-C4 critical SSOT breaks; complete system capability global inventory
- Packet name: **P11-W1-SSOT-BASELINE**
- Status: completed
- Sub-goals:
  - G11.1.1 — SSOT repair: system.yaml, goals/current.yaml, plans/README.md, control plane (C1-C4)
  - G11.1.2 — System capability baseline: live kairon package audit, SharedBrain organ/nucleus audit, agentmesh/gbrain interface mapping, Agora→OntoDerive decoupling assessment
  - G11.1.3 — User data scatter mapping: data/, SharedBrain/, spaces/, runtime/ directories

### Wave 2 — System capability core debt assault
- Goal: Resolve 5-phase-spanning core debt + SharedBrain decision + code quality improvement
- Packet name: **P11-W2-CORE-DEBT**
- Status: completed
- Sub-goals:
  - G11.2.1 — Cross-phase core debt: D2 CI env, D3 eu-pricing tests, D7 orphaned task cleanup
  - G11.2.2 — Product & tech debt: P1 SB decision, P5 interactive eidos define, T1 KOS ruff ≤500, T4 hardcoded paths
  - G11.2.3 — Model unification: OntoDerive Inference/Scheme → MetaType, Minerva Relation → MetaRelationType

### Wave 3 — User layer front-end landing
- Goal: User layer MVP — users can see, search, and operate their data
- Packet name: **P11-W3-USER-MVP**
- Status: completed
- Sub-goals:
  - G11.3.1 — Centralized data index: unified data directory API, type registry, TTL/GC baseline
  - G11.3.2 — Basic user tools: SQLite FTS5 search, HTTP health check, macOS notifications, workspace dashboard
  - G11.3.3 — Identity structuring: caller_id → structured identity model + audit trail

### Wave 4 — Deep hardening + long-term evolution alignment
- Goal: Production readiness start + roadmap alignment
- Packet name: **P11-W4-EVOLUTION-BRIDGE**
- Status: active
- Sub-goals:
  - G11.4.1 — v0.2 production readiness: absolute path elimination, pip install verify, KOS indexer hardening, FastMCP migration
  - G11.4.2 — Deep hardening: Hermes broken links (179→≤10), Minerva temp files, KOS storage format calibration, Cross-repo governance
  - G11.4.3 — Long-term evolution interface: v0.3 protocol planning, cross-project API contract pilot, Phase 12 pre-planning gate

---

## 3. Sequencing rule

```
Wave N stays gated until Wave N-1 closeout records a GO.

Wave 1 ← Phase 10 closeout GO
Wave 2 ← Wave 1: C1-C4 repaired + all inventory reports reviewed
Wave 3 ← Wave 2: D2/D3/D7 verified + SB decision completed + KOS ruff ≤500
Wave 4 ← Wave 3: User MVP demo passed + identity structured
Phase 12 ← Wave 4: pip install works + FastMCP migrated + Hermes ≤10 + Phase 12 gate ready
```

The active queue must never contain more than one execution-ready packet.

---

## 4. Success metrics

| Metric | Current | W1 | W2 | W3 | W4 |
|--------|---------|----|----|----|----|
| Health score | 90.0 | 92 | 94 | 96 | 97 |
| KOS ruff | 5,263 | ≤3,000 | ≤500 | ≤200 | ≤200 |
| Model unification | 80% | — | ≥95% | ≥95% | ≥95% |
| SB status | 0 tests / no decision | decision made | inventory done | migration plan | exec start |
| User feasible scenarios | 20/60 ✅ | 20/60 ✅ | 25/60 ✅ | 32/60 ✅ | 38/60 ✅ |
| Hermes broken links | 179 | — | — | — | ≤10 |
| Control plane health | degrade (70) | healthy (≥90) | healthy (≥90) | healthy (≥95) | healthy (≥95) |
| D2/D3 status | unhandled for 5 phases | — | ✅ verified | ✅ verified | ✅ verified |
| SSOT consistency | C1-C4 broken | C1-C4 ✅ | — | — | — |

---

## 5. Verification baseline

```bash
# Phase 11 baseline checks
make kairon-test                    # All kairon tests pass
cd projects/kairon && ruff check    # No new violations

# SSOT consistency (Wave 1)
test -f .omo/state/system.yaml && grep -q "current_phase: 11" .omo/state/system.yaml
test -f .omo/goals/current.yaml && grep -q "phase11" .omo/goals/current.yaml
test -f .omo/plans/README.md && grep -q "phase11" .omo/plans/README.md

# Health check (Wave 3)
curl -s http://localhost:8080/health 2>/dev/null | grep -q "ok"

# KOS ruff (Wave 2)
cd projects/kairon && ruff check packages/kos/ 2>/dev/null | wc -l

# Hermes (Wave 4)
grep -r "broken" .hermes/ 2>/dev/null | wc -l
```

---

## 6. Program-level go/no-go rules

### Entry from Phase 10
- [ ] Phase 10 all 4 waves closed
- [ ] Phase 10 closeout retrospective recorded
- [ ] system.yaml updated: `current_phase: 11, phase_status: entering`

### Phase 11 overall GO
- [ ] Health score ≥97
- [ ] D2/D3 no longer flagged as "future phase"
- [ ] SharedBrain has documented decision (migrate/rewrite/archive)
- [ ] User layer at least 3 tools operational
- [ ] KOS ruff ≤200
- [ ] system.yaml + goals + plans/README + control plane fully consistent

### Phase 11 No-Go
- [ ] C1-C4 NOT repaired by end of Wave 1
- [ ] D2/D3 still marked "future phase" at Phase 11 close
- [ ] Health score did not improve (still 90)
