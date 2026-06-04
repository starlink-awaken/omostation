# SharedBrain Architecture Governance Plan

> Date: 2026-06-02 | Version: 1.0 | Status: Draft for Phase 17 Planning Gate
> Authority: Derived from MASTER-BLUEPRINT.md v1.2, system.yaml, debt registry, and decomposition architecture analysis
> References: sharedbrain-decomposition-architecture.md, organ-migration-master-plan.md, organ-salvage-final-report.md, remaining-modules-architecture-plan.md, debt-cleanup-plan.md

---

## Executive Summary

SharedBrain has been through a major decomposition: 10 of 19 organs (D_Execution, D_Memory, D_Gateway, D_Harvest, D_Governance, D_Logos, D_Intelligence, D_Continuity, D_Voice, D_Cloud) have been extracted to kairon packages and archived. However, this extraction was done at the file-copy level, leaving behind a web of structural debt: BaseMembrane pollution (475 instances across 174/324 files), Nucleus framework coupling (320 references), 22 lazy-import references to now-archived organs, and zero active bridge connections between SharedBrain and kairon.

The system health score of 29.1 (raw 97.0 times debt_weight 0.3) reflects the reality: the code has been moved, but the architecture has not been governed. This plan defines the governance framework to close that gap.

---

## 1. Target Architecture Vision

### 1.1 SharedBrain's Role in the 4-Layer System

Per MASTER-BLUEPRINT.md, SharedBrain is the "合规控制面" (Compliance Control Plane) within the omostation architecture:

```
I0 — Agora Service Mesh (MCP routing, circuit breaking, discovery)
     │
     ├── SharedBrain (合规控制面) ← THIS DOCUMENT
     │   └── Remit: EU economics, digital immunity, A1 identity,
     │       self-healing, voice processing
     │
     ├── kairon (L1-L4 knowledge engineering stack)
     │   └── Remit: knowledge processing, reasoning, research,
     │       ontology, search, code analysis
     │
     ├── agentmesh (L3 agent runtime)
     │   └── Remit: agent orchestration, MCP gateway,
     │       tool registration, task scheduling
     │
     └── gbrain (L4 knowledge storage)
         └── Remit: Postgres-native knowledge brain,
             persistent graph storage
```

**The fundamental constraint**: SharedBrain must not duplicate capabilities that kairon and agentmesh already provide. Its residual value is as the compliance and identity kernel -- the organs that enforce rules, not the organs that process knowledge.

### 1.2 End-State for Each of the 9 Remaining Organs

| Organ | Files | Lines | Decision | Target | Rationale |
|-------|------:|------:|----------|--------|-----------|
| **D_Immunity** | 88 | 22K | Keep core, extract over-engineered parts | SharedBrain core (~8K) + kairon security utils (~14K) | RBAC, behavioral fingerprinting, threat detection are compliance-plane functions. Quantum-safe crypto and federated trust are over-engineering -- extract or archive |
| **D_Genesis** | 59 | 20K | Keep core, document the rest | SharedBrain core (~6K) + archived docs (~14K) | Origin engine and evolution feedback are SharedBrain identity. Prototype management and excessive evolution machinery should be archived as reference documentation |
| **D_Monitoring** | 64 | 15K | Extract to kairon | kairon/agent-runtime or new kairon/observability package | Observability, SLO tracking, and alerting are infrastructure concerns, not compliance-plane concerns. They belong with the runtime they monitor |
| **D_Excretion** | 37 | 7.5K | Extract to kairon | kairon/gc-engine (new package) | GC engine, memory excretion, and distillation are data lifecycle operations. They operate on knowledge, not on compliance rules |
| **D_Economy** | 30 | 7K | Extract to kairon | kairon/eu-pricing (existing package) | Energy ledger, reputation, and market analysis already have a counterpart in eu-pricing. Consolidate |
| **D_KnowledgeIntegration** | 23 | 6K | Extract to kairon | kairon/kos (existing package) | Knowledge query and context injection are knowledge operations. kos already provides knowledge OS capabilities |
| **D_Extension** | 14 | 5K | Extract to kairon | kairon/forge (existing package) | Plugin marketplace and adapters are extension mechanics. forge already handles digital asset management and extensions |
| **D_Harness** | 9 | 2K | Keep, refactor | SharedBrain core (~1K) | Benchmarking, snapshots, and verification are testing infrastructure. Keep minimal harness in SharedBrain for organ self-test; migrate testing patterns to kairon pytest conventions |
| **D_Window** | 0 | 0 | Delete | N/A | Empty shell. No code, no value, no migration needed |

### 1.3 Post-Governance SharedBrain Core

After full governance execution, SharedBrain shrinks to its essential compliance-plane nucleus:

