# OPC-P1.5: Cross-Repo Governance Baseline

> Date: 2026-06-11
> P1 carry-in: D001-D010 proposed debt, R46-R50 probe absorption
> Status: ✅ completed
> Source: OPC-ROADMAP.md §M1.5, OPC-PHASE0-BASELINE.md, OPC-ARCHITECTURE-GAPS.md

---

## T1 — R46: audit-rollout --include-metrics Baseline

| Finding | Status | OPC Impact |
|:--------|:------|:-----------|
| `audit-rollout` exists with `--include-metrics` flag | ✅ confirmed in scripts/ | Active governance capability |
| Can produce per-repo audit metrics | ✅ | Cross-repo gate inputs |
| Integration with OMO phase gates | ❌ not yet wired | Must be referenced in P2+ gate criteria |

**Action**: R46 is now a baseline governance capability. Later phases (P2+) must include `audit-rollout --include-metrics` as part of gate review evidence.

---

## T2 — R47: ci-lint Metrics Trend Baseline

| Finding | Status | OPC Impact |
|:--------|:------|:-----------|
| `scripts/plot-metrics.py` exists (7.5KB) | ✅ | Trend plotting script available |
| Lint metrics artifact from CI | ✅ | Cross-repo lint trend data |
| Integration with OPC dashboard | ❌ not yet wired | Future: add lint trend to cockpit health |

**Action**: R47 is an active observability input. P2+ gates should reference lint trend data.

---

## T3 — R48: kairon Probe Actions

| Finding | Severity | Action |
|:--------|:---------|:-------|
| kairon is 16-package workspace, not meta-stub | medium | OPC-P0 D005 → P1.5 carry-in |
| JSONL append paths in kairon packages | **high** | Direct `json.dumps` + `open("a")` patterns exist |
| Cross-package dependency complexity | medium | 16 packages share stdio_rpc helper |
| L0 audit hook dependency | medium | `mof_agora_hook` is soft import |

**Required tasks** (for P2 memory prerequisites):

| Task ID | Description | Owner |
|:--------|:------------|:------|
| KAI-01 | Audit kairon JSONL write paths; replace with AppendOnlyLog or schema-checked write | kairon |
| KAI-02 | Register 16-package workspace governance in OMO debt if not done | omo |
| KAI-03 | Add lint/metrics gate to kairon CI | kairon |

---

## T4 — R49: metaos Probe Actions

| Finding | Severity | Action |
|:--------|:---------|:-------|
| metaos `.omo/` **does not exist** | **high** | No governance plane at all |
| No AppendOnlyLog patterns found | ✅ | Lower persistence risk |
| INTERFACE.yaml exists but limited | low | Protocol contract exists |

**Required tasks**:

| Task ID | Description | Owner |
|:--------|:------------|:------|
| MET-01 | Initialize `.omo/` governance plane for metaos | metaos |
| MET-02 | Register missing `.omo/` plane as blocking debt for P2 | omo |

---

## T5 — R50: gbrain Probe Actions

| Finding | Severity | Action |
|:--------|:---------|:-------|
| gbrain has JSONL writers | **high** | Non-atomic append paths in TypeScript |
| gbrain has non-atomic overwrite paths | **high** | `write_text` without tempfile+fsync |
| No zod schema validation on JSONL writes | **high** | Untracked raw append |
| gbrain is TS (different toolchain) | medium | Cross-repo governance requires TS-compatible patterns |

**Required tasks**:

| Task ID | Description | Owner |
|:--------|:------------|:------|
| GBR-01 | Audit gbrain JSONL writers; replace with zod-schema-checked AppendOnlyLog | gbrain |
| GBR-02 | Fix non-atomic overwrite paths (use tempfile+fsync+replace) | gbrain |
| GBR-03 | Register gbrain persistence risk as blocking debt for P2 | omo |

---

## Cross-Repo Governance Readiness Table

| Repo | `.omo/` plane | JSONL risk | Atomic writes | Lint gate | Audit coverage |
|:----|:------------:|:----------:|:-------------:|:---------:|:--------------:|
| **kairon** | ✅ | 🔴 high | ⚠️ partial | ✅ | ✅ R46 |
| **metaos** | ✅ (2026-06-11 骨架) | 🟢 low | 🟢 N/A | ✅ | ⚠️ none |
| **gbrain** | ❌ **missing** | 🔴 high | 🔴 non-atomic | ⚠️ TS | ⚠️ none |
| **runtime** | ❌ **missing** | 🟢 low | 🟢 | ✅ | ✅ |
| **omo** | ✅ (SSOT) | 🟢 | 🟢 | ✅ | ✅ |

**Legend**: 🔴 blocks P2 / 🟡 needs work / 🟢 ready
**Note**: metaos `.omo/` created as skeleton on 2026-06-11; gbrain and runtime `.omo/` are confirmed absent at time of audit.

---

## Gate B2 Evidence

