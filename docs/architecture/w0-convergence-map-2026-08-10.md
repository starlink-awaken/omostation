---
lifecycle: contract
owner: governance-team
last_updated: 2026-08-18
title: W0-04 Convergence Map — Legacy Entrances, Duplicate Writers,
type: doc
---
# W0-04 Convergence Map — Legacy Entrances, Duplicate Writers, Consumers, and Retirement Candidates

> **Task**: W0-04 (digital-twin-blueprint-v1.md §25.2)
> **Date**: 2026-08-10
> **Depends on**: W0-01 (read-only baseline)
> **AC**: Every candidate has a Keep / Bridge / Absorb / Retire decision
> **Constraint**: Existing evidence only; no `.omo` modification; no commit

---

## 1. Scope and Method

This map audits the eight convergence domains — **OMO, ECOS, MOF, Agora, BOS, cockpit, L4, family entry** — against four candidate categories:

| Category | Definition |
|---|---|
| Legacy Entrance | An entry surface that has been superseded or is eligible for supersession |
| Duplicate Writer | Two or more code paths that write the same governed state |
| Consumer | A downstream dependency that reads from or routes through a domain |
| Retirement Candidate | A project or surface whose function can be absorbed elsewhere |

### Evidence Sources Read

| Source | Path |
|---|---|
| Architecture contracts | `ARCHITECTURE.md` |
| Layer index | `LAYER-INDEX.md` |
| Project registry | `docs/project-registry.yaml` |
| System panorama | `docs/PANORAMA.md` |
| Architecture evolution | `docs/ARCHITECTURE-EVOLUTION.md` |
| Functional capability map | `docs/FUNCTIONAL-CAPABILITY-MAP.md` |
| Architecture detailed map | `docs/ARCHITECTURE-DETAILED-MAP.md` |
| Mutation surfaces registry | `.omo/_truth/registry/mutation-surfaces.yaml` |
| Internal write profiles | `.omo/_truth/registry/internal-write-profiles.yaml` |
| OMO governance surfaces standard | `.omo/standards/omo-governance-surfaces.md` |
| MOF capabilities registry | `.omo/_truth/registry/mof-capabilities.yaml` |
| Digital twin blueprint | `docs/architecture/digital-twin-blueprint-v1.md` (§25.2 W0-04, W6-02) |
| Multi-agent execution blueprint | `docs/architecture/blueprint-multi-agent-execution-control-v1.md` |
| Vision roadmap | `docs/VISION-ROADMAP.md` |
| Convergence execution status | `docs/CONVERGENCE-EXECUTION-STATUS.md` |
| Strategy closeout | `docs/ARCHITECTURE-STRATEGY-CLOSEOUT-2026-08.md` |
| Port registry | `protocols/port-registry.yaml` |

---

## 2. Convergence Decision Table

> **Decision values**: **Keep** (maintain as-is) · **Bridge** (proxy/compat layer, eventual retirement) · **Absorb** (merge function into canonical owner) · **Retire** (remove entirely)

### 2.1 OMO — Governance Kernel

