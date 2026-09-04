---
type: ephemeral
created: 2026-09-03
---

# W0 Fact Baseline Report — 2026-08-10

> **Type**: Evidence-backed baseline inventory · Read-only probe results
> **Executor**: W0-01 (Orca worktree `w0-baseline-20260810`)
> **Scope**: omostation (eCOS v6) repository — root tree + `.omo/` read surfaces
> **Probe timestamp**: 2026-08-10T02:48:12Z (UTC)
> **Constraints**: No production mutation, no `.omo` writes, no commit/push, no submodule init
> **Convention**: ✅ = verified fact · ❌ = verified failure · ⚠️ = hypothesis/needs-confirmation

---

## 1. System State (from `.omo/state/system.yaml`)

| Field | Value | Source |
|-------|-------|--------|
| current_phase | 49 | `system.yaml::current_phase` |
| phase_status | active | `system.yaml::phase49_status` |
| current_wave | W5 | `system.yaml::current_wave` |
| health_score | 70/100 | `system.yaml::health_score` (ref: `compass_radar_composite_isc3`) |
| health_generated_at | 2026-08-08T12:39:31Z | `system.yaml::health_score_generated_at` |
| total_tasks | 298 | `system.yaml::total_tasks` |
| completed_tasks | 229 | `system.yaml::completed_tasks` |
| active_tasks | 1 | `system.yaml::active_tasks` |
| active_agents | 0 | `system.yaml::active_agents` |
| idle_agents | 4 | `system.yaml::idle_agents` |
| dead_agents | 0 | `system.yaml::dead_agents` |
| ecosystem_maturity_score | 100 | `system.yaml::ecosystem_maturity_score` |
| divergence_flags | `[]` (empty) | `system.yaml::divergence_flags` |

> ⚠️ **Divergence detected**: `current-state-coherence` check reports `planned_tasks_mismatch:expected=69:state=64` and `total_tasks_mismatch:expected=295:state=290` — but `system.yaml::divergence_flags` is empty. See §6.

---

## 2. Validation Gates — Executed Results

All probes ran on 2026-08-10 at approximately 02:48Z UTC in the Orca worktree. 17 submodules were not initialized (expected for a fresh worktree).

### 2.1 Gate Results Matrix

| Gate | Command | Result | Exit Code | Evidence |
|------|---------|--------|-----------|----------|
| journey-check | `make journey-check` | ✅ ALL PASS | 0 | 10 specs validated |
| scene-chain-validator | `python3 bin/ssot/scene-chain-validator.py` | ✅ VALID | 0 | 9 scenes, 11 edges, 2 feedback loops |
| adr-number-check | `make adr-number-check` | ✅ OK | 0 | 358 ADRs, latest=0406, next=0407 |
| scene-card-check | `make scene-card-check` | ❌ ALL 9 "(check failed)" | 0 | Makefile JSON parsing issue (see §2.2) |
| doc-ssot-lint | `make doc-ssot-lint` | ❌ 1 conflict | 1 | L0 constraint source missing |
| agent-workflow-bootstrap | `make agent-workflow-bootstrap` | ❌ ModuleNotFoundError | 1 | `No module named 'omo'` |
| ssot-guardian | `python3 bin/ssot/ssot-guardian.py` | ❌ 2 drifts | 0 | critical + medium |
| ci-surfaces-check | (from metrics-store) | ❌ unregistered check | — | `debt-audit.yml` executes unregistered check |
| current-state-coherence | (from metrics-store) | ❌ divergence | — | task count mismatch |
| doc-governance | (from metrics-store) | ✅ PASS | — | 1567 files, 79 warnings |
| swarm-collision | (from metrics-store) | ✅ PASS | — | 1 agent detected, no deadlock |

### 2.2 Scene Card Readiness (manual lifecycle probe)

The Makefile `scene-card-check` target reports "(check failed)" for all 9 cards due to a JSON output parsing mismatch (the `python3 -c` one-liner expects fields that may not be present). Manual invocation of `scene-card-lifecycle.py check` reveals the true status:

| Scene Card | Schema | Ready | Type | Lifecycle | Blockers | Approval State |
|------------|--------|-------|------|-----------|----------|----------------|
| agora-bos-gateway | v1 | false | external_resource | routine | 4 | approved |
| document-review | v1 | false | external_resource | shadow | 0 | confirmed |
| engineering-delivery-dogfood | **v2** | **ERROR** | internal_pipeline | active | — | — |
| knowledge-curation | v1 | false | external_resource | shadow | 0 | pending_business_confirmation |
| meeting-supervision | **v2** | **ERROR** | — | — | — | — |
| periodic-reporting | **v2** | **ERROR** | — | — | — | — |
| project-supervision | **v2** | **ERROR** | — | — | — | — |
| research-pipeline | v1 | false | external_resource | shadow | 0 | pending_business_confirmation |
| unified-inbox | v1 | false | external_resource | shadow | 0 | pending_business_confirmation |

**Root cause of ERROR rows**: `internal-scene-preflight.py:216` raises `PreflightInputError: scene card must use scene-card/v1` — it hardcodes v1 schema requirement but 4 cards declare `schema: scene-card/v2`. This is a **schema version gap** between the preflight validator and scene-card authors.

**Command (for reproduction)**:
```bash
python3 bin/ssot/scene-card-lifecycle.py check --scene-card docs/scene-cards/<card>.yaml
```

### 2.3 Journey Specs (10 total, all pass)

| Journey | States | Transitions |
|---------|--------|-------------|
| inbox-to-decision | 9 | 9 |
| intake-review-deliver-inbox | 0 | 0 |
| intake-review-deliver-meeting | 0 | 0 |
| intake-review-deliver-oversight | 0 | 0 |
| intent-to-execution | 6 | 5 |
| meeting-to-delivery | 10 | 9 |
| oversight-to-decision | 7 | 7 |
| parallel-approval-test | 6 | 4 |
| research-to-insight | 7 | 6 |
| schedule-to-evidence | 8 | 7 |

**Scene Chain**: ✅ VALID — 9 scenes, 11 edges, 2 architecturally-valid feedback loops:
- `knowledge-curation → research-pipeline → knowledge-curation`
- `meeting-supervision → periodic-reporting → project-supervision → meeting-supervision`

---

## 3. Signal & Health Sources Inventory

### 3.1 Registered Signal Sources (`.omo/_truth/registry/signal-sources.yaml`)

| Source ID | Transport | Health | last_signal_at | bos_uri | Registered |
|-----------|-----------|--------|----------------|---------|------------|
| apple_mail_inbox | local_filesystem | **healthy** | 2026-08-07T23:45:22Z | bos://perception/apple_mail/inbox | 2026-08-07 |
| netease_mailmaster_inbox | local_filesystem | **unknown** | null | bos://perception/netease/inbox | 2026-08-07 |
| github_push | webhook | **unknown** | null | bos://perception/github/push | 2026-08-07 |
| inbox_folder | local_filesystem | **unknown** | null | bos://perception/folder/inbox | 2026-08-09 |

**❌ FALSE-GREEN ALERT**: `signal-sources.yaml` defines `schema_contract.health_must_not` rules:
```yaml
- value: healthy
  when: "last_signal_at is null or older than 2x poll_interval"
```
3 of 4 sources have `health: unknown` with `last_signal_at: null`, but **no enforcement mechanism** was found that validates this contract at runtime. The `signal-poller.py` exists but does not support `--dry-run` and was not run (no mutation allowed).

### 3.2 Health Score Composition (`.omo/state/health.yaml`)

| Component | Weight | Contribution | Raw Value |
|-----------|--------|--------------|-----------|
| governance | 30% | **0.0** | anomaly_count=9, execution_score=0 (deduction=133) |
| freshness | 20% | **20.0** | freshness_score=100 |
| runtime | 50% | **50.0** | service_online_ratio=1.000 |
| **Total** | 100% | **70.0** | — |

**❌ Critical anomaly**: `governance_execution_surface.score = 0` with `execution_deduction = 133`. Drivers:
- `concurrent_conflicts: 16` (weight: 8 each = 128)
- `adr_renumber_events: 1` (weight: 5 each = 5)
- `orphan_worktrees: 0`