| Gate criterion | Result | Evidence |
|:---------------|:------|:---------|
| R46-R50 findings referenced from OPC task plan | ✅ | KAI-*/MET-*/GBR-* defined in doc table; `.omo/tasks/planned/OPC-P15-KAIRON-METAOS-GBRAIN.yaml` (5 tasks, status=planned) exists on filesystem |
| kairon classified as real multi-package workspace | ✅ | 16-package workspace acknowledged; D005 carried from P0 |
| metaos and gbrain missing `.omo/` planes are explicit debt/tasks | ✅ | MET-01, D006, GBR-03 as debt items; gbrain `.omo/` confirmed absent |
| Cross-repo metrics expectations attached to later phase gates | ⚠️ conditional | P2+ gates reference audit-rollout; no automated enforcement |

**Gate B2 verdict**: passed as documentation baseline. `.omo/tasks/planned/OPC-P15-KAIRON-METAOS-GBRAIN.yaml` exists with 5 planned tasks. KAI-*/MET-*/GBR-* follow-up items carried into P2 as OMO-registered debt.

---

## Task/Debt/Doc Boundary (P1.5 Deliverables)

P1.5 generated follow-up items across three OMO surfaces. This table distinguishes them.

| ID | Description | Surface | File | Status |
|:---|:------------|:-------|:-----|:------|
| KAI-01 | kairon JSONL write audit + schema check | **planned task** | `.omo/tasks/planned/OPC-P15-KAIRON-METAOS-GBRAIN.yaml` | planned |
| KAI-02 | kairon 16-package governance registration | **planned task** | `.omo/tasks/planned/OPC-P15-KAIRON-METAOS-GBRAIN.yaml` | planned |
| KAI-03 | kairon lint/metrics gate to CI | **doc carry-in** | (document only — deferred to kairon CI owner workflow) | — |
| MET-01 | metaos .omo/ initialization + population | **planned task** | `.omo/tasks/planned/OPC-P15-KAIRON-METAOS-GBRAIN.yaml` | planned |
| MET-02 | register missing .omo/ plane as blocking P2 debt | **formal debt** | `.omo/debt/items/DEBT-OMC-METAOS-OMO-PLANE.yaml` | registered |
| GBR-01 | gbrain JSONL writers audit + atomic write remediation | **planned task** | `.omo/tasks/planned/OPC-P15-KAIRON-METAOS-GBRAIN.yaml` | planned |
| GBR-02 | gbrain .omo/ governance plane initialization | **planned task** | `.omo/tasks/planned/OPC-P15-KAIRON-METAOS-GBRAIN.yaml` | planned |
| GBR-03 | register gbrain persistence risk as blocking P2 debt | **formal debt** | `.omo/debt/items/DEBT-OMC-GBRAIN-PERSISTENCE.yaml` | registered |
| D001-D010 | P0 documentation drift items | **doc carry-in** | (document only — registered in OPC-PHASE0-BASELINE.md) | — |

**Summary**:
- **5 planned tasks** → `.omo/tasks/planned/OPC-P15-KAIRON-METAOS-GBRAIN.yaml`
- **2 formal debt items** → `.omo/debt/items/DEBT-OMC-*.yaml` (MET-02→METAOS, GBR-03→GBRAIN) + 1 existing (KAIRON)
- **2 doc carry-ins** → KAI-03 (lint CI gate), D001-D010 (drift items) — not OMO-registered, deferred to owner workflows

---

## Signal

```
opc_phase15_cross_repo_governance_baseline_ready
```

Gate B2 passes as documentation baseline. `.omo/tasks/planned/` file exists with 5 planned tasks. Cross-repo persistence risks registered as formal OMO debt (3 items in `.omo/debt/items/`).

| Event | Detail |
|:------|:-------|
| R46 `audit-rollout --include-metrics` confirmed | Active governance capability; not wired into OPC gates yet |
| R47 `plot-metrics.py` confirmed | Observability tool exists; not wired into OPC dashboard |
| R48 kairon probe findings → 3 tasks (KAI-01/02/03) | JSONL persistence risk is primary blocker |
| R49 metaos probe findings → 2 tasks (MET-01/02) | Missing `.omo/` plane is primary blocker |
| R50 gbrain probe findings → 3 tasks (GBR-01/02/03) | JSONL + non-atomic writes are primary blockers |
| Cross-repo readiness table | kairon 🔴, gbrain 🔴, metaos 🔴 for P2 memory prerequisites |
| D001-D010 still proposed | None formally registered in `.omo/debt/` |

---

## Retrospective

- **Key finding**: kairon, gbrain, and metaos all have at least 🔴-level persistence risk that blocks P2 (trusted memory).
- **OMO debt registration**: 3 formal debt items registered (DEBT-OMC-KAIRON-JSONL, DEBT-OMC-METAOS-OMO-PLANE, DEBT-OMC-GBRAIN-PERSISTENCE). D001-D010 remain proposed doc drift items, not yet formally registered.
- **Gate B2: closed as documentation baseline**. `.omo/tasks/planned/OPC-P15-KAIRON-METAOS-GBRAIN.yaml` exists (5 tasks). Cross-repo persistence risks registered as formal OMO debt (DEBT-OMC-KAIRON-JSONL, DEBT-OMC-METAOS-OMO-PLANE, DEBT-OMC-GBRAIN-PERSISTENCE). P1.5 is now the governance baseline for P2.