| # | Component | Category | Decision | Owner | Dependency | Evidence Path | Cutover Note | Rollback Note |
|---|---|---|---|---|---|---|---|---|
| OMO-1 | `omo debt` CLI sub-commands (omo_debt.py) | Duplicate Writer | **Absorb** | omo-team | omo-debt project CLI; `.omo/debt/` state | `mutation-surfaces.yaml::omo-governance-ingress-debt`; `projects/omo/src/omo/omo_debt.py` (per `internal-write-profiles.yaml::debt-review-runtime`) | W6-02 first batch: omo-debt scoring absorbed into omo governance; `omo-debt score` becomes `omo debt score`; old project kept as compat shim for one release | Restore `omo-debt` standalone CLI; revert `omo debt` to thin delegation |
| OMO-2 | omo-debt project (`projects/omo-debt/`) | Retirement Candidate | **Retire** | omo-team | Consumed by omo; no independent runtime | `project-registry.yaml::omo-debt` (layer=L2, role="技术债务评分 CLI"); `ARCHITECTURE-EVOLUTION.md` (Boundary: omo→omo-debt) | After OMO-1 cutover: archive `projects/omo-debt/` to `docs/_archived/omo-debt/`; remove from `project-registry.yaml` | Restore submodule + registry entry; revert any absorbed code paths |
| OMO-3 | Worker direct task writes (`yield_task`, `_fast_track_compaction`, promotion) | Duplicate Writer | **Bridge** | omo-team | `omo_ingress.py` broker; `.omo/tasks/` lifecycle | `omo-governance-surfaces.md` §2.4 lists converged ingress calls; `internal-write-profiles.yaml::worker-task-lifecycle` shows residual direct writes for archive/yield | Already partially converged per §2.4; remaining direct writes (archive, yield) are migration targets; compat layer routes through `omo_ingress` | Keep worker internal write profiles active; revert ingress broker calls to direct writes |
| OMO-4 | OMO AppendOnlyLog (5 consumers) | Consumer | **Keep** | omo-team | audit/bos_metrics/sync/alert/event consumers; fcntl locks | `FUNCTIONAL-CAPABILITY-MAP.md` §3; `ARCHITECTURE-DETAILED-MAP.md` §3.1 ("JSONL 7 consumers 共享 AppendOnlyLog") | No cutover needed; AppendOnlyLog is canonical audit substrate | N/A |
| OMO-5 | `omo governance surfaces` mutation registry | Consumer | **Keep** | governance-team | 30+ registered mutation surfaces; `.omo/_truth/registry/mutation-surfaces.yaml` | `mutation-surfaces.yaml` (execution_entrypoints list); `omo-governance-surfaces.md` §2.4 | Registry is canonical; new surfaces must register | N/A |

### 2.2 ECOS — Protocol Layer (L0)

| # | Component | Category | Decision | Owner | Dependency | Evidence Path | Cutover Note | Rollback Note |
|---|---|---|---|---|---|---|---|---|
| ECOS-1 | `ecos→omo` reverse dependency (mof-state-bridge) | Consumer | **Keep** | ecos-team | omo kernel; recorded exception | `ARCHITECTURE-DETAILED-MAP.md` §2.2 ("ecos→omo 是唯一的 L0→L2 向上依赖, 已记录为例外") | Maintain as documented exception; no new L0→L2 deps allowed | N/A (no alternative path exists) |
| ECOS-2 | ECOS BOS URI calls (→minerva, kos, codeanalyze, metaos, runtime) | Consumer | **Keep** | ecos-team | agora BOS resolver | `ARCHITECTURE-DETAILED-MAP.md` §2.3 (BOS URI runtime call graph) | Cross-layer calls via BOS is canonical pattern | N/A |
| ECOS-3 | ECOS workflow engine (`cockpit workflow`) | Legacy Entrance | **Bridge** | ecos-team | cockpit CLI delegation; W1-04 Ledger Broker API | `FUNCTIONAL-CAPABILITY-MAP.md` §4 (workflow engine via `cockpit workflow`); blueprint W1-04 introduces Ledger Broker API as successor | W1-04 (W3 D3-D4): Ledger Broker provides CLI/MCP/BOS entries; current workflow engine becomes shadow until W6 cutover | Revert to direct `ecos workflow` CLI; disable Ledger Broker |

### 2.3 MOF — Meta-Object Framework

