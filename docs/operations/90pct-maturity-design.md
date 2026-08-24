# 90% Architecture Maturity Design — eCOS v6 / omostation

> Version: v1.0-draft
> Date: 2026-08-24
> Status: design
> Owner: governance-team
> Baseline: ARCHITECTURAL-REVIEW-2026-08-24.md, STRATEGIC-ANALYSIS-2026-08-24.md
> Target: 90% architecture maturity across 6 dimensions

---

## 0. Design Principles

Every design decision MUST satisfy ALL six principles:

| Principle | Definition | Acceptance Test |
|---|---|---|
| **Evolvable** | New capabilities can be added without breaking existing contracts; versioned interfaces; backward-compatible migrations | Add a new check type → existing gates still pass |
| **Iterable** | Can be delivered in 3-5 phases, each independently valuable and verifiable | Phase 1 delivers drift sweep; Phase 2 adds runbook validity; each is useful alone |
| **Observable** | Every component emits structured signals consumable by `compass_radar.py` and `gac-local-gate` | Component health visible in `make omo-status` within 1 refresh cycle |
| **Traceable** | Every action has causal chain: `principal_id → workflow_run_id → packet_id → assignment_id → EvidenceRecorded → VerificationReceipt` | Can answer "who changed what, when, why, and what was the outcome?" |
| **Troubleshootable** | Failures produce structured diagnostics with owner, expected behavior, and remediation command | A failed check outputs: owner, expected, actual, remediation, related runbooks |
| **Optimizable** | All data is queryable for trend analysis; improvement hypotheses can be tested and measured | Health trend shows improvement after each phase; drift count trend is queryable |

Non-negotiable constraints:
1. Single worktree = main
2. Single-owner model
3. Submodules = independent repos
4. macOS-first
5. Python 3.13

Non-negotiable anti-patterns:
1. No new top-level entry surfaces without registry update
2. No second state plane
3. No blocking drift detector in concurrent-agent scenarios
4. No auto-fix scripts without audit log
5. No global rewrites

---

## 1. Strategic Framework

### 1.1 Vision Alignment

Serves the north star: **weekly successful completed and actually-consumed closed-loop journeys**.

### 1.2 Maturity Model

| Level | Name | Description | Current | Target |
|---|---|---|---|---|
| 0 | Ad Hoc | Manual checks | Below | — |
| 1 | Repeatable | Scripts exist, run manually | Achieved | — |
| 2 | Managed | Automated checks, gate-blocking | Achieved | — |
| 3 | Defined | Standardized processes, documentation | Partial | Target |
| 4 | Measured | Metrics-driven, trend analysis | Partial | Target |
| 5 | Optimized | Self-healing, predictive, continuous improvement | Below | 90% → Level 4+ |

Target: **Level 4+ across all 6 dimensions.**

### 1.3 Six-Dimension Maturity Matrix

| Dimension | Current | Target | Gap | Primary Design |
|---|---|---|---|---|
| Evolvable | 6/10 | 9/10 | +3 | Versioned contracts, plugin registry, backward-compatible migrations |
| Iterable | 7/10 | 9/10 | +2 | Phased delivery, each phase independently valuable |
| Observable | 7/10 | 9/10 | +2 | Unified metrics plane, health signals, trend dashboards |
| Traceable | 8/10 | 9/10 | +1 | Causal chain completion, ADR link validity, knowledge provenance |
| Troubleshootable | 6/10 | 9/10 | +3 | Owner fields, structured diagnostics, runbook validity, root-cause automation |
| Optimizable | 5/10 | 9/10 | +4 | Predictive ops, drift sweep, auto-remediation, knowledge closing loop |

**Overall: 6.5/10 → 9.0/10**

---

## 2. Gap Analysis → Solution Mapping

### 2.1 Gap Inventory

