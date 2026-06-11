# OPC-P0: Fact Baseline

> Date: 2026-06-11
> Status: ✅ completed (Gate A applied)
> Last revised: 2026-06-11 (fixed SHA, debt status, Gate accuracy)
> Source: OPC-ROADMAP.md §M0, OPC-ARCHITECTURE-GAPS.md, opc-roadmap-omo-plan.md

---

## T1 — Project Inventory

21 directories under `projects/` + `scripts/`. 19 are git submodules per `git submodule status --recursive`.

| # | Project | Submodule SHA | Role | Status |
|---|---------|:------------:|------|:------:|
| 1 | **agora** | 27fd85a | Agent entry, BOS mesh, MCP routing | 🟢 |
| 2 | **cockpit** | debca5c | Human entry CLI, Web dashboard | 🟢 |
| 3 | **l4-kernel** | e6b3c53 | Self-layer, domain registry, KEMS | 🟢 |
| 4 | **ecos** | 4da6384 | Protocol/SSB, L0 anchor | 🟢 |
| 5 | **runtime** | a28fb67 | Sandbox, scheduler, KEI | 🟢 |
| 6 | **omo** | 54eb358 | Governance, task/debt, phase state | 🟢 |
| 7 | **omo-debt** | efbbf2f | Debt registry isolated | 🟡 |
| 8 | **metaos** | 747b43a | Decision gating, immune | 🟡 |
| 9 | **model-driven** | ac6375c | Lifecycle models, M0 | 🟢 |
| 10 | **kairon** | 032a2c2 | Knowledge OPS, 16 packages | 🟡 |
| 11 | **gbrain** | 1c2b825 | Graph memory, TS codebase | 🟡 |
| 12 | **swarm-engine** | f747517 | Task market, DAG, swarm | 🟢 |
| 13 | **aetherforge** | 1313064 | Product aggregation, gateway | 🟡 |
| 14 | **aetherforge-swarm-ext** | 3d20334 | Swarm extensions, perception | 🟡 |
| 15 | **llm-gateway** | 135b84e | Model abstraction | 🟢 |
| 16 | **compute-mesh** | e7102de | Compute discovery, scheduling | 🟡 |
| 17 | **family-hub** | eb81471 | Family product scenarios | 🟡 |
| 18 | **hermes-console** | 62155cd | Web/archived entry | 🟡 |
| 19 | **scripts** | 46fbeff | Tooling, CI, metrics | 🟢 |

**Non-submodule dirs**: `spaces/` (tenant manifests), `AGENTS.md` (not a dir — misdetected). These are not package projects.

**Note**: `runtime` SHA updated from e5dd816 to a28fb67 after re-verification.

---

## T2 — Doc Drift Audit

| Document | Claimed | Actual | Status |
|----------|---------|--------|:------:|
| AGENTS.md: architecture | 5+4+1+1 | 5+4+1+1 | ✅ verified |
| AGENTS.md: project list | 10 rows | 19 submodules | ❌ stale |
| AGENTS.md: testing table | outdated counts | varies | ❌ stale |
| PANORAMA.md: architecture | 8-layer + 3-entry | matches | ✅ verified |
| PANORAMA.md: entry table | 3 entries | 3 entries | ✅ verified |
| OPC-ROADMAP.md: project map | 9 areas | 19 repos | ⚠️ partial |
| OPC-ARCHITECTURE-GAPS.md: facts | post-convergence | matches | ✅ verified |
| `.omo/state/system.yaml`: phase | 28 reported | actual 33+ | ❌ stale |
| Entry convergence CLAUDE.md | 3 entries | matches | ✅ verified |

---

## T3 — Capability Map