```
projects/SharedBrain/  (target: ~16K lines, ~50 files)
├── nucleus/
│   ├── Z-Spore/        (25K → keep as reference ontology, not runtime)
│   ├── Z-Core/         (1K → keep as architectural constitution)
│   └── Z-Microkernel/  (55K → reduce to stub interfaces only)
├── organs/
│   ├── D_Immunity/     (core ~8K: RBAC, threat detection, identity)
│   ├── D_Genesis/      (core ~6K: origin engine, self-healing kernel)
│   └── D_Harness/      (core ~1K: organ self-test scaffold)
├── data/db/            (persistent SQLite stores)
├── docs/               (architecture documentation)
├── tests/              (core organ tests)
└── README.md           (canonical description of SharedBrain's reduced role)
```

### 1.4 Interface Contracts Between SharedBrain and kairon

The bridge between SharedBrain (compliance plane) and kairon (knowledge plane) must be explicit, versioned, and testable:

```
Contract 1: Identity Verification (D_Immunity → kairon)
  - kairon calls: D_Immunity.verify_identity(principal, action, resource) -> bool
  - Protocol: HTTP POST to sharedbrain-bridge /verify
  - SLA: p99 < 50ms, availability 99.9%

Contract 2: Energy Accounting (D_Economy → kairon/eu-pricing)
  - After extraction: kairon/eu-pricing is the canonical energy ledger
  - SharedBrain consumes: eu-pricing.get_balance(principal) -> EUBalance
  - Protocol: Python import (same process after extraction)

Contract 3: Self-Healing Trigger (D_Genesis → agentmesh)
  - D_Genesis detects anomaly → emits event to agentmesh
  - Protocol: Agora event bus (wksp://events/genesis.anomaly)
  - SLA: event delivery < 1s

Contract 4: Organ Health Check (D_Monitoring → kairon/observability)
  - After extraction: kairon/observability polls organ health endpoints
  - Protocol: HTTP GET /health on each organ
  - SLA: check interval 30s, alert on 3 consecutive failures
```

---

## 2. Wave-by-Wave Execution

### 2.1 Wave 1: Structural Cleanup (Days 1-3)

**Objective**: Eliminate the highest-risk technical debt with zero behavioral change.

**Scope**:
- D_Window removal (0 lines, symbolic cleanup)
- Fix 22 archived organ lazy-import references
- BaseMembrane Phase 1: remove from D_Harness (2.7 instances/file, worst offender)
- Root SharedBrain shell cleanup (SB_ROOT_CLEANUP debt item)

**Tasks**:

| ID | Task | Files | Effort | Verification |
|----|------|------:|--------|-------------|
| W1.1 | Delete D_Window directory and all references | 0 | 15 min | `rg D_Window` returns 0 results in SharedBrain |
| W1.2 | Resolve 22 archived organ lazy imports: replace try/except stubs with explicit "archived, use kairon" error messages | 22 | 2 hr | Each import raises `ArchivedOrganError("D_Memory has moved to kairon/eidos")` |
| W1.3 | D_Harness BaseMembrane removal: replace BaseMembrane inheritance with plain classes | 9 | 3 hr | D_Harness files compile, tests pass |
| W1.4 | Root SharedBrain shell cleanup: remove empty `/SharedBrain/` directory, update all path references | 3-5 | 1 hr | No code references `/SharedBrain/` (only `/projects/SharedBrain/`) |
| W1.5 | Run full test suite, record baseline metrics | all | 30 min | Baseline: test count, pass rate, coverage |

**Acceptance Criteria**:
- [ ] D_Window fully removed from codebase
- [ ] All 22 archived organ references resolve to explicit error messages (not silent None)
- [ ] D_Harness BaseMembrane instances reduced from 2.7/file to 0/file
- [ ] Root `/SharedBrain/` shell cleaned
- [ ] Test suite passes with same or better pass rate

**Debt Items Addressed**: SB_ROOT_CLEANUP (partial), SB_DECOMPOSITION (progress)

---

### 2.2 Wave 2: Bridge Activation (Days 4-8)

**Objective**: Wire the sharedbrain-bridge package and establish active kairon-SharedBrain contracts.

**Scope**:
- Activate sharedbrain-bridge with real implementations
- Establish Contract 1 (Identity Verification)
- Prepare D_Economy and D_KnowledgeIntegration for extraction
- BaseMembrane Phase 1 completion across D_Immunity and D_Genesis

**Tasks**:

| ID | Task | Files | Effort | Verification |
|----|------|------:|--------|-------------|
| W2.1 | Rewrite sharedbrain-bridge from stub (140 lines dead code) to active bridge with Contract 1 | 3 | 4 hr | `curl POST /verify` returns valid JSON response |
| W2.2 | Implement D_Immunity.verify_identity endpoint in sharedbrain-bridge | 2 | 3 hr | Integration test: kairon calls bridge, bridge calls D_Immunity, response round-trip < 100ms |
| W2.3 | Prepare D_Economy extraction: inventory all internal dependencies, create extraction manifest | 30 | 3 hr | Manifest document listing every import, class, and test |
| W2.4 | Prepare D_KnowledgeIntegration extraction: same process | 23 | 2 hr | Manifest document complete |
| W2.5 | BaseMembrane Phase 1 in D_Immunity: remove from low-coupling modules (not core RBAC) | ~30 | 5 hr | BaseMembrane count in D_Immunity drops from 1.7/file to < 0.5/file |
| W2.6 | BaseMembrane Phase 1 in D_Genesis: remove from prototype management modules | ~20 | 4 hr | BaseMembrane count in D_Genesis drops below 1.0/file |
| W2.7 | Run full test suite after each organ modification | all | 1 hr | No regressions |

**Acceptance Criteria**:
- [ ] sharedbrain-bridge is no longer dead code: at least 1 active endpoint with integration test
- [ ] Contract 1 (Identity Verification) passes round-trip integration test
- [ ] D_Economy and D_KnowledgeIntegration extraction manifests complete
- [ ] BaseMembrane Phase 1 metrics met for D_Immunity and D_Genesis
- [ ] Test suite passes with zero regressions

**Debt Items Addressed**: SB_BRIDGE_FIX (resolved), SB_DECOMPOSITION (significant progress)

---

### 2.3 Wave 3: Organ Extraction (Days 9-18)

**Objective**: Extract D_Economy, D_KnowledgeIntegration, D_Monitoring, D_Excretion, D_Extension to kairon packages.

**Scope**:
- 5 organs extracted to kairon packages (either existing or new)
- Tests migrated alongside code
- Lazy-import bridges left in SharedBrain for backward compatibility

**Tasks**:

| ID | Task | Source Organ | Target Package | Lines | Effort |
|----|------|-------------|---------------|------:|--------|
| W3.1 | Extract D_Economy | D_Economy (30 files, 7K) | kairon/eu-pricing | ~5K | 2 days |
| W3.2 | Extract D_KnowledgeIntegration | D_KnowledgeIntegration (23 files, 6K) | kairon/kos | ~4K | 1.5 days |
| W3.3 | Extract D_Monitoring | D_Monitoring (64 files, 15K) | kairon/observability (NEW) | ~10K | 3 days |
| W3.4 | Extract D_Excretion | D_Excretion (37 files, 7.5K) | kairon/gc-engine (NEW) | ~5K | 2 days |
| W3.5 | Extract D_Extension | D_Extension (14 files, 5K) | kairon/forge | ~3K | 1.5 days |
| W3.6 | Per-extraction: migrate tests, verify >= 70% pass rate | -- | -- | -- | embedded |
| W3.7 | Per-extraction: leave lazy-import bridge in SharedBrain | -- | -- | -- | embedded |
| W3.8 | Full integration test after all extractions | all | all | -- | 4 hr |

**Acceptance Criteria**:
- [ ] Each extracted organ has pytest pass rate >= 70% in its new kairon package
- [ ] Each extracted organ has lazy-import backward-compatibility stub in SharedBrain
- [ ] SharedBrain test suite continues to pass (stubs provide graceful degradation)
- [ ] kairon `make test-fast` passes with new packages included
- [ ] `ruff check` clean on all new packages

**Debt Items Addressed**: SB_DECOMPOSITION (major progress -- 5 more organs governed), SB_UNTESTED_PKGS (progress -- new packages get test baselines)

---

### 2.4 Wave 4: Deep Decoupling (Days 19-28)

**Objective**: Eliminate Nucleus framework coupling and complete BaseMembrane removal from the remaining core organs.

**Scope**:
- Nucleus replacement strategy for D_Immunity, D_Genesis, D_Harness
- BaseMembrane Phase 2: complete removal from remaining files
- D_Genesis over-engineering documentation and archival

**Tasks**:

| ID | Task | Effort | Verification |
|----|------|--------|-------------|
| W4.1 | Replace Nucleus Z_Microkernel path references with standard library pathlib in D_Immunity | 3 days | Zero imports from nucleus.Z_Microkernel in D_Immunity |
| W4.2 | Replace Nucleus Z_Microkernel event bus references with Agora event bus in D_Genesis | 2 days | D_Genesis uses wksp://events protocol, not direct nucleus imports |
| W4.3 | Replace Nucleus Z_Microkernel references in D_Harness | 1 day | Zero nucleus imports in D_Harness |
| W4.4 | Complete BaseMembrane Phase 2: remove remaining instances from all remaining files | 3 days | `rg BaseMembrane` returns 0 in projects/SharedBrain/organs/ |
| W4.5 | Document D_Genesis over-engineered components (quantum-safe, federated learning, edge computing) and move to archived docs | 1 day | Archived docs in `docs/archived/` with clear "why archived" headers |
| W4.6 | Run full system test suite | 0.5 day | All tests pass |