**⚠️ Health anomalies (9)**:
- P0 tasks 45 (threshold 5) — strategic priority imbalance
- L3 high-risk tasks 10 — needs review
- Owner concentration: agent holds 68% of pending tasks (single-point-of-failure)

### 3.3 Event/Ledger Physical Files

| File | Exists | Size | Lines | Last Entry |
|------|--------|------|-------|------------|
| `.omo/_delivery/observability/events.jsonl` | ❌ **MISSING** | — | — | — |
| `.omo/_knowledge/workflow-mesh/scene-outcomes.jsonl` | ❌ **MISSING** | — | — | — |
| `.omo/state/metrics-store.jsonl` | ✅ | 32KB | 138 | 2026-08-08T05:03:21Z |
| `.omo/state/swarm/broadcast-bus.jsonl` | ✅ | 617B | 2 | — |

**❌ The unified event surface (`events.jsonl`) is registered in `observability-events.yaml` with 8 adapters (6 enabled), but the physical file has never been created.** All event routing targets a non-existent sink.

### 3.4 Freshness Assessment

All key runtime artifacts are **~2 days stale** relative to the probe time (2026-08-10T02:48:12Z):

| Artifact | Generated At | Staleness |
|----------|-------------|-----------|
| `health.yaml` | 2026-08-08T12:38:56Z | ~38h |
| `BRIEF.md` | 2026-08-08T12:35:00Z | ~38h |
| `system.yaml::updated_at` | 2026-08-08T12:39:32Z | ~38h |
| `metrics-store.jsonl` (last line) | 2026-08-08T05:03:21Z | ~45h |
| `health.yaml::feedback_last_ts` | 2026-08-08T12:25:48Z | ~38h |

**Note**: This is expected if no agent/governance activity has run since 2026-08-08. Not necessarily a false-green — the freshness_score=100 was computed at generation time.

---

## 4. Existing Surfaces Inventory

### 4.1 Governance Surfaces (`.omo/_truth/registry/`)

| Registry | File | Status | Key Stats |
|----------|------|--------|-----------|
| Governance Checks | `governance-checks.yaml` | active | 4 checkers (X1-X4), all enabled |
| Debt | `debt.yaml` | active | 8 seed items + 26 gap items (META/FACE/EVO/OBS/GOV/SCENE/DATA/THEORY/AGENT/MECH) |
| Agent Workflows | `agent-workflows/workflows/` | active | 15 workflow definitions |
| Redlines | `redlines.yaml` | active | 8 enforced red lines + 2 acknowledged gaps |
| MOF Capabilities | `mof-capabilities.yaml` | active | v2.2, 4 layers all "complete" |
| OMO Governance Surfaces | `omo-governance-surfaces.yaml` | active | 621+ lines, references X1-X4 policies |
| Observability Events | `observability-events.yaml` | active | 8 adapters (6 enabled), unified event schema |
| Memory OS | `memory-os.yaml` | phase10 | Neo4j-gated, MOS_LIVE flags, RBAC policy |
| External Connection Fabric | `external-connection-fabric.yaml` | active | v1.0, unified lifecycle contract |
| Runtime Projections | `runtime-projections.yaml` | active | OMO state-sync broker projections |
| CI Surfaces | `ci-surfaces.yaml` | — | 108 surfaces, 87 wired, 25 orphan registered |
| Port Registry | `protocols/port-registry.yaml` | active | Multi-project port assignments (conflicts resolved) |

### 4.2 Agent Workflow Registry (15 workflows)

```
agent-onboarding · bet-execution · c2g-spec-ingress · external-adapter-sync ·
governance-audit · governance-state-mutation · handoff-resume · mof-model-change ·
mof-state-bridge-audit · observer-audit · project-code-change · project-doc-change ·
pyright-sweep · state-sync · submodule-pointer-close
```

**❌ BLOCKER**: `make agent-workflow-bootstrap` fails with `ModuleNotFoundError: No module named 'omo'`. The workflow engine imports `omo.workflow` which lives in `projects/omo/` submodule — **not initialized** in this worktree. This blocks all workflow lifecycle commands.

### 4.3 Scene Execution Engine (`bin/ssot/`)