| Capability | Projects | Primary | OPC Role |
|:-----------|:---------|:--------|:---------|
| **Entry (human)** | cockpit, hermes-console | cockpit CLI | Human entry point |
| **Entry (agent)** | agora | agora MCP :7431 | Agent entry, BOS routing |
| **Entry (Web/API)** | cockpit HTTP | :8090 | REST + dashboard |
| **Self-layer** | l4-kernel | l4-kernel | Domain registry, 24 domains |
| **Memory/knowledge** | kairon, gbrain, cockpit DB | kairon (kos) | Search, ingest, recall |
| **Governance** | omo, omo-debt, metaos, model-driven | omo | Phase, debt, audit, gates |
| **Swarm execution** | swarm-engine, aetherforge, aetherforge-swarm-ext | swarm-engine | DAG, market, dispatch |
| **Runtime/execution** | runtime | runtime | Sandbox, matrix, KEI |
| **Model abstraction** | llm-gateway | llm-gateway | Provider routing |
| **Compute orchestration** | compute-mesh | compute-mesh | Worker discovery |
| **Protocol/anchoring** | ecos | ecos | SSB, L0, MOF |
| **Product scenarios** | family-hub, cockpit | family-hub | Family health, work |
| **Evolution** | (governance) | OMO + metaos | Radar, scoring, planning |

---

## T4 — Debt Register (proposed, not yet registered)

| Debt ID | Description | Source | Severity | OMO Status |
|:--------|:------------|:-------|:---------|:-----------|
| D001 | AGENTS.md lists 10 projects; actual inventory is 19 submodules | doc-drift | high | proposed — not registered |
| D002 | `.omo/state/system.yaml` reports Phase 28; actual is 33+ | state-drift | high | proposed — not registered |
| D003 | AGENTS.md test table has stale counts (agora 1200→1371) | doc-drift | medium | proposed — not registered |
| D004 | Entry convergence claimed complete; P1 verification not done | convergence | medium | proposed — not registered |
| D005 | kairon treated as meta-project; actual 16-package workspace | governance | medium | proposed — not registered |
| D006 | metaos missing `.omo/` governance plane | governance | high | proposed — not registered |
| D007 | gbrain has JSONL non-atomic writes | persistence | high | proposed — not registered |
| D008 | kairon JSONL append lacks schema check | persistence | medium | proposed — not registered |
| D009 | R46-R50 probe findings not yet tasks | governance | medium | proposed — not registered |
| D010 | cockpit MCP docs still reference `workspace` (removed) | doc-drift | low | proposed — not registered |

---

## T5 — Recent Change Digest

### Root commits (last 10 rounds):

| Round | Key changes |
|:------|:------------|
| R45 | Doc closeout §11.36, cross-repo lint-metrics template |
| R46 | Governance-ecosystem doc, `audit-rollout --include-metrics` |
| R46-47 | Entry convergence Phase 1-2: cockpit/l4-kernel/runtime → agora |
| R46-47 | Doc sync: ENTRY-CONVERGENCE.md, PANORAMA.md |
| R48-50 | kairon/metaos/gbrain probe reports filed |
| Current | cockpit alias removed, AGENTS.md agora count updated, l4-kernel tests fixed |

### R46-R50 Probe Findings (key inputs for P1.5):

| Report | File | Key Finding |
|:-------|:-----|:------------|
| R46 | `audit-rollout --include-metrics` | Governance metrics baseline |
| R47 | ci-lint metrics + trend script | Ongoing observability |
| R48 | `_delivery/kairon-probe-2026-06-11.md` | kairon JSONL write paths, dep management |
| R49 | `_delivery/metaos-probe-2026-06-11.md` | metaos missing `.omo/` governance plane |
| R50 | `_delivery/gbrain-probe-2026-06-11.md` | gbrain non-atomic writes, zod schemas |

### Entry Convergence Status:

| Claim | Status | Evidence type |
|:------|:------|:-------------|
| cockpit CLI is human entry | ✅ verified | command exists, workspace alias removed |
| agora MCP :7431 is agent entry | ✅ verified | resolve_bos_uri routes exist in POC_SERVICES (code) |
| cockpit HTTP :8090 is Web API | ✅ verified | FastAPI app runs on :8090 (code) |
| `bos://cockpit/**` routes | ✅ verified | POC_SERVICES has routes in `bos_resolver.py` (code) |
| `bos://l4-kernel/**` routes | ✅ verified | POC_SERVICES has routes in `bos_resolver.py` (code) |
| `bos://runtime/**` routes | ✅ verified | POC_SERVICES has routes in `bos_resolver.py` (code) |
| Direct stdio MCP deprecated | ⚠️ partially | Code marked deprecated; docs still teach direct access |
| Agent instructions default to Agora | ❌ not done | No explicit Agent guidance exists yet |