| # | Gap | Dimension | Severity | Proposed Solution |
|---|---|---|---|---|
| G1 | 440+ bin/ scripts, no central registry | Observability, Evolvability | HIGH | Bin Script Registry |
| G2 | No agent PR checklist | Troubleshootability | MEDIUM | Agent Experience Layer |
| G3 | No "who owns this" in failed checks | Troubleshootability | HIGH | Governance Hardening |
| G4 | No "what changed since last session" view | Observability | MEDIUM | Agent Experience Layer |
| G5 | Cockpit Web UI offline by default | Observability | MEDIUM | Agent Experience Layer |
| G6 | gac-worktree.sh claim cold start 60s no progress | Observability | LOW | Agent Experience Layer |
| G7 | P74 silent-workflow no dedicated dashboard | Observability | MEDIUM | Agent Experience Layer |
| G8 | Knowledge rot (ADR stale references) | Traceability, Anti-corruption | HIGH | Anti-Corruption Sweep |
| G9 | Skill rot (orphan SKILL.md) | Traceability, Anti-corruption | MEDIUM | Anti-Corruption Sweep |
| G10 | Runbook rot (commands vs actual code) | Traceability, Anti-corruption | HIGH | Anti-Corruption Sweep |
| G11 | Sub-project health invisible | Observability | MEDIUM | Sub-project Health |
| G12 | No predictive operations | Optimizability | HIGH | Predictive Ops |
| G13 | No root-cause automation | Troubleshootability | MEDIUM | Predictive Ops |
| G14 | No knowledge closing loop | Optimizability | MEDIUM | Predictive Ops |
| G15 | S3 workflow discipline social-only | Evolvability, Troubleshootability | HIGH | Governance Hardening |
| G16 | S4 concurrent drift visible but not blocked | Evolvability | MEDIUM | Governance Hardening |
| G17 | S5 onboarding no template | Evolvability | MEDIUM | Agent Experience Layer |
| G18 | 67% human bottleneck (L3 tasks) | Strategic | HIGH | Strategic Framework |

### 2.2 Solution Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         90% Maturity Architecture                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│  │ Bin Script  │  │  Agent      │  │ Governance  │  │ Predictive  │        │
│  │ Registry    │  │  Experience │  │ Hardening   │  │ Operations  │        │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘        │
│         │                │                │                │               │
│         └────────────────┼────────────────┼────────────────┘               │
│                          │                │                                │
│                    ┌─────▼─────┐  ┌──────▼──────┐                          │
│                    │  Anti-    │  │  Sub-project│                          │
│                    │ Corruption│  │  Health     │                          │
│                    │  Sweep    │  │  (8)        │                          │
│                    └─────┬─────┘  └─────────────┘                          │
│                          │                                                 │
│                    ┌─────▼─────────────────────┐                           │
│                    │   Governance & Evolution  │                           │
│                    └───────────────────────────┘                           │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Bin Script Registry & Discovery Layer

### 3.1 Problem

440+ scripts in `bin/` with no central registry. Discoverability degrades as scripts grow.

### 3.2 Design

**Location**: `bin/_registry/` (new directory, tracked by git)

**Structure**:
```
bin/_registry/
├── index.yaml              # Master index (auto-generated)
├── scripts/
│   ├── governance/
│   │   ├── gac-local-gate.yaml
│   │   ├── drift-sweep.yaml
│   │   └── ...
│   ├── state/
│   │   ├── compass_radar.yaml
│   │   └── ...
│   ├── workflow/
│   │   ├── agent-workflow.yaml
│   │   └── ...
│   ├── migration/
│   │   └── ...
│   └── knowledge/
│       └── ...
└── schemas/
    └── script-registry/v1
```

**Schema fields**: id, name, category, owner, description, inputs, outputs, dependencies, triggers, related, maturity, last_reviewed.

**Tool**: `bin/ssot/script-registry.py`
- `register` — interactive registration
- `validate` — verify all `bin/*.py` have registry entries
- `query` — search by category, owner, dependency
- `generate-index` — produce `docs/generated/script-registry.md`

**Integration**:
- `gac-local-gate` adds `script-registry-validate` check
- CI runs `script-registry.py validate` on every PR
- Subtraction quota extended: adding a script requires registry entry + deprecating another OR bumping baseline

**Evolution**:
1. Registry schema + 50 core scripts registered
2. Full migration (440 scripts)
3. Discovery integration into `compass_radar.py` and `make omo-status`
4. Dependency graph visualization
5. Auto-discovery via docstring metadata

---

## 4. Agent Experience Layer

### 4.1 Agent Quickstart

**Location**: `bin/_registry/quickstart.md` + `cockpit agent quickstart`

**Content**: 1-page summary of workflow lifecycle, key rules, and recovery commands.

### 4.2 Pre-PR Checklist

**Tool**: `bin/gac/pre-pr-check.py`
- Tests pass
- Gate passes
- Script registry validated
- No secrets in diff
- Related docs updated
- Commit message follows conventional commits
- Runbook references valid
- ADR links valid

**Integration**: Added to `gac-local-gate`; `gac-worktree.sh submit` runs it automatically.

### 4.3 Session Recovery View

**Tool**: `bin/gac/session-recovery.py --since "2 days ago"`
- Code changes (PRs, commits, agents)
- State changes (freshness, last writer)
- Anomalies (silent workflows, stale locks)
- Action items (suggested commands)

### 4.4 Cockpit Dashboard Auto-Start

**Fix**: Update `~/Library/LaunchAgents/com.cockpit.dashboard.plist`
- Change `cockpit.dashboard_server` → `cockpit-dashboard`
- Add `RunAtLoad=true`, `KeepAlive=true`
- New helper: `bash bin/gac/cockpit-auto-start.sh`