| Tool | Size | Purpose | Status |
|------|------|---------|--------|
| `journey-runner.py` | 32.2KB | Journey state machine executor | ✅ exists |
| `journey-validator.py` | 6.3KB | Journey spec validation | ✅ works |
| `journey-state-store.py` | 4.1KB | Journey checkpoint persistence | ✅ exists |
| `signal-poller.py` | 7.5KB | Perception signal detection | ✅ exists (no --dry-run) |
| `scene-card-lifecycle.py` | 11.1KB | Scene card readiness check | ⚠️ v2 schema gap |
| `scene-chain-validator.py` | 5.2KB | Scene graph validation | ✅ works |
| `scene-outcome-recorder.py` | 5.7KB | Scene outcome recording | ✅ exists |
| `scene-reflection.py` | 6.4KB | Scene reflection | ✅ exists |
| `internal-scene-preflight.py` | 11.7KB | Internal pipeline preflight | ⚠️ hardcoded v1 schema |
| `external-activation-preflight.py` | 11.6KB | External resource preflight | ✅ exists |
| `ssot-guardian.py` | 19.5KB | SSOT drift detection | ✅ works |
| `doc-ssot-lint.py` | 16.5KB | Doc SSOT contract lint | ❌ L0 source missing |
| `observability-events.py` | 14.7KB | Event surface utilities | ✅ exists |
| `alert-connectors.py` | 10.4KB | Alert notification connectors | ✅ exists (partial) |
| `capability-token.py` | 4.9KB | Scene capability token | ✅ exists |

**❌ 5 empty (0-byte) scripts** — stubs never implemented:
- `bin/ssot/mail_agent.py`
- `bin/ssot/mail_daemon.py`
- `bin/ssot/mail_reader.py`
- `bin/ssot/mail_sender.py`
- `bin/ssot/doc_generator.py`

### 4.4 SSOT Guardian Findings

```
❌ 检测到 2 项未修复 SSOT 漂移:
   - direct_omo_io_violation (critical)
   - workspace_hygiene (medium) — 0字节=5 大小写冲突=0
```

### 4.5 Doc-SSOT Lint Finding

```json
{
  "ok": false,
  "conflicts": 1,
  "files_scanned": 74,
  "finding": {
    "label": "L0/MOF 映射",
    "reason": "L0 约束源缺失: projects/ecos/.omo/_derived/l0-constraints.v2.yaml
               / projects/ecos/src/ecos/ssot/registry/L0-constraints.yaml"
  }
}
```

**Root cause**: `projects/ecos` submodule not initialized → L0 constraint files not on disk. This is a **worktree-environment artifact**, not a real project defect. In a full checkout the files exist.

---

## 5. Project Registry Summary (`docs/project-registry.yaml`)

| Metric | Value |
|--------|-------|
| Architecture | 5+4+1+1 |
| eCOS version | v6 |
| Total submodules | 17 |
| Total projects | 17 |

**Key projects by layer**:

| Layer | Projects |
|-------|----------|
| L0 | mesh-router (implemented-in-bin), ecos |
| L1 | runtime |
| L2 | kairon (16 packages, KOS: 25 MCP tools), gbrain, omo, metaos |
| L3 | cockpit, cockpit-ui |
| I0 | agora (200 BOS services: 188 active / 11 unimplemented / 1 deprecated) |
| M0 | model-driven |
| X | aetherforge, c2g, bus-foundation, omo-debt, observability, family-hub |

---

## 6. Known False-Green Paths

| # | Path | Symptom | Impact | Evidence |
|---|------|---------|--------|----------|
| 1 | Signal source health contract | 3/4 sources `health: unknown`, `last_signal_at: null` — no enforcement of `health_must_not` rules | Dead signals silently ignored | `signal-sources.yaml::schema_contract.health_must_not` |
| 2 | Makefile `scene-card-check` target | All 9 cards report "(check failed)" regardless of actual status | False failure signal masks real issues | JSON parsing mismatch in Makefile one-liner |
| 3 | Scene card v2 schema gap | 4 cards use `scene-card/v2` but preflight hardcodes v1 | 4 cards cannot be checked at all | `internal-scene-preflight.py:216` |
| 4 | Unified event sink | `events.jsonl` registered but never created | All event routing to void | `observability-events.yaml` vs missing file |
| 5 | BRIEF.md X3 "工作交付" | "未接入真实数据源" explicitly noted | Value metric shows as row but has no data | `BRIEF.md` |
| 6 | `divergence_flags` empty | `system.yaml::divergence_flags = []` but coherence check found task count mismatch | Stale divergence not surfaced | `current-state-coherence` in metrics-store |
| 7 | Governance execution score=0 | `health.yaml::governance_execution_surface.score = 0` (deduction=133) | Main driver of health=70 (not 100) | `health.yaml` |
| 8 | P74 warn count file missing | `.p74_solidification.warn_count` does not exist | P74 solidification check cannot report | `ls .p74_solidification.warn_count` → ENOENT |