| # | Component | Category | Decision | Owner | Dependency | Evidence Path | Cutover Note | Rollback Note |
|---|---|---|---|---|---|---|---|---|
| MOF-1 | MOF 34 tools (`bin/mof/*`) | Consumer | **Keep** | ecos-team | ecos ssot registry; L0-constraints.yaml | `project-registry.yaml::ecos.mof_tools` (34); `mof-capabilities.yaml` (4-layer architecture: data/knowledge/decision/action) | MOF tools are canonical L0 capability; no convergence needed | N/A |
| MOF-2 | M1 YAML nodes (1196 instances) | Consumer | **Keep** | ecos-team | GaC rules; model-driven M3→M2→M1 bridge | `project-registry.yaml::ecos.m1_yaml` (1196); `ARCHITECTURE-DETAILED-MAP.md` §3.2 (MOF M3→M2→M1) | M1 is canonical governance instance layer; W1-01 defines M2 core types as next evolution | N/A |
| MOF-3 | `model-driven` M0 framework | Consumer | **Bridge** | model-driven-team | ecos M3 schema; consumed by l4-kernel + omo | `project-registry.yaml::model-driven` (layer=M0, "7阶段+门禁"); `ARCHITECTURE-EVOLUTION.md` Evolution Vector 5 | W1-01: MOF compiler generates Pydantic/Zod/DDL from M2; model-driven becomes consumer of generated artifacts rather than independent derivation | Keep model-driven manual derivation; disable compiler output |

### 2.4 Agora — I0 Mesh Layer

| # | Component | Category | Decision | Owner | Dependency | Evidence Path | Cutover Note | Rollback Note |
|---|---|---|---|---|---|---|---|---|
| AGORA-1 | Agora MCP (SSE) — unified agent entry | Consumer | **Keep** | agora-team | BOS resolver; all L2+ services | `PANORAMA.md` §四 (agora MCP = 🟢 已收敛); `ARCHITECTURE.md` §3 (AI agent entry = agora MCP) | Canonical agent entry surface; no new top-level agent entries | N/A |
| AGORA-2 | Agora HTTP (standalone) | Legacy Entrance | **Retire** | agora-team | Never independently existed | `PANORAMA.md` §四 ("agora HTTP — 从未独立存在 → cockpit HTTP") | Already documented as non-existent; ensure no future standalone HTTP surface | N/A (never existed) |
| AGORA-3 | Agora→bus-foundation import dependency | Consumer | **Keep** | agora-team | bus-foundation Omni-Bus | `ARCHITECTURE-DETAILED-MAP.md` §2.1 (agora imports bus); bus-foundation is most-depended project (7 importers) | bus-foundation is canonical event infrastructure | N/A |
| AGORA-4 | Agora converge (federal routing) | Consumer | **Keep** | agora-team | Cross-node discovery | `FUNCTIONAL-CAPABILITY-MAP.md` §6 (联邦路由 via `agora converge`) | Federal routing is canonical for multi-node; currently low usage | N/A |

### 2.5 BOS — Service Routing Domain

| # | Component | Category | Decision | Owner | Dependency | Evidence Path | Cutover Note | Rollback Note |
|---|---|---|---|---|---|---|---|---|
| BOS-1 | BOS URI 5-domain routing (memory/governance/analysis/persona/capability) | Consumer | **Keep** | agora-team | agora resolver; ecos protocol declarations | `ARCHITECTURE.md` §4; `PANORAMA.md` §2.3; `project-registry.yaml::agora.bos_services` (200 services) | BOS is canonical service routing; 5 domains locked per ARCHITECTURE.md §4 | N/A |
| BOS-2 | BOS middleware (rate limiter/circuit breaker/cache) | Consumer | **Keep** | agora-team | BOS resolver internal | `FUNCTIONAL-CAPABILITY-MAP.md` §6 (BOS 中间件: p50/p95/p99 指标) | Middleware is canonical resilience layer | N/A |
| BOS-3 | `bos://capability/` domain (toolbox) | Consumer | **Bridge** | agora-team | toolbox external services (11 L3 instances) | `project-registry.yaml::toolbox.bos_services` (11 services, all active) | Toolbox external services remain bridged through BOS; convergence target is unified capability catalog in cockpit | Restore direct toolbox invocation paths |

### 2.6 Cockpit — L3 Entry Layer