**Acceptance Criteria**:
- [ ] Zero BaseMembrane instances in projects/SharedBrain/organs/
- [ ] Zero nucleus.Z_Microkernel imports in active organ code (stub imports in bridge layer OK)
- [ ] D_Genesis over-engineered components documented and archived
- [ ] All tests pass

**Debt Items Addressed**: SB_DECOMPOSITION (near-complete), SB_ROOT_CLEANUP (complete)

---

### 2.5 Wave 5: Architecture Convergence (Days 29-35)

**Objective**: Final integration verification, documentation, and debt ledger closure.

**Scope**:
- End-to-end integration tests across all 4 layers
- Contract verification for all 4 interface contracts
- Documentation finalization
- Debt ledger formal closure

**Tasks**:

| ID | Task | Effort | Verification |
|----|------|--------|-------------|
| W5.1 | End-to-end test: kairon → sharedbrain-bridge → D_Immunity → response | 1 day | Full round-trip < 200ms p99 |
| W5.2 | End-to-end test: D_Genesis anomaly → Agora event → agentmesh action | 1 day | Event delivery < 1s |
| W5.3 | End-to-end test: D_Monitoring (now kairon/observability) polls all organs | 1 day | Health dashboard populated with live data |
| W5.4 | Finalize SharedBrain README with reduced role description | 0.5 day | README accurately describes ~16K line compliance kernel |
| W5.5 | Update PROJECTS.yaml with accurate line counts and descriptions | 0.5 day | PROJECTS.yaml matches reality |
| W5.6 | Formal debt ledger closure: mark SB_DECOMPOSITION, SB_BRIDGE_FIX, SB_ROOT_CLEANUP as resolved | 0.5 day | Debt registry updated |
| W5.7 | Recalculate health score with updated debt_weight | 0.5 day | health_score_raw stays at 97+, debt_weight increases toward 1.0 |

**Acceptance Criteria**:
- [ ] All 4 interface contracts verified with integration tests
- [ ] SharedBrain README and PROJECTS.yaml reflect post-governance reality
- [ ] SB_DECOMPOSITION, SB_BRIDGE_FIX, SB_ROOT_CLEANUP marked resolved in debt registry
- [ ] Health score recalculated with updated debt weights
- [ ] `make test-fast` all green, `ruff check` clean

**Debt Items Addressed**: SB_DECOMPOSITION (resolved), SB_BRIDGE_FIX (resolved), SB_ROOT_CLEANUP (resolved), SB_PROJECTS_YAML (resolved), SB_PHASE17_PLAN (resolved)

---

## 3. Per-Organ Strategy Detail

### 3.1 D_Immunity (88 files, 22K lines) -- KEEP CORE, EXTRACT OVER-ENGINEERING

**Decision**: Keep as SharedBrain core organ, extract over-engineered security components.

**Keep (SharedBrain core, ~8K lines)**:
- RBAC engine and permission matrix
- Behavioral fingerprinting core
- Threat detection pipeline
- Identity verification (Contract 1 implementation)
- A1 identity management

**Extract to kairon/shared-lib or archive (~14K lines)**:
- Quantum-safe cryptography (premature -- archive)
- Federated trust network (over-engineered -- archive)
- Edge computing security (inapplicable -- archive)
- Advanced encryption schemes beyond standard TLS/AES

**Rationale**: Immunity is the definitional compliance-plane function. Without it, SharedBrain has no reason to exist as a separate system. But the quantum-safe and federated components were designed for a scale that never materialized and a threat model that does not apply to a single-user knowledge engineering workstation.

**Post-governance structure**:
```
D_Immunity/
├── rbac/           (keep: permission matrix, role engine)
├── fingerprint/    (keep: behavioral fingerprinting)
├── threat/         (keep: threat detection pipeline)
├── identity/       (keep: A1 identity, verification endpoint)
├── _archived/      (quantum, federated, edge -- reference only)
└── __init__.py     (public API: verify_identity, check_permission, detect_threat)
```

---

### 3.2 D_Genesis (59 files, 20K lines) -- KEEP CORE, ARCHIVE EVOLUTION

**Decision**: Keep origin engine and self-healing kernel; archive excessive evolution machinery.