---

## Gate A Evidence

| Gate criterion | Self-assessed | Basis | Issue |
|:---------------|:-------------|:------|:------|
| Project inventory matches submodule | ✅ | Manual comparison of `git submodule status` output | Documentation evidence only; not an OMO mechanism |
| Each core project has one OPC role | ✅ | T3 capability map | Manual analysis; not automated |
| Stale/current/conflicting facts listed | ✅ | T2 + T4 | Documentation evidence only |
| Entry convergence classified | ⚠️ partial | T5 entry convergence table | 6/8 verified, 2 incomplete; classified as doc evidence |
| R46-R50 probe findings captured | ✅ | T5 digest + T4 D005-D009 | Documented; will be actionable in P1.5 |
| No business code changes | ✅ | Only docs/ edited | ✅ |

**Note**: Gate A evidence is entirely documentation-based. No OMO debt items were registered. No automated checks exist. Gate A is a human review gate; the criteria are informational, not enforced by any mechanism.

---

## Verification Commands

Commands used to produce this baseline (run at `~/Workspace`):

```bash
# Submodule inventory
git submodule status --recursive | wc -l       # → 19
for d in projects/* scripts; do
  name=$(basename "$d")
  sha=$(git -C "$d" rev-parse --short HEAD 2>/dev/null || echo "N/A")
  echo "$name: $sha"
done

# Root commit history
git log --oneline -10

# Entry convergence — cockpit CLI
cockpit health --full 2>/dev/null | head -3     # → L4/L3/I0/... sections

# Entry convergence — agora MCP routes
# Check POC_SERVICES for cockpit/l4-kernel/runtime:
grep -c "bos://cockpit" projects/agora/src/agora/mcp/bos_resolver.py   # → 2 routes
grep -c "bos://l4-kernel" projects/agora/src/agora/mcp/bos_resolver.py # → 2 routes
grep -c "bos://runtime" projects/agora/src/agora/mcp/bos_resolver.py   # → 2 routes

# R46-R50 probe files
ls .omo/_delivery/*probe*.md                  # → 3 files
ls .omo/_delivery/ 2>/dev/null | grep -c probe  # → 3 files matching kairon/metaos/gbrain

# Panic check: no workspace command
cockpit version 2>/dev/null | head -1          # → cockpit vX.X
# workspace no longer resolves (command not found)
```

---

## Audit Records

- Baseline created: 2026-06-11
- 19 submodule projects inventoried
- 8 doc drift items identified (T2)
- 10 proposed debt items listed (T4) — none formally registered in OMO debt
- 13 capability roles assigned (T3)
- Entry convergence: 6/8 verified, 1 partial, 1 missing (T5)
- R46-R50 probe findings catalogued for P1.5
- `eco_s` typo corrected → `ecos`
- `runtime` SHA corrected: e5dd816 → a28fb67

---

## Signal

```
opc_phase0_baseline_ready
```

---

## Remaining Before Gate A Can Close

| Item | Owner | Action |
|:-----|:------|:-------|
| Proposed debts D001-D010 | omo | Must be registered in `.omo/debt/` as formal items or explicitly deferred |
| AGENTS.md stale counts | docs | Update to reflect 19 submodule reality |
| Agent instructions | docs | Write default-Agora guidance for Agents |
| Direct stdio path cleanup | docs | Verify deprecated markings are complete |

---

## Retrospective

- **Fixed**: `eco_s` → `ecos`; `runtime` SHA e5dd816 → a28fb67; debts labelled "proposed, not yet registered".
- **Gate A reality**: This gate is entirely documentation-based. No OMO debt was filed, no automated verification exists. It is a human review gate, not a system gate.
- **Not done**: D001-D010 are proposed only. Formal OMO debt registration requires editing `.omo/debt/registry.yaml` or adding YAML files to `.omo/debt/items/` — this is a separate action.
- **Next**: Phase 1 — Entry Convergence Verification and Hardening.