### 4.5 P74 Silent-Workflow Dashboard

**Tool**: `bin/gac/silent-workflow-dashboard.py`
- Dedicated view replacing buried gate output
- Table: workflow, last run, status, recommended action
- Recommendations: remove, add coverage, archive

### 4.6 Onboarding Template

**Location**: `docs/operations/onboarding-template.md`

**Checklist**:
- Phase 1: Script (registered, validated, --help, --json, exit codes)
- Phase 2: Gate (check added, owner field, expected field, CI coverage)
- Phase 3: Documentation (runbook, frontmatter, actual bin/ paths verified)

---

## 5. Governance Hardening

### 5.1 Owner Field Injection

**Target**: `.omo/_truth/registry/governance-checks.yaml`

Add to every active check:
```yaml
owner: <team-or-agent>
expected: "<observable correct behavior>"
remediation: "<exact command or action>"
related_runbooks:
  - docs/operations/runbook-*.md
```

**Migration tool**: `bin/ssot/governance-migration.py`
- Backfill `owner` and `expected` for all ~140 active checks
- `--dry-run` first, then `--apply`

### 5.2 Mechanical Enforcement for S3

**Pre-commit hook**: `bin/gac/hook-pre-edit-claim-check.py`
- On every commit, check if staged files are claimed by an active WorkflowRun
- Block commit if no claim found and file is in governed surface
- Allow if `AGENT_ID` is set (human escape hatch)

**MCP tool**: `check_edit_claim(path=...)`
- Agent calls before editing
- Returns claim status or blocks with message

### 5.3 S4 Concurrent Write Escalation

Three-tier model:

| Tier | Condition | Action | Gate Result |
|---|---|---|---|
| Tier 1 | Soft drift (current) | emit_topic | PASS |
| Tier 2 | Hard drift (same file, different content, <5min) | emit_topic + block_merge | FAIL |
| Tier 3 | Conflict (merge conflict detected) | emit_topic + halt_pipeline + notify_human | HALT |

**Tool**: `bin/gac/concurrent-write-analyzer.py`
- Tracks write timestamps and content hashes per file
- Tier 2/3 opt-in via `make gac-local-gate --strict`

### 5.4 Subtraction Quota Enforcement

**Tool**: `bin/gac/subtraction-quota-enforcer.py`
- Checks if adding a new artifact exceeds baseline
- Suggests candidates for deprecation
- CI fails when quota exceeded without deprecation or baseline bump

---

## 6. Predictive Operations & Auto-Remediation

### 6.1 Health Trend Predictor

**Tool**: `bin/gac/health-trend-predictor.py`
- Input: `governance-history.jsonl` time series
- Output: predicted health in 24h, 7d, 30d
- Signals: freshness declining, health declining, concurrent-write-drift increasing, silent-workflows increasing

### 6.2 Auto-Remediation Engine

**Tool**: `bin/gac/auto-remediate.py`

**Rules** (YAML, human-reviewed):
```yaml
rules:
  - id: auto-rotate-history
    condition: "history.jsonl > 90 days old"
    action: bin/gac/rotate-history.py
    safe: true
    approval: none

  - id: auto-prune-stale-locks
    condition: "stale locks > 0"
    action: bin/gac/prune-locks
    safe: true
    approval: none

  - id: auto-archive-stale-tasks
    condition: "planned tasks > 30 days old"
    action: bin/plan/sync-planned-to-done.py
    safe: true
    approval: none

  - id: auto-refresh-state
    condition: "freshness_score < 80"
    action: make state-sync
    safe: true
    approval: none

  - id: auto-fix-submodule-drift
    condition: "submodule pointer drift detected"
    action: bin/ssot/submodule-pointer-transaction.sh
    safe: true
    approval: governance-team
```

**Execution modes**:
- `--dry-run`: emit events only
- `--auto`: execute `approval: none` rules
- `--supervised`: execute all, ask for approval on `approval: <team>`

### 6.3 Root-Cause Automation

**Tool**: `bin/gac/root-cause-collector.py`

When failure occurs:
1. Capture snapshot: `launchctl list`, `git status`, `compass_radar.py --json`, `agent-workflow.py compliance --json`
2. Package as evidence tarball
3. Append to `governance-history.jsonl`
4. Suggest relevant runbook from `FAILURE_TYPE_TO_RUNBOOK` mapping

### 6.4 Knowledge Closing Loop

**Tool**: `bin/gac/knowledge-closing-loop.py`

After every auto-remediation or manual fix:
1. Does a runbook exist? → create draft or update
2. Does a gate check exist? → propose new or update
3. Is this recurring (≥3 occurrences)? → escalate to governance-team

---

## 7. Anti-Corruption Sweep System