---

## 7. Keep / Bridge / Absorb / Retire Candidate List

### 🟢 KEEP (verified working, high value)

| Item | Evidence | Rationale |
|------|----------|-----------|
| `journey-validator.py` + 10 journey specs | ✅ All pass | Core state-machine validation, zero failures |
| `scene-chain-validator.py` | ✅ VALID (9 scenes, 11 edges, 2 feedback loops) | Scene graph topology validation works correctly |
| `adr-number-check.py` | ✅ 358 ADRs, no conflicts | ADR numbering integrity maintained |
| `ssot-guardian.py` | ✅ Detects 2 real drifts | Catches genuine SSOT violations |
| `signal-sources.yaml` schema contract | ✅ Well-defined health_must_not rules | Good contract design, needs enforcement wiring |
| `redlines.yaml` | ✅ 8 enforced + 2 acknowledged gaps | Every redline has an executor or explicit gap_reason |
| MOF capabilities v2.2 | ✅ 4 layers complete | Model-driven framework operational |
| `doc-governance-check` | ✅ PASS (1567 files, 79 warnings) | Document governance enforcement working |
| `observability-events.yaml` adapter registry | ✅ 8 adapters, well-schema'd | Unified event surface design is sound |
| `governance-checks.yaml` (X1-X4) | ✅ 4 checkers, all enabled | Multi-axis governance framework active |

### 🟡 BRIDGE (exists but needs wiring/fixing)

| Item | Gap | Fix Direction |
|------|-----|---------------|
| Makefile `scene-card-check` target | JSON parsing mismatch → all "(check failed)" | Fix Makefile one-liner to handle actual JSON schema |
| Scene card v2 schema support | `internal-scene-preflight.py` hardcodes `scene-card/v1` | Support v2 in preflight or migrate v2 cards to v1 |
| `events.jsonl` unified event sink | Designed but file never created | Initialize file + wire adapter write paths |
| Signal health enforcement | `health_must_not` contract not enforced | Add runtime validator in `signal-poller.py` |
| `agent-workflow-bootstrap` | `ModuleNotFoundError: omo` in worktree | Document submodule init requirement or vendor omo module |
| `doc-ssot-lint` L0 source | Missing in worktree (submodule not init) | Document or provide fallback path |
| `.p74_solidification.warn_count` | File not created | Wire P74 check to write the count file |
| `signal-poller.py` | No `--dry-run` support | Add safe read-only mode for baseline probes |
| Scene card readiness pipeline | 0/9 cards ready (all shadow/preview) | Move cards through approval → preflight → trial → activation |
| Memory OS phase10 | NEO4J_URI-gated, fixture-safe defaults | Production wiring requires Neo4j instance |

### 🟠 ABSORB (consolidation candidates)

| Item | Current State | Consolidation Target |
|------|---------------|----------------------|
| `metrics-store.jsonl` + `broadcast-bus.jsonl` | 2 separate event streams | → unified `events.jsonl` (already designed) |
| 9 `scene-card-*.py` scripts | scene-card-lifecycle, approval-flow, candidates, connector, decision-inbox, intake-pipeline, intake, review, task-bridge | Consider absorbing into lifecycle + connector + bridge (3 tools) |
| `health.yaml` + `system.yaml` health fields | Duplicated health references | Single `health.yaml` as canonical, `system.yaml` references it |
| Debt items + gap items | 2 separate registries (`debt.yaml` seed + `gap-registry.yaml`) | Unify under single debt registry with `type` field |

