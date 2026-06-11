# OPC-P1: Entry Convergence Verification and Hardening

> Date: 2026-06-11
> P0 carry-in: entry items 7-8 incomplete, D001-D010 proposed debt
> Status: ✅ completed
> Source: OPC-ROADMAP.md §M1, OPC-PHASE0-BASELINE.md

---

## P0 Carry-In Items

| Item | Original Status | P1 Action |
|:-----|:--------------|:----------|
| Direct stdio MCP deprecated (P0: ⚠️ partial) | Code marked, docs not fully updated | ✅ Updated AGENTS.md with explicit deprecated notice |
| Agent instructions default to Agora (P0: ❌ not done) | No guidance existed | ✅ Added rules 12-14 to AGENTS.md |
| D001-D010 (proposed debt) | Not registered | Carried forward to P1.5 — no formal `.omo/debt/` registration yet |

---

## T1 — Entry Contract Verification

### Human entry: `cockpit CLI`

| Check | Result |
|:------|:------:|
| `cockpit` command resolves | ✅ `cockpit v0.4.0` |
| `cockpit health --full` works | ✅ 7-layer check |
| `cockpit search` works | ✅ SQLite + --all BOS |
| `workspace` alias removed | ✅ command not found |

### Agent entry: `agora MCP :7431`

| Check | Result |
|:------|:------:|
| POC_SERVICES has cockpit routes | ✅ 2 routes (`bos://governance/cockpit/context`, `bos://cockpit/context`) |
| POC_SERVICES has l4-kernel routes | ✅ 2 routes (`bos://governance/l4-kernel/domains`, `bos://l4-kernel/domains`) |
| POC_SERVICES has runtime routes | ✅ 6 routes (4 agent-runtime + 2 runtime) |
| KNOWN_SERVICES has cockpit | ✅ "Cockpit MCP — 研究(12)、状态(3)、L4桥接" |
| KNOWN_SERVICES has l4-kernel | ✅ "L4 Domain Kernel — 24域统一注册表" |
| KNOWN_SERVICES has runtime | ✅ "Runtime MCP — 服务注册表、健康监控" |
| `_meta_discover()` works | ✅ 41 services, 5 domains |

### Web/API entry: `cockpit HTTP :8090`

| Check | Result |
|:------|:------:|
| FastAPI app exists | ✅ `dashboard_server.py` |
| Endpoints: `/api/status`, `/api/context`, `/api/cards`, `/api/services` | ✅ 16+ routes |
| Port configurable via env | ✅ `COCKPIT_DASHBOARD_PORT` |

---

## T2 — Agora MCP Route Verification

### Cockpit routes

```
bos://cockpit/context → POC_SERVICES → mcp_stdio transport
  → uv run --package cockpit python -m cockpit.scripts.cockpit_mcp
  → KNOWN_SERVICES: ✅ registered
```

### l4-kernel routes

```
bos://l4-kernel/domains → POC_SERVICES → mcp_stdio transport
  → uv run --directory projects/l4-kernel python -m l4_kernel.mcp_server
  → KNOWN_SERVICES: ✅ registered
```

### Runtime routes

```
bos://runtime/health → POC_SERVICES → mcp_stdio transport
  → uv run --directory projects/runtime python -m runtime.mcp_server
  → KNOWN_SERVICES: ✅ registered
```

All three internal MCP services are registered in both KNOWN_SERVICES (launch) and POC_SERVICES (routing). Agora can launch and route to all three.

---

## T3 — BOS Entry Route Verification

| Route | POC_SERVICES | Transport | Verified |
|:------|:------------:|:---------:|:--------:|
| `bos://governance/cockpit/context` | ✅ | mcp_stdio | ✅ |
| `bos://cockpit/context` (alias) | ✅ | mcp_stdio | ✅ |
| `bos://governance/l4-kernel/domains` | ✅ | mcp_stdio | ✅ |
| `bos://l4-kernel/domains` (alias) | ✅ | mcp_stdio | ✅ |
| `bos://capability/runtime/health` | ✅ | mcp_stdio | ✅ |
| `bos://runtime/health` (alias) | ✅ | mcp_stdio | ✅ |

---

## T4 — Deprecated Path Cleanup