### 7.1 Three-Tier Model

| Tier | Scope | Frequency | Integration | Action on Failure |
|---|---|---|---|---|
| Tier 1: Gate | Per-PR | Every PR | `gac-local-gate` | Block merge |
| Tier 2: Sweep | Weekly | Every Sunday 02:00 | Cron + report | Emit alert, create ticket |
| Tier 3: Audit | Monthly | 1st of month | Governance review | Create ADR if pattern found |

### 7.2 Weekly Drift Sweep

**Tool**: `bin/gac/drift-sweep.py`

**Checks**:
- `ssot_pointer_drift`
- `mof_capability_drift`
- `submodule_pointer_drift`
- `adr_link_validity`
- `adr_frontmatter_validity`
- `scene_card_validity`
- `runbook_command_validity`
- `runbook_frontmatter_validity`
- `runbook_age_check`
- `skill_registry_validity`
- `skill_frontmatter_validity`
- `doc_link_validity`
- `doc_hardcoded_values`
- `governance_check_coverage`
- `script_registry_coverage`
- `layer_contract_compliance`

**Output**: JSON report with pass/warn/fail counts, action items, and suggested fixes.

### 7.3 Skill Registry Verification

**Tool**: `bin/gac/skill-registry-verify.py`
- Scan `.agents/skills/*/SKILL.md`
- Verify referenced `bin/` commands exist
- Report orphans

### 7.4 Runbook Validity CI Check

Add to `governance-checks.yaml`:
```yaml
- id: CR-DOC-RUNBOOK-VALIDITY
  dimension: X4
  layer: L3
  name: Runbook Command Validity
  description: All bin/ commands referenced in runbooks exist
  check_type: doc_lifecycle
  target: docs/operations/runbook-*.md
  executor:
    - ci_gate
    - omo_audit
  owner: governance-team
  expected: "Every bin/ path in runbook body resolves to existing file"
  remediation: "Update runbook command reference or restore missing script"
```

### 7.5 ADR Link Validity

**Tool**: `bin/gac/adr-link-validator.py`
- Scan `.omo/_knowledge/decisions/*.md` and `docs/adr/*.md`
- Verify all file path references exist
- Allow `docs/_archived/` references
- Flag `.omo/` mutable state references as warnings

---

## 8. Sub-project Health Visibility

### 8.1 Design

**Tool**: `bin/meta/sub-project-health.py`

**Health scoring**:
- 🟢 GREEN: tests pass, commit < 7 days
- 🟡 YELLOW: tests pass, commit 7-30 days
- 🔴 RED: tests fail OR commit > 30 days OR detached HEAD

**CI integration**: `make ci-local-fast` includes `sub-project-health` check. Fails if any sub-project is RED.

**Data source**: Each submodule's `make test-diff`. Cache in `.omo/_control/sub-project-health.json` (refreshed daily by cron).

**Evolution**:
1. Aggregator reads each submodule's test output
2. Health cached in `.omo/_control/`
3. `make omo-status` includes sub-project health section
4. Trend analysis: sub-project health over time
5. Auto-alert when sub-project turns RED

---

## 9. Phased Implementation Plan

### Phase 1: Foundation (Weeks 1-2)

Goal: Establish discoverability and basic governance hardening.

| Task | Deliverable | Owner | Verification |
|---|---|---|---|
| 1.1 Bin script registry schema | `bin/_registry/schemas/script-registry/v1` | governance-team | Schema validates against 10 sample scripts |
| 1.2 Registry 50 core scripts | `bin/_registry/scripts/**/*.yaml` | governance-team | `script-registry.py validate` passes |
| 1.3 Owner fields in governance-checks | Backfill `owner:` and `expected:` for all ~140 active checks | governance-team | `gac-local-gate` includes owner-field check |
| 1.4 Pre-PR checklist tool | `bin/gac/pre-pr-check.py` | governance-team | `pre-pr-check.py` runs in <5s, detects known issues |
| 1.5 Subtraction quota enforcer | `bin/gac/subtraction-quota-enforcer.py` | governance-team | CI fails when quota exceeded without deprecation |

**Exit criteria**:
- `make ci-local-fast` passes with new checks
- 50 core scripts registered
- All governance checks have owner fields
- Pre-PR checklist catches 3 known issue types

### Phase 2: Anti-Corruption (Weeks 3-4)

Goal: Detect knowledge rot, skill rot, and runbook rot.

