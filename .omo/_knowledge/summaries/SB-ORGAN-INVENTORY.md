---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P55 R2: summaries/ 根目录历史快照批量归档, 当前状态以 .omo/state/system.yaml + .omo/tasks/active/ 为准"
---
# Phase 11 Wave 1 — SharedBrain organ inventory (T1.6)

> Scope: `projects/SharedBrain/`
> Method: top-level `organs/` + `nucleus/` directory scan with rough `*.py` / test-file counts
> Normalization note: this inventory uses the underscore-style `D_*` organ dirs and `Z-*` nucleus dirs as canonical. For tests, it merges both underscore and hyphen variants under `tests/unit/organs/` (e.g. `D_Execution` + `D-Execution`) to avoid under-counting.
> Dependency note: `Top internal deps` is a **heuristic** derived from counting `from X import ...` / `import X` statements under each organ and keeping only internal-looking module prefixes (`nucleus.*`, `organs.*`, `SharedBrain.*`). It is **not** a full dependency graph.

## Reality check vs the Phase 11 shorthand

The Phase 11 plan refers to a “14-organ inventory,” but the live repository currently exposes **19 canonical `D_*` organ domains** plus **6 canonical `Z-*` nucleus domains**. Wave 1 should treat the inventory as a **live topology snapshot**, not as a frozen legacy count.

## Organ inventory

| Organ | Status | Py files | LOC | Test files | Top internal deps (heuristic) | Snapshot |
|---|---|---:|---:|---:|---|---|
| `D_Cloud` | ✅ ACTIVE | 21 | 5,278 | 2 | `nucleus.Z_Microkernel(7)` | Cloud/integration edge surface |
| `D_Continuity` | ✅ ACTIVE | 15 | 4,143 | 3 | `nucleus.Z_Microkernel(11)` | Continuity / resilience support |
| `D_Economy` | ✅ ACTIVE | 38 | 7,038 | 44 | `nucleus.Z_Microkernel(36)`, `nucleus.Z_Spore(4)`, `organs.D_Execution(1)` | Resource/economy domain |
| `D_Excretion` | ✅ ACTIVE | 48 | 7,731 | 9 | `nucleus.Z_Microkernel(38)`, `organs.D_Memory(2)` | Cleanup / residue management |
| `D_Execution` | ✅ ACTIVE | 275 | 55,725 | 172 | `nucleus.Z_Microkernel(198)`, `nucleus.Z_Spore(69)`, `nucleus.shared(3)` | Largest organ by code volume; execution/orchestration core |
| `D_Extension` | ✅ ACTIVE | 20 | 5,496 | 7 | `nucleus.Z_Microkernel(13)`, `nucleus.Z_Spore(7)`, `organs.D_Execution(2)` | Extension/plugin surface |
| `D_Gateway` | ✅ ACTIVE | 98 | 26,516 | 55 | `nucleus.Z_Microkernel(54)`, `nucleus.Z_Spore(12)`, `organs.D_Voice(5)` | MCP / gateway / edge communications hub |
| `D_Genesis` | ✅ ACTIVE | 69 | 20,374 | 60 | `nucleus.Z_Microkernel(58)`, `nucleus.Z_Spore(8)`, `organs.D_Memory(3)` | Bootstrapping / evolution surface |
| `D_Governance` | ✅ ACTIVE | 131 | 27,200 | 42 | `nucleus.Z_Microkernel(55)`, `nucleus.Z_Spore(3)`, `organs.D_Memory(2)` | Policy/governance heavy surface |
| `D_Harness` | ✅ ACTIVE | 15 | 2,366 | 1 | `nucleus.Z_Microkernel(18)`, `organs.D_Execution(3)` | Harness/test support domain |
| `D_Harvest` | ✅ ACTIVE | 110 | 29,394 | 23 | `organs.D_Governance(2)`, `nucleus.Z_Microkernel(1)`, `organs.D_Memory(1)` | Best-tested organ domain in the repo |
| `D_Immunity` | ✅ ACTIVE | 102 | 22,475 | 58 | `nucleus.Z_Microkernel(77)`, `nucleus.Z_Spore(3)`, `organs.D_Memory(1)` | Security / safety layer |
| `D_Intelligence` | ✅ ACTIVE | 20 | 4,007 | 2 | `nucleus.Z_Microkernel(9)` | Intelligence layer |
| `D_KnowledgeIntegration` | ✅ ACTIVE | 39 | 6,007 | 10 | `organs.D_Memory(9)`, `nucleus.Z_Microkernel(3)` | Semantic integration layer |
| `D_Logos` | ✅ ACTIVE | 51 | 16,857 | 17 | `nucleus.Z_Microkernel(22)`, `nucleus.Z_Spore(1)` | Documentation / reasoning layer |
| `D_Memory` | ✅ ACTIVE | 133 | 42,359 | 80 | `nucleus.Z_Microkernel(105)`, `nucleus.Z_Spore(10)` | Memory/indexing core; second-largest organ by LOC |
| `D_Monitoring` | ✅ ACTIVE | 74 | 15,549 | 19 | `nucleus.Z_Microkernel(47)`, `nucleus.Z_Spore(6)`, `organs.D_Harvest(1)` | Metrics / topology / health |
| `D_Voice` | ✅ ACTIVE | 11 | 2,631 | 1 | `organs.D_Continuity(2)`, `nucleus.Z_Spore(1)`, `organs.D_Execution(1)` | Voice surface |
| `D_Window` | ⚠️ STUB | 1 | 5 | 0 | — | Placeholder/thin surface |

## Nucleus inventory

| Nucleus domain | Py files | LOC | Snapshot |
|---|---:|---:|---|
| `Z-Core` | 13 | 1,188 | Core law/kernel layer |
| `Z-Extension` | 4 | 223 | Extension kernel layer |
| `Z-Gateway` | 3 | 229 | Gateway kernel bridge |
| `Z-Genesis` | 7 | 521 | Genesis kernel slice |
| `Z-Microkernel` | 273 | 57,742 | Largest nucleus surface; runtime/router/control core |
| `Z-Spore` | 135 | 25,528 | Genome/base substrate |

## High-signal findings

1. **Execution + Microkernel dominate the codebase**: `D_Execution` (55.7k LOC) and `Z-Microkernel` (57.7k LOC) are the two largest structural centers of gravity.
2. **Testing is concentrated in a few large domains**: `D_Execution` (172 test files) and `D_Memory` (80) dominate, followed by `D_Genesis` (60), `D_Immunity` (58), and `D_Gateway` (55).
3. **Topology drift exists at the directory level**: alias/compatibility dirs (`D-Execution`, `Z_Core`, `Z_Microkernel`, etc.) still exist beside canonical dirs. That is acceptable for compatibility, but inventory/reporting should normalize to one naming form to avoid false double-counting.

## Wave 1 implication

If Phase 11 intends to establish a reliable capability baseline, these organ/nucleus totals should become the **reference inventory** for follow-on debt work:

- prioritize `D_Execution`, `D_Governance`, `D_Gateway`, `D_Harvest`, `D_Memory`, and `Z-Microkernel`
- explicitly decide whether alias dirs remain part of the supported topology or are merely compatibility shims