### 🔴 RETIRE (dead/broken/stub)

| Item | Evidence | Action |
|------|----------|--------|
| `bin/ssot/mail_agent.py` (0 bytes) | Empty stub, never implemented | Delete or implement |
| `bin/ssot/mail_daemon.py` (0 bytes) | Empty stub | Delete or implement |
| `bin/ssot/mail_reader.py` (0 bytes) | Empty stub | Delete or implement |
| `bin/ssot/mail_sender.py` (0 bytes) | Empty stub | Delete or implement |
| `bin/ssot/doc_generator.py` (0 bytes) | Empty stub | Delete or implement |
| 3 empty journey specs | `intake-review-deliver-*` (0 states, 0 transitions) | Implement or remove stubs |

---

## 8. Verified Facts vs Hypotheses

### ✅ Verified Facts (evidence-backed)

1. Phase 49 is active; health score is 70/100
2. 10 journey specs all validate successfully
3. Scene chain topology is valid with 2 feedback loops
4. 358 ADRs exist with no numbering conflicts
5. 4/9 scene cards check OK (v1 schema), 0 ready
6. 4/9 scene cards crash on v2 schema (preflight hardcoded v1)
7. `events.jsonl` does not exist on disk
8. `scene-outcomes.jsonl` does not exist on disk
9. 5 SSOT Python scripts are 0-byte stubs
10. `agent-workflow-bootstrap` fails without omo submodule
11. All 17 submodules uninitialized in this worktree
12. 3 of 4 signal sources have `health: unknown` with `last_signal_at: null`
13. `metrics-store.jsonl` last entry is 2026-08-08T05:03:21Z
14. Governance execution surface score = 0 (deduction = 133)
15. `ci-surfaces-check` found unregistered check (`debt-audit.yml`)

### ⚠️ Hypotheses (need confirmation)

1. **BOS services = 200 (188 active)** — from `project-registry.yaml` but `projects/agora/etc/bos-services.yaml` not accessible (submodule not initialized)
2. **"direct_omo_io_violation" details** — ssot-guardian reports "critical" but detailed description was empty in output
3. **Feedback loop in health.yaml** — `feedback_alive: True` with `feedback_staleness_hours: 0.2` but last_ts is 38h old — possibly generated at a different time
4. **P0 task count (45)** — from health.yaml anomaly list, but `health.yaml::total_tasks` says 68 while `system.yaml::total_tasks` says 298 — scope difference unclear

---

## 9. Probe Command Reference (exact commands used)

```bash
# Validation gates (read-only)
make journey-check                              # exit 0
make scene-card-check                           # exit 0 (but all "(check failed)")
make adr-number-check                           # exit 0
make doc-ssot-lint                              # exit 1
make agent-workflow-bootstrap                   # exit 1

# Direct tool probes
python3 bin/ssot/scene-card-lifecycle.py check --scene-card docs/scene-cards/<card>.yaml
python3 bin/ssot/scene-chain-validator.py       # exit 0
python3 bin/ssot/ssot-guardian.py               # exit 0 (2 drifts)

# File existence probes
ls -la .omo/_delivery/observability/events.jsonl          # ENOENT
ls -la .omo/_knowledge/workflow-mesh/scene-outcomes.jsonl  # ENOENT
wc -l .omo/state/metrics-store.jsonl                      # 138 lines
wc -l .omo/state/swarm/broadcast-bus.jsonl                # 2 lines
find bin/ssot/ -name "*.py" -size 0 -type f               # 5 files

# State probes (read-only)
cat .omo/state/system.yaml | head -100
cat .omo/state/health.yaml
cat .omo/_truth/registry/signal-sources.yaml
git submodule status                            # 17 uninit
git status --short                              # clean working tree
```

---

## 10. Metadata

| Field | Value |
|-------|-------|
| Report path | `docs/reports/w0-fact-baseline-2026-08-10.md` |
| Probe date | 2026-08-10 |
| Worktree | `w0-baseline-20260810` (Orca managed) |
| Files modified | `docs/reports/w0-fact-baseline-2026-08-10.md` (new only) |
| `.omo` writes | None |
| Commits | None |
| Submodule init | None |
| Production mutation | None |