| Task | Deliverable | Owner | Verification |
|---|---|---|---|
| 2.1 Drift sweep tool | `bin/gac/drift-sweep.py` with 15 checks | governance-team | Weekly sweep runs in <2min, produces actionable report |
| 2.2 ADR link validator | `bin/gac/adr-link-validator.py` | governance-team | Detects 100% of known broken links in test set |
| 2.3 Runbook validity check | `CR-DOC-RUNBOOK-VALIDITY` in governance-checks.yaml | governance-team | CI catches stale runbook references |
| 2.4 Skill registry verify | `bin/gac/skill-registry-verify.py` | governance-team | Detects orphan skills in test set |
| 2.5 Weekly sweep cron | GitHub Action + launchd/cron | governance-team | Runs every Sunday 02:00, posts report |

**Exit criteria**:
- All 15 sweep checks pass on current codebase
- Weekly sweep integrated into CI
- Zero knowledge rot issues detected

### Phase 3: Predictive Operations (Weeks 5-6)

Goal: Detect signals before they become failures.

| Task | Deliverable | Owner | Verification |
|---|---|---|---|
| 3.1 Health trend predictor | `bin/gac/health-trend-predictor.py` | governance-team | Predictions within 10% of actual 7-day health |
| 3.2 Auto-remediation engine | `bin/gac/auto-remediate.py` with 5 rules | governance-team | Dry-run mode produces correct action items |
| 3.3 Root-cause collector | `bin/gac/root-cause-collector.py` | governance-team | Captures complete snapshot on simulated failure |
| 3.4 Knowledge closing loop | `bin/gac/knowledge-closing-loop.py` | governance-team | Creates draft runbook for new failure type |

**Exit criteria**:
- Health prediction accuracy > 80%
- Auto-remediation dry-run covers 5 common failure modes
- Root-cause collector captures all required artifacts
- Knowledge closing loop creates at least 1 new runbook from simulated failure

### Phase 4: Agent Experience (Weeks 7-8)

Goal: Reduce onboarding friction and improve daily usability.

| Task | Deliverable | Owner | Verification |
|---|---|---|---|
| 4.1 Agent quickstart | `bin/_registry/quickstart.md` + `cockpit agent quickstart` | governance-team | New agent can complete workflow lifecycle in <10min using only quickstart |
| 4.2 Pre-PR checklist CI | Integrated into `gac-local-gate` + `gac-worktree.sh submit` | governance-team | Blocks PR when known issues present |
| 4.3 Session recovery view | `bin/gac/session-recovery.py` + `make omo-status --recovery` | governance-team | Shows changes since last session in <5s |
| 4.4 Cockpit auto-start | `bin/gac/cockpit-auto-start.sh` + fixed plist | governance-team | `make cockpit-start` brings up dashboard in <10s |
| 4.5 Silent-workflow dashboard | `bin/gac/silent-workflow-dashboard.py` | governance-team | Shows all silent workflows with recommended actions |
| 4.6 Onboarding template | `docs/operations/onboarding-template.md` | governance-team | Used for 2 new capabilities, checklist 100% complete |

**Exit criteria**:
- Agent quickstart covers all workflow lifecycle steps
- Pre-PR checklist catches 5 issue types
- Session recovery shows code, state, and anomaly changes
- Cockpit dashboard starts with single command
- Silent-workflow dashboard replaces buried gate output
- Onboarding template used for 2 new capabilities

### Phase 5: Full Maturity (Weeks 9-12)

Goal: Integrate all components, achieve 90% maturity.

| Task | Deliverable | Owner | Verification |
|---|---|---|---|
| 5.1 Governance hardening complete | S3 mechanical enforcement, S4 escalation, owner fields | governance-team | All governance checks have owner fields; pre-commit hook active |
| 5.2 Predictive ops integrated | Health predictor + auto-remediation + root-cause + knowledge loop | governance-team | All 4 tools integrated into `compass_radar.py` and `make omo-status` |
| 5.3 Anti-corruption sweep automated | Weekly drift sweep + monthly audit | governance-team | Sweep runs weekly, audit runs monthly, both produce actionable reports |
| 5.4 Sub-project health visible | Aggregator + CI check + omo-status integration | governance-team | `make omo-status` shows sub-project health; CI fails on RED |
| 5.5 Maturity scorecard | 6-dimension scorecard automated | governance-team | `make maturity-scorecard` shows all dimensions ≥ 8/10 |

**Exit criteria**:
- All 6 dimensions ≥ 8/10
- Overall maturity ≥ 9.0/10
- Zero unregistered scripts
- Zero orphan skills
- Zero stale runbook references
- Zero broken ADR links
- All sub-projects GREEN
- Predictive ops accuracy > 80%
- Auto-remediation covers 10+ failure modes

---

## 10. Governance & Evolution Model

### 10.1 Design Principle

> **"The governance system must govern itself. Any check, rule, or process that cannot detect its own obsolescence is a liability."**

### 10.2 Self-Governance Cycle