| # | Component | Category | Decision | Owner | Dependency | Evidence Path | Cutover Note | Rollback Note |
|---|---|---|---|---|---|---|---|---|
| COCKPIT-1 | Cockpit CLI — sole human entry | Consumer | **Keep** | cockpit-team | agora (BOS resolve), omo, runtime, l4-kernel | `PANORAMA.md` §四 (cockpit CLI = 🟢 terminal entry); `ARCHITECTURE.md` §3 (human operator entry) | Canonical human entry surface; CLI convergence Phase 3 already completed for 9 domains | N/A |
| COCKPIT-2 | Cockpit HTTP (FastAPI Web Dashboard) | Consumer | **Keep** | cockpit-team | cockpit-ui (Vite/React); API key auth | `PANORAMA.md` §四 (cockpit HTTP = 🟢); `project-registry.yaml::cockpit-ui` (mounted at /) | Canonical web entry; cockpit-ui is presentation layer | N/A |
| COCKPIT-3 | Cockpit MCP (stdio) — DEPRECATED | Legacy Entrance | **Retire** | cockpit-team | Was superseded by agora MCP | `PANORAMA.md` §四 ("cockpit MCP — stdio — 入口收敛 Phase 1 → agora MCP `bos://cockpit/context`") | Already offlined; entry converged Phase 1; ensure no revival | Already retired; no rollback needed |
| COCKPIT-4 | Cockpit→agora BOS delegation pattern | Consumer | **Keep** | cockpit-team | agora `resolve_bos_uri()` | `ARCHITECTURE-DETAILED-MAP.md` §2.3 (cockpit→agora BOS calls); `FUNCTIONAL-CAPABILITY-MAP.md` coverage list | Canonical cross-layer delegation; cockpit does not implement services directly | N/A |
| COCKPIT-5 | hermes-console (archived L3 project) | Retirement Candidate | **Retire** | governance-team | Was independent L3 entry; now converged | `ARCHITECTURE-EVOLUTION.md` Archived Projects ("hermes-console → 入口能力收敛到 cockpit/agora"); `PANORAMA.md` appendix ("hermes-console — ARCHIVED") | Already archived; ensure historical reference removed from active docs | Already retired |
| COCKPIT-6 | agora-dashboard (legacy L3 snapshot) | Retirement Candidate | **Retire** | governance-team | Was independent dashboard; now cockpit-ui | `PANORAMA.md` appendix ("agora-dashboard — LEGACY SNAPSHOT — 独立入口已收敛") | Already legacy; cockpit-ui is successor | Already retired |

### 2.7 L4 — Self-Layer

| # | Component | Category | Decision | Owner | Dependency | Evidence Path | Cutover Note | Rollback Note |
|---|---|---|---|---|---|---|---|---|
| L4-1 | L4-kernel domain registry (28 domains) | Consumer | **Keep** | l4-kernel-team | cockpit context bridge; DOMAIN-INDEX.md | `project-registry.yaml::l4-kernel.domains` (28); `PANORAMA.md` §2.2 (L4 域注册表) | Canonical domain registry; KEMS six-plane health aggregation | N/A |
| L4-2 | L4-kernel MCP (stdio) — DEPRECATED | Legacy Entrance | **Retire** | l4-kernel-team | Was superseded by agora MCP | `PANORAMA.md` §四 ("l4-kernel MCP — stdio — 入口收敛 Phase 2 → agora MCP `bos://l4-kernel/domains`") | Already offlined; entry converged Phase 2; ensure no revival | Already retired |
| L4-3 | L4-kernel SignalBus | Consumer | **Keep** | l4-kernel-team | omo event emission; cockpit health aggregation | `PANORAMA.md` §3.2 ("Signal 发射 → l4-kernel SignalBus") | Canonical signal bus for domain events | N/A |
| L4-4 | L4→cockpit context bridge | Consumer | **Keep** | l4-kernel-team | cockpit l4bridge.py | `PANORAMA.md` §3.3 ("路径 A: cockpit health → L4 Context (l4-kernel bridge)") | Canonical context delivery path for cockpit health checks | N/A |
| L4-5 | Documents CLAUDE.md (global) L4 gateway | Consumer | **Bridge** | l4-kernel-team | `~/Documents/CLAUDE.md` (L4 网关 v5.1) | `CLAUDE.md` §0 (域检测: `~/Documents/` 内 → 先读 Documents CLAUDE.md L4 网关) | L4 gateway exists as routing layer for Documents domain; bridge to unified cockpit context when W2 sovereignty kernel lands | Keep Documents CLAUDE.md as primary L4 gateway |