| Path | Status | Action |
|:-----|:------|:-------|
| cockpit MCP stdio | ✅ marked deprecated | `cockpit_mcp.py:main()` docstring |
| l4-kernel MCP stdio | ✅ not a direct entry in docs | Registered only as Agora route |
| runtime MCP stdio | ✅ not a direct entry in docs | Registered only as Agora route |
| AGENTS.md stdio config examples | ✅ not present | No direct MCP config examples found |
| AGENTS.md Agent guidance | ✅ updated | Rules 12-14 added |
| `workspace` CLI alias | ✅ removed | pyproject.toml cleanup (earlier) |

---

## T5 — Journey Probes Update

Updated `docs/JOURNEY-PROBES.md`: journeys E and F rewritten with `Agent → agora MCP → bos://` as primary paths, with direct MCP paths as collapsed compatibility appendix. Top-of-document header updated with entry convergence notice.

### Primary agent probe pattern (journeys E and F)

```
Agent (now)
  → agora MCP :7431
  → resolve_bos_uri("bos://cockpit/context")   ← 取代 cockpit MCP stdio
  → resolve_bos_uri("bos://l4-kernel/domains")  ← 取代 l4-kernel MCP stdio
  → resolve_bos_uri("bos://runtime/health")     ← 取代 runtime MCP stdio
```

---

## Gate B Evidence

| Gate criterion | Result | Evidence |
|:---------------|:------|:---------|
| Agent docs default to Agora MCP | ✅ | AGENTS.md rules 12-14 |
| Internal MCP services are implementation details | ✅ | Deprecated markings, only Agora routes documented as primary |
| Entry journey probes exist | ✅ | This document + JOURNEY-PROBES.md |
| Direct cockpit/l4-kernel/runtime MCP probes deprecated | ✅ | cockpit_mcp.py + AGENTS.md |
| Route behavior validated, not only documented | ⚠️ partially | POC_SERVICES service lookup verified programmatically; no live subprocess `resolve_bos_uri()` execution test run |

---

## Audit Records

| Event | Detail |
|:------|:-------|
| AGENTS.md updated | Rules 12-14 added: Agent defaults to Agora, 3-entry architecture, BOS-only cross-layer calls |
| PANORAMA.md entry table | Already has 3-entry table and deprecated entries section |
| Deprecated markings verified | cockpit_mcp.py main() docstring, AGENTS.md rules |
| P0 carry-in items addressed | 2 entry items completed; D001-D010 carried forward |

### Runtime Evidence

```
# POC_SERVICES lookup verification (2026-06-11):
✅ bos://cockpit/context     → BosService(transport=mcp_stdio)
✅ bos://l4-kernel/domains   → BosService(transport=mcp_stdio)
✅ bos://runtime/health      → BosService(transport=mcp_stdio)
✅ _meta_discover()          → 41 services, 5 domains
```

---

## Signal

```
opc_phase1_conditionally_passed
```

Gate B conditionally passed for contract and documentation hardening. Route contract verified (POC_SERVICES has all 3 routes). Live `resolve_bos_uri()` subprocess invocation pending. JOURNEY-PROBES.md primary paths rewritten.

| Item | Source | Action |
|:-----|:-------|:-------|
| D001-D010 proposed debts | P0 | OMO formal registration deferred to P1.5 governance process |
| R46-R50 probe findings | R48-50 | Convert to tasks in P1.5 |
| kairon/gbrain/metaos persistence risk | D005-D008 | Remediation prerequisites for P2 memory spine |

---

## Retrospective

- **Verification method**: Manual inspection of POC_SERVICES, KNOWN_SERVICES, AGENTS.md, and source code deprecated markings.
- **No automation**: Route behavior validation was manual (`grep` + `python3 -c`). No automated test verifies Agora → BOS routing for these routes.
- **Entry convergence**: All 3 entries now have verified contracts. Direct stdio entries are deprecated. Agent guidance exists.
- **Gate B: conditionally passed**. Contract and documentation hardening complete (AGENTS.md, JOURNEY-PROBES.md, deprecated markings). Route contract verified via POC_SERVICES lookup. Live `resolve_bos_uri()` subprocess invocation pending. This is not a full pass.
- **Next**: Phase 1.5 — Cross-Repo Governance Baseline (absorb R46-R50 into gates).
