# OPC-P2: P2 Readiness Checklist

> Date: 2026-06-11
> P1: conditionally passed (Gate B accepted as conditional)
> P1.5: documentation/governance baseline for P2 (Gate B2 accepted)
> P2: implementation in progress (T4 complete, T2 wired, C1+C2 sub-gates passed, C3/C4 pending)
> P3: not yet opened (P2 Gate C pending)
> Gate C: not yet passed (C1+C2 closed; C3/C4 open)

---

## Pre-P2 Prerequisite Verification

### Persistence Risk Resolution

| Risk ID | Description | Status | Action |
|:--------|:------------|:------|:-------|
| KAI-01 | kairon JSONL write paths need schema check | 📝 registered debt | `DEBT-OMC-KAIRON-JSONL.yaml` → P2 may proceed with this as known risk |
| GBR-01/02 | gbrain non-atomic writes + no schema | 📝 registered debt | `DEBT-OMC-GBRAIN-PERSISTENCE.yaml` → P2 may proceed with this as known risk |
| MET-01 | metaos .omo/ initialized (skeleton) | ✅ resolved | `.omo/state/system.yaml` created on 2026-06-11 |

### OMO Debt Items (Pre-P2)

| Debt ID | File | Severity | Status |
|:--------|:-----|:---------|:------|
| DEBT-OMC-METAOS-OMO-PLANE | `.omo/debt/items/DEBT-OMC-METAOS-OMO-PLANE.yaml` | high | registered |
| DEBT-OMC-KAIRON-JSONL | `.omo/debt/items/DEBT-OMC-KAIRON-JSONL.yaml` | high | registered |
| DEBT-OMC-GBRAIN-PERSISTENCE | `.omo/debt/items/DEBT-OMC-GBRAIN-PERSISTENCE.yaml` | high | registered |

### OMO Tasks (Pre-P2)

| Task ID | File |
|:--------|:----|
| OPC-P15-KAI-01 | `.omo/tasks/planned/OPC-P15-KAIRON-METAOS-GBRAIN.yaml` (5 tasks) |
| OPC-P15-KAI-02 | ~same~ |
| OPC-P15-MET-01 | ~same~ |
| OPC-P15-GBR-01 | ~same~ |
| OPC-P15-GBR-02 | ~same~ |
| OPC-P2-MEMORY-SPINE | `.omo/tasks/done/OPC-P2-MEMORY-SPINE.yaml` |

### Carried Debt (P0 D001-D010)

| Debt | Status |
|:-----|:------|
| D001-D010 | carried as proposed debt; not yet formally registered in `.omo/debt/items/` |

---

## P2 Start Conditions

### Meets P2 Planning Criteria

| Criterion | Status | Evidence |
|:----------|:------|:---------|
| P0 baseline complete | ✅ | `docs/OPC-PHASE0-BASELINE.md` |
| P1 entry convergence hardened | ✅ conditional | `docs/OPC-PHASE1-CONVERGENCE.md` |
| P1.5 cross-repo governance baseline | ✅ | `docs/OPC-PHASE15-GOVERNANCE.md` |
| Persistence risks registered | ✅ | 3 debt items in `.omo/debt/items/` |
| Memory design tasks completed | ✅ | `.omo/tasks/done/OPC-P2-MEMORY-SPINE.yaml` |
| Readiness table reflects reality | ✅ | OPC-PHASE15-GOVERNANCE.md corrected |

### P2 Design-Phase Delivery Status

| Task | Status | Note |
|:-----|:------|:-----|
| P2-T1 memory boundary | ✅ completed | 5 zones defined |
| P2-T2 bos://memory/** | ✅ completed | 9 routes + response contract |
| P2-T3 recall flow | ✅ completed | 5-step flow designed |
| P2-T4 source metadata | ⚠️ partial → ✅ completed | **8/8 fields** in all local search results |
| P2-T5 memory metrics | ✅ completed | 5 quality metrics designed |

### Blocking Risks (Accepted)

| Risk | Acceptance |
|:-----|:-----------|
| kairon JSONL: raw writes without schema validation | Accept — P2 bootstraps with KOS local search; schema hardening follow-up |
| gbrain non-atomic overwrite paths | Accept — P2 bootstrap uses cockpit local search; gbrain hardening follows |
| metaos .omo/ state population | Accept — skeleton exists; full population follows DAEMON activation |

---

## Signal

```
opc_p2_design_complete_implementation_pending
opc_p2_gate_c1_local_contract_passed  (2026-06-11)
opc_p2_gate_c2_kos_activation_passed  (2026-06-11)
```

P2 — Personal Memory Spine — T4 complete (8/8 metadata). T2 response contract wired into CLI search output (text + JSON consistent). Gate C sub-gate C1 (Local Contract Hardening) and C2 (KOS Activation) passed with 15/15 tests and runtime evidence (real kairon/kos MCP stdio invocation returns 10 items for q='kairon'). C3 (Vault Activation) and C4 (Real Trace Closure) still open. Gate C not yet passed.