### 2.8 Family Entry — family-hub

| # | Component | Category | Decision | Owner | Dependency | Evidence Path | Cutover Note | Rollback Note |
|---|---|---|---|---|---|---|---|---|
| FAMILY-1 | family-hub standalone project (`projects/family-hub/`) | Duplicate Writer | **Bridge** | family-hub-team | cockpit coverage; agora BOS `bos://persona/family-hub/health` | `project-registry.yaml::family-hub` (layer=L2, "家庭数字枢纽"); `PANORAMA.md` appendix (family-hub ARCHITECTURE.md exists); `FUNCTIONAL-CAPABILITY-MAP.md` (cockpit coverage includes family-hub) | W6-02 first batch: family entry bridges into cockpit; standalone project kept as compat layer; cockpit `family` subcommand becomes canonical | Restore standalone `family-hub` CLI; revert cockpit family delegation |
| FAMILY-2 | family-hub BOS URI route | Consumer | **Keep** | agora-team | agora resolver | `ARCHITECTURE-DETAILED-MAP.md` §2.3 (cockpit→family-hub `bos://persona/family-hub/health`); `FUNCTIONAL-CAPABILITY-MAP.md` §6 | BOS route remains canonical even after FAMILY-1 bridge; persona domain is stable | N/A |
| FAMILY-3 | family-hub as standalone priority | Retirement Candidate | **Absorb** | governance-team | Vision roadmap deprioritized family-hub | `VISION-ROADMAP.md` ("Family Hub、KEMS 独立产品化和物理多机当前不构成主轴") | Per W6-02: absorb family-hub entry into cockpit; standalone project functions remain available via BOS but not as top-level entry | Restore family-hub as top-level entry point |

### 2.9 Cross-Cutting — Bus Foundation

| # | Component | Category | Decision | Owner | Dependency | Evidence Path | Cutover Note | Rollback Note |
|---|---|---|---|---|---|---|---|---|
| BUS-1 | bus-foundation Omni-Bus (Data/Event/Control) | Duplicate Writer | **Bridge** | bus-team | 7 direct importers; OMO AppendOnlyLog overlaps on event plane | `ARCHITECTURE-DETAILED-MAP.md` §2.1 ("bus-foundation 是被依赖最多的项目, 7 个直接 import"); `FUNCTIONAL-CAPABILITY-MAP.md` §6 (Omni-Bus 三平面) | W6-02 first batch: bridge bus event plane through OMO AppendOnlyLog; bus-foundation keeps Data + Control planes; Event plane converges to OMO audit substrate | Restore bus-foundation Event plane; revert OMO AppendOnlyLog consumer list |

---

## 3. Summary of Decisions

### By Decision

| Decision | Count | Candidates |
|---|---|---|
| **Keep** | 17 | OMO-4, OMO-5, ECOS-1, ECOS-2, MOF-1, MOF-2, AGORA-1, AGORA-3, AGORA-4, BOS-1, BOS-2, COCKPIT-1, COCKPIT-2, COCKPIT-4, L4-1, L4-3, L4-4 |
| **Bridge** | 7 | OMO-3, ECOS-3, MOF-3, BOS-3, L4-5, FAMILY-1, BUS-1 |
| **Absorb** | 2 | OMO-1, FAMILY-3 |
| **Retire** | 5 | OMO-2, AGORA-2, COCKPIT-3, COCKPIT-5, COCKPIT-6, L4-2 |