```
┌─────────────────────────────────────────────────────────────────┐
│                    Self-Governance Cycle                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐  │
│  │ Measure  │ →  │ Evaluate │ →  │ Improve  │ →  │ Verify   │  │
│  │ (sweep)  │    │ (score)  │    │ (fix)    │    │ (re-measure)│
│  └──────────┘    └──────────┘    └──────────┘    └──────────┘  │
│         ↑                                              │        │
│         └──────────────────────────────────────────────┘        │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Frequency**: Monthly

**Inputs**:
- Drift sweep results
- Governance history
- Health trends
- Operator feedback

**Outputs**:
- Maturity scorecard update
- Quota baseline adjustments
- New check proposals
- Deprecation candidates
- ADR for systemic issues

### 10.3 Evolution Triggers

| Trigger | Action | Owner |
|---|---|---|
| Maturity scorecard shows dimension < 8/10 for 2 consecutive months | Create improvement plan | governance-team |
| Drift sweep finds > 5 issues in same category | Create ADR for systemic fix | governance-team |
| Health predictor accuracy < 70% | Retrain or replace predictor | governance-team |
| Auto-remediation false positive rate > 5% | Review and tighten rules | governance-team |
| Operator feedback "X is too hard" | Simplify X, add tooling or documentation | governance-team |
| New sub-project added | Register in sub-project health aggregator | governance-team |

### 10.4 Backward Compatibility

All new tools and checks MUST:
1. Have `--dry-run` mode
2. Have `--json` output
3. Have `--help` documentation
4. Return 0 on success, 1 on failure
5. Not break existing `gac-local-gate` checks
6. Be opt-in via feature flags or `--strict` mode before becoming default

---

## 11. Observability & Metrics

### 11.1 Unified Metrics Plane

All metrics flow through `compass_radar.py` → `health.yaml` → `make omo-status`.

**New metrics added**:

| Metric | Source | Frequency | Consumer |
|---|---|---|---|
| `script_registry_count` | `script-registry.py` | Daily | `make omo-status`, dashboard |
| `script_registry_coverage` | `script-registry.py validate` | Per-PR | `gac-local-gate` |
| `drift_sweep_score` | `drift-sweep.py` | Weekly | `make omo-status`, governance review |
| `knowledge_rot_count` | `drift-sweep.py` | Weekly | Governance review |
| `skill_rot_count` | `skill-registry-verify.py` | Weekly | Governance review |
| `runbook_rot_count` | `runbook-validity` check | Per-PR | `gac-local-gate` |
| `sub_project_health_score` | `sub-project-health.py` | Daily | `make omo-status`, CI |
| `prediction_accuracy` | `health-trend-predictor.py` | Weekly | Governance review |
| `auto_remediation_count` | `auto-remediate.py` | Daily | `make omo-status` |
| `maturity_dimension_score` | `maturity-scorecard.py` | Monthly | Governance review |

### 11.2 Health Scorecard

```yaml
# .omo/state/health.yaml addition
maturity:
  evolvable: 8
  iterable: 9
  observable: 9
  traceable: 9
  troubleshootable: 8
  optimizable: 8
  overall: 8.5
  last_calculated: "2026-08-24T06:00:00Z"
  next_calculated: "2026-09-24T06:00:00Z"