**Keep (SharedBrain core, ~6K lines)**:
- Origin engine (organ bootstrap and initialization)
- Self-healing kernel (anomaly detection, auto-recovery triggers)
- Evolution feedback loop (core feedback collection)
- Organ lifecycle management

**Archive (~14K lines)**:
- Prototype management system (was designed for spawning new organ types -- never used)
- Multi-generational evolution tracking (academic exercise, not operational)
- Genetic algorithm components for organ optimization (over-engineered)
- Federated evolution (requires multi-node deployment that doesn't exist)

**Rationale**: Genesis defines what SharedBrain is -- its origin story and its ability to heal itself. These are identity functions. But the prototype management and genetic algorithm machinery belong in a research paper, not in a production compliance kernel.

**Post-governance structure**:
```
D_Genesis/
├── origin/         (keep: bootstrap, organ initialization)
├── self_healing/   (keep: anomaly detection, recovery triggers)
├── feedback/       (keep: evolution feedback collection)
├── lifecycle/      (keep: organ start/stop/restart)
├── _archived/      (prototypes, genetic algorithms, federated evolution)
└── __init__.py     (public API: heal, bootstrap, collect_feedback)
```

---

### 3.3 D_Monitoring (64 files, 15K lines) -- EXTRACT TO kairon

**Decision**: Extract to new kairon/observability package.

**Target package**: `kairon/packages/observability/`

**What moves**:
- SLO definitions and tracking
- Alerting engine and notification pipeline
- Metrics collection and aggregation
- Health check framework
- Dashboard data providers

**What stays (stub)**:
- Lazy-import bridge: `from kairon.observability import SloTracker` with fallback

**Rationale**: Monitoring is an infrastructure concern, not a compliance-plane concern. The compliance plane should be monitored, not be the monitor. Extracting monitoring to kairon puts it alongside the systems it observes (agent-runtime, kos, minerva, etc.).

**Dependencies to resolve**:
- Nucleus event bus → Agora event bus (wksp://events)
- BaseMembrane status tracking → standard health check protocol
- Organ-specific metrics → generic MetricsCollector interface

---

### 3.4 D_Excretion (37 files, 7.5K lines) -- EXTRACT TO kairon

**Decision**: Extract to new kairon/gc-engine package.

**Target package**: `kairon/packages/gc-engine/`

**What moves**:
- GC engine core (mark-and-sweep for knowledge entries)
- Memory excretion pipeline (identify stale/duplicate memories)
- Distillation engine (compress multiple memories into summaries)
- Retention policy enforcement

**Rationale**: Excretion is a data lifecycle operation. It operates on knowledge artifacts, which belong to the knowledge plane (kairon), not the compliance plane (SharedBrain). The biological metaphor is useful but should not dictate deployment topology.

---

### 3.5 D_Economy (30 files, 7K lines) -- EXTRACT TO EXISTING kairon/eu-pricing

**Decision**: Merge into kairon/eu-pricing.

**Target package**: `kairon/packages/eu-pricing/` (existing)

**What moves**:
- Energy ledger (EU token accounting)
- Reputation scoring engine
- Market analysis (cost tracking, usage patterns)
- Resource consumption tracking

**What's already in eu-pricing**:
- Basic pricing models
- Usage tracking stubs

**Integration**: D_Economy becomes the implementation that eu-pricing's stubs were meant for. The EU (Energy Unit) concept originates from SharedBrain; eu-pricing was created as its kairon counterpart but never populated.

---

### 3.6 D_KnowledgeIntegration (23 files, 6K lines) -- EXTRACT TO EXISTING kairon/kos

**Decision**: Merge into kairon/kos.

**Target package**: `kairon/packages/kos/` (existing)

**What moves**:
- Knowledge query interface
- Context injection pipeline
- Cross-source knowledge fusion
- Search result aggregation

**Rationale**: kos (Knowledge Operating System) already provides knowledge query and fusion capabilities. D_KnowledgeIntegration's 6K lines fill specific gaps in kos's implementation, particularly around context injection for LLM prompts.

**Note**: D_KnowledgeIntegration has 9 lazy-import references to D_Memory (archived). These must be resolved during extraction -- the knowledge sources D_Memory used to provide now come from gbrain (Postgres) via eidos.

---

### 3.7 D_Extension (14 files, 5K lines) -- EXTRACT TO EXISTING kairon/forge

**Decision**: Merge into kairon/forge.

**Target package**: `kairon/packages/forge/` (existing)

**What moves**:
- Plugin marketplace logic
- Adapter registry and discovery
- Extension lifecycle management

**Rationale**: forge handles AI digital asset management and extensions. D_Extension's plugin marketplace and adapter patterns are a natural fit.

---

### 3.8 D_Harness (9 files, 2K lines) -- KEEP, REFACTOR

**Decision**: Keep minimal testing scaffold in SharedBrain; align with kairon pytest conventions.

**Keep (SharedBrain, ~1K lines)**:
- Organ self-test scaffold (importable by each organ's tests/)
- Snapshot testing utilities (if not duplicating pytest-snapshot)
- Benchmark harness for compliance-plane latency requirements

**Refactor**:
- Replace BaseMembrane-dependent test infrastructure with standard pytest fixtures
- Align with kairon's pytest conventions (conftest.py, fixtures, markers)

**Rationale**: D_Harness has the highest BaseMembrane density (2.7 instances/file), making it both the highest-risk organ and the easiest to fix (only 9 files). It provides testing infrastructure, which should follow the project's standard testing conventions rather than inventing its own.

---

### 3.9 D_Window (0 files, 0 lines) -- DELETE

**Decision**: Remove entirely.

**Action**: Delete the directory. Remove any references from INDEX.md, AGENTS.md, and organ registries.

**Rationale**: An empty shell with no code, no tests, and no purpose. It was a placeholder for a never-implemented UI surface that is now handled by the Agora Dashboard and wksp CLI.

---

## 4. Risk Matrix and Acceptance Criteria

### 4.1 Risk Matrix

| Risk | Probability | Impact | Mitigation | Wave |
|------|:----------:|:------:|------------|:----:|
| D_Harness BaseMembrane removal breaks organ tests | Medium | High | Fix in Wave 1 (smallest organ, easiest to verify) | W1 |
| Archived organ lazy-import resolution breaks runtime imports | Medium | Medium | Each import guarded by try/except already; replace with explicit error | W1 |
| D_Immunity extraction removes security capability that something depends on | Low | High | Keep core RBAC + threat detection in SharedBrain; only extract over-engineered parts | W3 |
| D_Economy extraction breaks energy accounting during active use | Low | Medium | No active processes on any SharedBrain port; zero runtime users | W3 |
| Nucleus replacement breaks event communication between organs | Medium | High | Replace with Agora event bus (wksp:// protocol) which is already tested in production | W4 |
| New kairon packages (observability, gc-engine) lack test baselines | High | Low | Each extraction wave includes test migration; SB_UNTESTED_PKGS tracks this | W3-W4 |
| Interface contracts not honored after extraction | Medium | Medium | Integration tests in Wave 5 verify all 4 contracts | W5 |
| PROJECTS.yaml line counts diverge again after governance | High | Low | Automate line counting in CI; add to debt watchlist | W5 |

### 4.2 Acceptance Criteria Summary

**Wave 1 Acceptance**:
- [ ] D_Window fully removed (0 remaining references)
- [ ] 22 archived organ imports resolve to explicit error types
- [ ] D_Harness: BaseMembrane instances = 0
- [ ] Root `/SharedBrain/` shell cleaned, no broken paths
- [ ] Test suite: same or better pass rate

**Wave 2 Acceptance**:
- [ ] sharedbrain-bridge: >= 1 active endpoint with integration test
- [ ] Contract 1 round-trip: < 100ms p99
- [ ] D_Economy and D_KnowledgeIntegration extraction manifests complete
- [ ] D_Immunity BaseMembrane: < 0.5 instances/file (from 1.7)
- [ ] D_Genesis BaseMembrane: < 1.0 instances/file

**Wave 3 Acceptance**:
- [ ] 5 organs extracted to kairon packages
- [ ] Each extracted organ: pytest pass rate >= 70%
- [ ] Backward-compatibility stubs in SharedBrain for all 5
- [ ] kairon `make test-fast` passes
- [ ] `ruff check` clean on new packages

**Wave 4 Acceptance**:
- [ ] Zero BaseMembrane instances in projects/SharedBrain/organs/
- [ ] Zero nucleus.Z_Microkernel imports in active organ code
- [ ] D_Genesis over-engineering documented and archived
- [ ] Full test suite passes

**Wave 5 Acceptance**:
- [ ] All 4 interface contracts verified with integration tests
- [ ] SharedBrain: ~16K lines, ~50 files (from current ~85K, 324 files)
- [ ] PROJECTS.yaml reflects accurate line counts
- [ ] 3 debt items resolved: SB_DECOMPOSITION, SB_BRIDGE_FIX, SB_ROOT_CLEANUP
- [ ] Health score calculation updated

### 4.3 Pre/Post Metrics

| Metric | Pre-Governance (Current) | Post-Wave 1 | Post-Wave 3 | Post-Wave 5 (Target) |
|--------|:------------------------:|:-----------:|:-----------:|:--------------------:|
| SharedBrain organ count | 9 active + 10 archived | 8 active + 11 archived | 3 active + 16 archived/extracted | 3 active + 16 governed |
| SharedBrain lines (organs) | ~85K | ~83K | ~48K | ~16K |
| SharedBrain files | 324 | ~315 | ~180 | ~50 |
| BaseMembrane instances | 475 | ~420 | ~200 | 0 |
| Nucleus Z_Microkernel refs | 320 | ~300 | ~150 | 0 (in active code) |
| Archived organ lazy refs | 22 | 0 (all resolved) | 0 | 0 |
| Active bridge connections | 0 | 1 | 2 | 4 |
| Health score (raw) | 97.0 | 97.0 | 97.0 | 97.0 |
| Debt weight | 0.3 | 0.45 | 0.65 | 1.0 |
| Health score (weighted) | 29.1 | 43.7 | 63.1 | 97.0 |
| Test pass rate | baseline | >= baseline | >= baseline | >= baseline |

---

## 5. Debt Ledger Update

### 5.1 Debt Items This Plan Resolves

| Debt ID | Title | Current State | Resolution Wave | Resolution Action |
|---------|-------|:------------:|:---------------:|--------------------|
| **SB_DECOMPOSITION** | SharedBrain decomposition partially governed | in_progress | W5 | Mark resolved: all 19 organs have governed destinations (3 keep, 11 extracted, 5 archived/merged) |
| **SB_BRIDGE_FIX** | sharedbrain-bridge disconnected | classified | W2 | Mark resolved: bridge has active endpoints with integration tests |
| **SB_ROOT_CLEANUP** | Root SharedBrain shell cleanup deferred | classified | W1 | Mark resolved: root shell cleaned, all paths point to /projects/SharedBrain/ |
| **SB_PROJECTS_YAML** | PROJECTS registry metadata stale | classified | W5 | Mark resolved: PROJECTS.yaml updated with accurate post-governance line counts |
| **SB_PHASE17_PLAN** | Phase 17 planning needs debt-ledger tracking | mitigated | W5 | Mark resolved: this plan serves as the canonical execution plan with debt-ledger integration |

### 5.2 Debt Items This Plan Improves But Does Not Fully Resolve

| Debt ID | Title | Improvement | Remaining Work |
|---------|-------|-------------|----------------|
| **SB_UNTESTED_PKGS** | kairon packages lack test baselines | Each extracted organ gets pytest >= 70% pass rate | Need CI integration and coverage thresholds for all kairon packages |
| **SB_ORPHANED_TASKS** | Orphaned task semantics drift from debt ledger | This plan creates a governed task structure | Need automated task-to-debt reconciliation in CI |

### 5.3 Debt Items Not Addressed By This Plan

| Debt ID | Title | Why Not Addressed |
|---------|-------|-------------------|
| **D2_CI_E2E** | CI E2E test environment non-canonical | Separate infrastructure concern; addressed by D2-CI-E2E-TEST-ENV task |
| **D3_EU_PRICING** | eu-pricing tests not independently governed | Addressed by D3-EU-PRICING-TEST task; Wave 3 extraction will improve but not fully resolve |

### 5.4 Proposed Debt Weight Trajectory

```
Current:  debt_weight = 0.30  (9 items, 0 resolved)
Post-W1:  debt_weight = 0.40  (SB_ROOT_CLEANUP resolved)
Post-W2:  debt_weight = 0.50  (SB_BRIDGE_FIX resolved)
Post-W3:  debt_weight = 0.60  (SB_UNTESTED_PKGS partial)
Post-W4:  debt_weight = 0.70  (SB_DECOMPOSITION near-complete)
Post-W5:  debt_weight = 0.85  (SB_DECOMPOSITION, SB_PROJECTS_YAML, SB_PHASE17_PLAN resolved)
          + D2_CI_E2E and D3_EU_PRICING remain (0.15 weight)
```

The final 0.15 debt weight corresponds to D2_CI_E2E and D3_EU_PRICING, which are infrastructure and testing concerns outside this plan's scope but tracked in the active task queue.

---

## 6. Governance Integration

### 6.1 Relationship to .omo Governance

This plan operates within the .omo governance framework defined in `.omo/AGENT.md`. Key governance touchpoints:

- **Task SSOT**: All Wave tasks are registered in `.omo/tasks/active/` as YAML files, not duplicated here
- **Debt Ledger**: Debt item state transitions happen in `.omo/debt/items/*.yaml`, with this plan providing the execution roadmap
- **System State**: `system.yaml` health_score and debt_weight are updated after each Wave's verification gate
- **Knowledge Surface**: This plan lives in `.omo/_knowledge/design/` as the canonical architecture governance reference

### 6.2 Phase 17 Integration

This plan is the execution arm of the Phase 17 SharedBrain governance gate. It answers the question posed by the SHAREDBRAIN-FORMAL-DECISION task: "What happens to SharedBrain?" The answer: SharedBrain becomes a ~16K-line compliance kernel with 3 core organs (D_Immunity, D_Genesis, D_Harness), with 5 more organs extracted to kairon and 1 empty organ deleted.

### 6.3 Decision Log

| Decision ID | Description | Rationale | Date |
|-------------|-------------|-----------|------|
| D-001 | D_Window deletion | Empty shell, no code, no purpose | 2026-06-02 |
| D-002 | D_Immunity stays as core | Definitional compliance function; without it, SharedBrain has no identity | 2026-06-02 |
| D-003 | D_Genesis stays as core | Origin and self-healing are identity functions | 2026-06-02 |
| D-004 | D_Harness stays (refactored) | Testing scaffold for remaining core organs | 2026-06-02 |
| D-005 | D_Monitoring extracted to kairon/observability | Infrastructure concern, not compliance-plane | 2026-06-02 |
| D-006 | D_Economy merged into kairon/eu-pricing | eu-pricing was created for this purpose | 2026-06-02 |
| D-007 | D_KnowledgeIntegration merged into kairon/kos | kos already provides knowledge OS capabilities | 2026-06-02 |
| D-008 | D_Excretion extracted to kairon/gc-engine | Data lifecycle belongs in knowledge plane | 2026-06-02 |
| D-009 | D_Extension merged into kairon/forge | forge already handles extensions and assets | 2026-06-02 |
| D-010 | Nucleus replaced with Agora event bus + stdlib pathlib | Eliminates 320-reference framework coupling | 2026-06-02 |

---

## Appendix A: File Inventory

### Source Documents (Read-Only References)

| Document | Path | Role |
|----------|------|------|
| Master Blueprint | `.omo/MASTER-BLUEPRINT.md` | System architecture authority |
| System State | `.omo/state/system.yaml` | Current health, debt weights, active tasks |
| Decomposition Architecture | `.omo/_knowledge/design/sharedbrain-decomposition-architecture.md` | Prior analysis of SharedBrain-kairon split |
| Organ Migration Plan | `.omo/_knowledge/design/organ-migration-master-plan.md` | 410-module extraction task pool |
| Organ Salvage Report | `.omo/_knowledge/design/organ-salvage-final-report.md` | 10-organ deep scan results |
| Remaining Modules Plan | `.omo/_knowledge/design/remaining-modules-architecture-plan.md` | 62-module precise repair strategy |
| Debt Cleanup Plan | `.omo/_knowledge/design/debt-cleanup-plan.md` | Historical debt analysis and resolution design |
| Debt Registry | `.omo/debt/registry.yaml` | Canonical debt item index |

### Output Documents (This Plan Generates)

| Document | Path | When |
|----------|------|------|
| This Governance Plan | `.omo/_knowledge/design/sharedbrain-architecture-governance-plan.md` | Now |
| Wave 1 Execution Log | `.omo/_delivery/wave1-execution-log.md` | After W1 |
| Wave 2 Bridge Test Report | `.omo/_delivery/wave2-bridge-test-report.md` | After W2 |
| Extraction Manifests (per organ) | `.omo/_knowledge/design/extraction-manifests/{organ}.md` | During W2-W3 |
| Final Convergence Report | `.omo/_delivery/architecture-convergence-report.md` | After W5 |

---

## Appendix B: Constitutional Principles Check

This plan complies with the 10 immutable architectural laws defined in MASTER-BLUEPRINT.md:

1. **I0 Isolation**: Yes -- SharedBrain communicates through Agora (I0), never directly to kairon internals
2. **MCP Mandate**: Yes -- all cross-system communication uses MCP or wksp:// protocol
3. **Python to kairon**: Yes -- extracted organs go to kairon Python packages
4. **TypeScript to agentmesh/gbrain**: Yes -- no violation; SharedBrain remains Python
5. **SharedBrain does not do knowledge processing**: Yes -- post-governance SharedBrain is compliance-only; knowledge operations are in kairon
6. **kairon does not do runtime control**: Yes -- agentmesh handles runtime; SharedBrain handles compliance
7. **core-models is sole authority**: Yes -- Z-Spore retained as reference ontology, not as competing authority
8. **Organs delegate, not delete**: Yes -- all organ capabilities are preserved (extracted or archived), never destroyed
9. **Absorb, not replicate**: Yes -- D_Economy merges into eu-pricing, not duplicated
10. **Per-phase security scan**: Yes -- each Wave includes test verification gate

---

*Maintained by: Architect Agent (Serena Blackwood) for SharedBrain Governance*
*Next review: After Wave 1 completion (target Day 3)*
*Canonical location: `.omo/_knowledge/design/sharedbrain-architecture-governance-plan.md`*