### Already-Converged Entrances (Historical Evidence)

These entrances were converged in prior phases and are documented here for completeness:

| Entrance | Phase | Successor | Evidence |
|---|---|---|---|
| cockpit MCP (stdio) | Phase 1 | agora MCP `bos://cockpit/context` | `PANORAMA.md` §四 已下线入口 |
| l4-kernel MCP (stdio) | Phase 2 | agora MCP `bos://l4-kernel/domains` | `PANORAMA.md` §四 已下线入口 |
| runtime MCP (stdio) | Phase 2 | agora MCP `bos://runtime/health` | `PANORAMA.md` §四 已下线入口 |
| agora HTTP | N/A | cockpit HTTP (never independently existed) | `PANORAMA.md` §四 |
| hermes-console | Pre-convergence | cockpit / agora | `ARCHITECTURE-EVOLUTION.md` Archived |
| agora-dashboard | Pre-convergence | cockpit-ui | `PANORAMA.md` appendix |
| llm-gateway | Pre-convergence | aetherforge/packages/gateway | `ARCHITECTURE-EVOLUTION.md` Archived |
| compute-mesh | Pre-convergence | aetherforge/packages/mesh | `PANORAMA.md` appendix |
| swarm-engine | Pre-convergence | aetherforge/packages/swarm | `PANORAMA.md` appendix |
| aetherforge-swarm-ext | Pre-convergence | aetherforge/packages/swarm | `PANORAMA.md` appendix |

### W6-02 First Batch Candidates (Bridge → Absorb)

Per blueprint §25.2, W6-02 depends on W0-04 and targets the first Bridge→Absorb cutover:

| Candidate | Current State | Target | Blocker |
|---|---|---|---|
| OMO Debt (OMO-1, OMO-2) | Dual writer: omo_debt.py + omo-debt project | Absorb scoring into omo governance; retire standalone project | W6-01 Golden Scenario canary must pass first |
| Bus Foundation (BUS-1) | 7 importers; Event plane overlaps OMO AppendOnlyLog | Bridge Event plane through OMO; keep Data + Control | Requires all 7 consumers tested under bridged path |
| Family Entry (FAMILY-1, FAMILY-3) | Standalone project + cockpit coverage overlap | Absorb entry into cockpit; standalone functions via BOS only | VISION-ROADMAP deprioritizes; low urgency |

---

## 4. Risk Assessment

| Risk | Affected Candidates | Mitigation |
|---|---|---|
| Documentation vs code drift | All Bridge/Absorb candidates | Each row cites concrete evidence path; cutover must re-verify against live code |
| Compat layer long-term residue | OMO-3, FAMILY-1, BUS-1 | W6 cutover includes explicit "old write path closed" verification; bridge has sunset date |
| bus-foundation consumer breakage | BUS-1 (7 importers) | Full test matrix required before Event plane bridge; Data + Control planes untouched |
| omo-debt scoring regression | OMO-1, OMO-2 | Absorption must pass identical scoring test suite; shadow run before cutover |
| Family-hub feature loss | FAMILY-1, FAMILY-3 | BOS route preserved; only entry surface converges; functions remain accessible |
| New top-level entry creation | All domains | ARCHITECTURE.md §3: "Do not introduce a new top-level human or agent entry without updating the relevant registry" |

---

## 5. Constraints Honored

- **No `.omo` modification**: This report reads from `.omo/` evidence files but writes only to `docs/architecture/`.
- **No commit**: No git operations performed.
- **Existing evidence only**: All decisions reference existing files in the repository.
- **AC met**: Every row has a Keep/Bridge/Absorb/Retire decision, owner, dependency, evidence path, cutover note, and rollback note.