```

### 11.3 Trend Dashboards

**Existing**: `health-trend-chart.py` (ASCII sparkline)

**New**: `bin/gac/maturity-trend-chart.py`
- 6-dimension trend over time
- Predicts time to 90% target
- Identifies dimensions needing attention

---

## 12. Risk Analysis & Mitigation

### 12.1 Risk Register

| Risk | Probability | Impact | Mitigation | Owner |
|---|---|---|---|---|
| Script registry becomes stale | Medium | Medium | Subtraction quota enforcement; weekly sweep validates | governance-team |
| Pre-PR checklist too strict, slows development | Medium | Medium | Opt-in via `--strict` first; tune thresholds based on feedback | governance-team |
| Auto-remediation causes data loss | Low | High | All auto-remediation rules marked `safe: true` by default; `--supervised` mode for risky actions | governance-team |
| Health predictor gives false confidence | Medium | Medium | Prediction accuracy tracked; alert if accuracy < 70% | governance-team |
| Drift sweep creates noise | Medium | Medium | Tiered alerts (warn vs fail); actionable fix suggestions | governance-team |
| Sub-project health check fails due to environment | Medium | Low | Cache results; allow environment-specific skip markers | governance-team |
| Governance hardening blocks legitimate work | Low | High | Escape hatch (`AGENT_ID`); human override always possible | governance-team |
| 90% target unrealistic | Low | Medium | Phased delivery; each phase independently valuable; target adjustable | governance-team |

### 12.2 Failure Modes

| Failure Mode | Detection | Recovery |
|---|---|---|
| Script registry out of sync | `script-registry.py validate` fails in CI | Automated PR with missing entries |
| Pre-PR checklist blocks valid PR | Human override via `--no-verify` | Review checklist rules, adjust thresholds |
| Auto-remediation fails | Event emitted to `events.jsonl` | Human notified via alert; rule disabled |
| Health predictor inaccurate | Accuracy metric < 70% | Retrain or fall back to trend-only mode |
| Drift sweep misses issues | Monthly audit finds issues not in sweep | Add new checks to sweep |
| Sub-project health false negative | Environment-specific test failure | Add skip marker, investigate root cause |

---

## 13. Success Criteria (90% Maturity)

### 13.1 Dimension Scorecard

| Dimension | Measurement | Current | Target | Gate |
|---|---|---|---|---|
| **Evolvable** | % of new features added without breaking existing contracts | 60% | ≥ 90% | CI tracks backward-compat failures |
| **Iterable** | % of phases delivered on time with independent value | 70% | ≥ 90% | Phase exit criteria met |
| **Observable** | % of components with health signals in `make omo-status` | 70% | ≥ 95% | `make omo-status` shows all components |
| **Traceable** | % of actions with complete causal chain | 80% | ≥ 95% | Random audit of events.jsonl |
| **Troubleshootable** | % of failures with owner, expected, remediation | 40% | ≥ 90% | Failed checks have all fields |
| **Optimizable** | % of metrics queryable for trend analysis | 50% | ≥ 90% | All metrics in `governance-history.jsonl` |

### 13.2 Operational Metrics

| Metric | Current | Target | Measurement |
|---|---|---|---|
| Health score | 70/100 | ≥ 85/100 | `compass_radar.py` |
| Governance anomaly score | 0-17/100 | ≤ 5/100 | `compass_radar.py` |
| Bin script registry coverage | 0% | 100% | `script-registry.py validate` |
| Governance checks with owner fields | ~10% | 100% | `governance-checks.yaml` audit |
| Pre-PR checklist coverage | 0% | 100% | CI tracking |
| Drift sweep issues per week | Unknown | ≤ 3 | `drift-sweep.py` |
| Knowledge rot issues | Unknown | 0 | `drift-sweep.py` |
| Skill rot issues | Unknown | 0 | `skill-registry-verify.py` |
| Runbook rot issues | Unknown | 0 | `runbook-validity` check |
| Sub-project health (GREEN) | Unknown | 100% | `sub-project-health.py` |
| Prediction accuracy | N/A | ≥ 80% | `health-trend-predictor.py` |
| Auto-remediation coverage | 0% | ≥ 10 failure modes | `auto-remediate.py` |
| Silent workflow dashboard adoption | 0% | ≥ 80% | Usage tracking |
| Agent quickstart completeness | 0% | 100% | Checklist audit |

### 13.3 Timeline

| Week | Milestone | Dimensions Improved | Overall Maturity |
|---|---|---|---|
| 1-2 | Phase 1: Foundation | Evolvable, Troubleshootable | 7.0/10 |
| 3-4 | Phase 2: Anti-Corruption | Traceable, Troubleshootable | 7.5/10 |
| 5-6 | Phase 3: Predictive Ops | Optimizable, Troubleshootable | 8.0/10 |
| 7-8 | Phase 4: Agent Experience | Observable, Evolvable | 8.5/10 |
| 9-12 | Phase 5: Full Maturity | All | **9.0/10** |

### 13.4 Go/No-Go Criteria

**Phase 1 Go/No-Go**:
- [ ] `script-registry.py validate` passes for 50 core scripts
- [ ] All governance checks have owner fields
- [ ] `pre-pr-check.py` runs in <5s
- [ ] Subtraction quota enforcer blocks invalid PRs

**Phase 2 Go/No-Go**:
- [ ] `drift-sweep.py` runs in <2min
- [ ] All 15 sweep checks pass on current codebase
- [ ] Zero knowledge rot issues detected
- [ ] Weekly sweep integrated into CI

**Phase 3 Go/No-Go**:
- [ ] Health prediction accuracy > 80%
- [ ] Auto-remediation dry-run covers 5 failure modes
- [ ] Root-cause collector captures complete snapshot
- [ ] Knowledge closing loop creates runbook from simulated failure

**Phase 4 Go/No-Go**:
- [ ] Agent quickstart enables workflow completion in <10min
- [ ] Pre-PR checklist catches 5 issue types
- [ ] Session recovery shows changes since last session
- [ ] Cockpit dashboard starts with single command

**Phase 5 Go/No-Go**:
- [ ] All 6 dimensions ≥ 8/10
- [ ] Overall maturity ≥ 9.0/10
- [ ] All exit criteria from Phases 1-4 met
- [ ] Zero critical risks unmitigated

---

## 14. Governance Evolution

### 14.1 ADR Requirements

Each phase requires at least one ADR:
- Phase 1: ADR for script registry schema and owner field injection
- Phase 2: ADR for weekly drift sweep and anti-corruption model
- Phase 3: ADR for auto-remediation and predictive ops
- Phase 4: ADR for agent experience layer and mechanical enforcement
- Phase 5: ADR for maturity scorecard and self-governance cycle

### 14.2 Quota Adjustments

As new tools and checks are added, subtraction quota baselines must be adjusted:
- Rules: current 139 → target 150 (net +11 over 5 phases)
- ADRs: current 361 → target 380 (net +19 over 5 phases)
- Scripts: current 443 → target 460 (net +17 over 5 phases)

**Enforcement**: `subtraction-quota-enforcer.py` blocks PRs that exceed baseline without deprecation or explicit baseline bump.

### 14.3 Review Cadence

| Review | Frequency | Audience | Output |
|---|---|---|---|
| Maturity scorecard | Monthly | governance-team | Scorecard update, improvement plan |
| Drift sweep | Weekly | governance-team | Sweep report, action items |
| Phase retrospective | Per phase | governance-team + operators | Phase report, lessons learned |
| Annual architecture review | Yearly | governance-team + operators | Architecture update, roadmap adjustment |

---

## 15. Appendix

### A. Tool Inventory

| Tool | Location | Phase | Status |
|---|---|---|---|
| `script-registry.py` | `bin/ssot/` | 1 | New |
| `pre-pr-check.py` | `bin/gac/` | 1 | New |
| `subtraction-quota-enforcer.py` | `bin/gac/` | 1 | New |
| `drift-sweep.py` | `bin/gac/` | 2 | New |
| `adr-link-validator.py` | `bin/gac/` | 2 | New |
| `skill-registry-verify.py` | `bin/gac/` | 2 | New |
| `health-trend-predictor.py` | `bin/gac/` | 3 | New |
| `auto-remediate.py` | `bin/gac/` | 3 | New |
| `root-cause-collector.py` | `bin/gac/` | 3 | New |
| `knowledge-closing-loop.py` | `bin/gac/` | 3 | New |
| `session-recovery.py` | `bin/gac/` | 4 | New |
| `cockpit-auto-start.sh` | `bin/gac/` | 4 | New |
| `silent-workflow-dashboard.py` | `bin/gac/` | 4 | New |
| `sub-project-health.py` | `bin/meta/` | 4 | New |
| `maturity-scorecard.py` | `bin/gac/` | 5 | New |
| `governance-migration.py` | `bin/ssot/` | 1 | New |
| `hook-pre-edit-claim-check.py` | `bin/gac/` | 1 | New |
| `concurrent-write-analyzer.py` | `bin/gac/` | 1 | New |

### B. File Inventory

| File | Location | Phase | Status |
|---|---|---|---|
| `bin/_registry/schemas/script-registry/v1` | `bin/_registry/` | 1 | New |
| `bin/_registry/scripts/**/*.yaml` | `bin/_registry/` | 1-2 | New |
| `bin/_registry/index.yaml` | `bin/_registry/` | 1 | Auto-generated |
| `bin/_registry/quickstart.md` | `bin/_registry/` | 4 | New |
| `docs/operations/onboarding-template.md` | `docs/operations/` | 4 | New |
| `docs/operations/runbook-concurrent-write.md` | `docs/operations/` | 1 | New |
| `docs/operations/runbook-gate-failure.md` | `docs/operations/` | 3 | New |
| `docs/operations/runbook-submodule-drift.md` | `docs/operations/` | 2 | New |

### C. CI Integration Points

| Check | Current | Target |
|---|---|---|
| `gac-local-gate` checks | 49 | 55+ |
| CI steps | ~18 | ~25 |
| Subtraction quota enforcement | Baseline only | Baseline + per-artifact-type |

### D. Rollback Plan

Each phase is independently valuable and can be rolled back:
- Phase 1: Disable new `gac-local-gate` checks via `--skip` flags
- Phase 2: Disable weekly sweep cron, keep tools for manual use
- Phase 3: Disable auto-remediation cron, keep in dry-run mode
- Phase 4: Revert launchd plist, keep tools for manual use
- Phase 5: Maturity scorecard is read-only, no rollback needed

---

## Document Control

| Version | Date | Author | Changes |
|---|---|---|---|
| 0.1 | 2026-08-24 | governance-team | Initial draft from strategic analysis |
| 0.2 | 2026-08-24 | governance-team | Added phases 1-5, governance evolution, success criteria |
| 1.0 | TBD | governance-team | Approved for implementation |

**Next actions**:
1. Review this document with operators
2. Prioritize Phase 1 tasks
3. Create BET for each phase
4. Begin implementation
