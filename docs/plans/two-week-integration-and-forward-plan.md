---
status: superseded
lifecycle: history
owner: auto-fix-loop
last_updated: 2026-08-25
superseded-by: docs/plans/2026-08-25-y1-value-loop-phase.md
type: ephemeral
---

# Two-Week System Integration & Forward Plan

> **Date**: 2026-08-24
> **Window analyzed**: 2026-08-10 → 2026-08-24 (14 days)
> **Commits**: 802 | **PRs merged**: 30+ | **Concurrent agents**: 4-8 active
> **Audience**: operator, future agents, architecture reviewers

---

## Part I — What Happened (Two-Week Retrospective)

### 1.1 Quantitative Summary

| Metric | Value |
|---|---|
| Total commits | 802 |
| PRs merged | ~30+ |
| Commit types | feat:177, chore:171, fix:125, docs:108, test:9, ci:6 |
| Top scopes | governance(65), gac(60), documents(33), resident(27), submodule(25) |
| Health score evolution | 28/100 → 70/100 |
| Governance anomaly | 25/100(熔断) → 0/100 |
| Drift sweep | N/A → 16/16 PASS, 0 FAIL |
| Knowledge graph | N/A → 968 nodes, 730 edges |
| Bin scripts | ~420 → ~476 (+56 net) |
| BET completion | 121/123 → 122/136 (12 new T10 candidates) |

### 1.2 Thematic Analysis — Six Major Threads

#### Thread A: Governance Hardening (the largest thread)

**What happened**: The system went from "structurally healthy but operationally fragile" to "structurally healthy and operationally self-aware."

Key deliverables:
- **Drift detection**: drift-sweep.py aggregates 16 independent checks into one weekly report
- **State freshness gate**: 5-file SSOT contract with CI enforcement
- **P74 silent-workflow gate**: promoted to always-on; silent regressions block every commit
- **Concurrent-write drift detector**: fingerprint snapshot at gate start, soft warning on torn reads
- **Runbook validity gate**: validate-runbook-refs.py catches stale bin/ references in docs
- **L3 remediation tool**: generates actionable plan for high-risk tasks
- **Anti-corrosion check**: detects tool bloat, doc decay, scene stagnation
- **Remediation engine**: auto-fixes stale docs, suggests archiving deprecated tools
- **Subtraction quota**: enforces bin/ script count ceiling + quarterly archive quota
- **Gitlink ancestry gate**: intercepts concurrent submodule pointer rollback
- **Bin-quota-diff**: per-change conservation check for bin/ script additions

**Impact**: Before this window, a single agent session could leave 45 stale locks and 61 zombie runs undetected. Now, the system catches these within one gate run.

#### Thread B: Knowledge Infrastructure

**What happened**: The project went from "no unified knowledge access" to "searchable knowledge graph."

Key deliverables:
- `bin/kb/knowledge-graph.py` — scans 968 assets across 6 types, produces .kb/graph.json
- `bin/kb/search.py` — keyword search + reverse lookup (--refs)
- `bin/kb/staleness-check.py` — detects 98 stale files out of 491 checked
- `docs/plans/knowledge-indexing-plan.md` — full design document
- 7 operational runbooks covering all new gates
- `docs/operations/README.md` — consolidated tool reference table
- Architectural review at `docs/operations/ARCHITECTURAL-REVIEW-2026-08-24.md`

**Impact**: An operator can now answer "what references X?" or "what's related to Y?" in seconds instead of grepping across 5 directories.

#### Thread C: Architecture Evolution (concurrent agents)

Major structural changes:
- **AST semantic callgraph** (#2097): blast radius gate + bootstrap indexer
- **BCOS 业务域系统 W1-W4**: signal routing → evolution engine → north star meter
- **Resident agent体系 M1-M4**: event-driven daemon with 5 roles (sediment/decision/execute/monitor/heartbeat)
- **Project convergence ADR-0423**: family-hub paused, metaos boundary defined, mesh-router archived
- **Documents content plane**: full convergence as sovereign content plane
- **omlxc v3 compute hub**: local compute integration with KV warming
- **Sovereignty kernel W1-W2**: JSONL shadow delivery + delegation mandates

**Assessment**: These are not cleanup — they represent genuine architectural advancement. The system gained real new capabilities (local compute, resident agents, BCOS business domain) while simultaneously being cleaned up.

#### Thread D: Value Tracking & North Star

The concurrent agents built a complete value measurement pipeline:
- `attest-review.py` — human value attestation interactive flow
- `episode-source-aggregator.py` — three-source episode draft aggregator
- `est-minutes-coefficient v1` — time ledger estimation coefficient table
- Weekly review card + meta-doctor M3 ritual
- North Star weekly cron
- Document-review calibration path

**Assessment**: This addresses the "67% human bottleneck" identified in the architectural review. By building attestation and tracking infrastructure, the system is making human judgment more efficient rather than trying to replace it.

#### Thread E: Scene Activation & Maturity

- Scene activation sweeper (Phase 4)
- Signal poller health monitoring
- Alert enforcement + tool lifecycle + UHS
- Maturity design document targeting 90% UHS
- 12 new T10-series candidate bets (all 0.5 day each) for maturity improvements

**Assessment**: The system is now actively working toward measurable maturity targets rather than just maintaining status quo.

#### Thread F: Project Convergence

- family-hub paused (not deleted, just deprioritized)
- metaos boundary defined
- mesh-router archived
- Documents content plane converged
- KEMS convergence audit completed

**Assessment**: Correctly reduces surface area by consolidating overlapping projects.

---

## Part II — What My Work Contributed

Across this window, my sessions contributed:

| Category | Deliverables | PRs |
|---|---|---|
| Drift detection | drift-sweep.py (initial version), concurrent-write drift detector, state-freshness gate wiring | #1989, #1957 |
| Knowledge indexing | knowledge-graph.py, search.py, staleness-check.py, planning doc | #2105 |
| Runbook coverage | runbook-p74-silent-workflow.md, runbook-state-freshness.md, ops README tool reference | #2059, #2064, #2065 |
| L3 visibility | l3-remediation.py | #2071 |
| Agent experience | agent-quickstart SKILL.md | #2065 |
| Stale task cleanup | sync-planned-to-done.py (61 candidates archived) | #1928 |
| Bug fixes | venv python anchor, debt dashboard mirror, observability dedup | #1915, #1936, #1957 |
| Documentation | architectural review, cleanup retrospective, operations index | #2028, multiple |

**What I did NOT do (correctly deferred)**:
- Broker enforcement of `.omo/` writes (needs new ADR, multi-tool refactor)
- Knowledge graph Phase 2-3 (search UI, staleness cron) (Phase 1 proves concept first)
- Cockpit dashboard auto-start (launchd plist already exists and works)
- Deleting historical stashes (they belong to other sessions)

---

## Part III — Current State Assessment

### 3.1 What's Working Well

1. **Self-healing gates** — the system catches its own drift without human intervention
2. **Knowledge graph** — 968 assets searchable in <1 second
3. **Runbooks cover all new behaviors** — no undocumented failure modes
4. **Health metrics are honest** — 70/100 reflects reality (3 L3 blocked on human)
5. **Concurrent agent coordination** — worktrees + PASW prevent most collisions
6. **Value tracking pipeline** — north star metrics are now measured, not guessed

### 3.2 What Needs Attention

| Issue | Impact | Effort | Priority |
|---|---|---|---|
| 12 T10 candidate BETs unclaimed | maturity stuck at current level | 6 days total | HIGH |
| 2 blocked Y3 bets (human-only) | health capped at 70 | external dependency | can't fix |
| 98 stale knowledge files | search returns outdated info | ongoing maintenance | MEDIUM |
| Concurrent agent flake | occasional gate false positives | tolerated by design | LOW |
| No scheduled KB rebuild | graph.json goes stale | add cron | LOW |
| 55+ historical stashes | workspace noise | needs owner decision | LOW |
| Cockpit Web UI offline by default | non-CLI users have no entry point | launchd plist exists but not loaded | LOW |

### 3.3 The Human Bottleneck (unchanged)

The architectural review identified that 67% of pending tasks are owned by `human`. This hasn't changed. The 2 blocked Y3 bets (`BET-Y3H1-T7-01` 中试/政策申报, `BET-Y3H2-T7-01` 公文场景 routine) require external events (user 借调国转中心).

However, the concurrent agents' value-tracking work (attest-review, north-star weekly, calibration path) directly addresses this bottleneck by making human judgment more structured and time-bounded.

---

## Part IV — Forward Plan

### Phase α: Immediate (this week) — Claim T10 BETs

The 12 unclaimed T10 candidate bets are the highest-leverage next actions. Each is estimated at 0.5 day:

| BET | What it does | Why it matters |
|---|---|---|
| T10-01 | Script registry full registration | Makes all 476 scripts discoverable via registry |
| T10-02 | 90pct-maturity-design.md 落盘 | Already written, needs formal registration |
| T10-03 | ADR link repair | Fixes broken cross-references between ADRs |
| T10-04 | Governance owner field migration | Every check gets an explicit owner |
| T10-05 | compass_radar new indicators | Integrate drift-sweep + KB staleness into radar |
| T10-06 | Scorecard granularity upgrade | Enables 9/10 maturity scores |
| T10-07 | Droid-Shield false positive fix | Reduces gate noise |
| T10-08 | Closeout hard-gate / bet binding | Ensures BETs are properly closed out |
| T10-09 | Worktree submodule init strategy | Reduces environment-dependent gate failures |
| T10-10 | Maturity metric alignment (health/scorecard/ledger) | Single source of truth for "how mature are we" |

**Recommended order**: T10-05 → T10-10 → T10-03 → T10-04 → rest

Why: T10-05 integrates the new tools (drift-sweep, KB) into the primary health dashboard. T10-10 ensures all maturity numbers agree. These two unlock meaningful measurement of the others.

### Phase β: Short-term (next 2 weeks)

1. **KB cron integration** — schedule `knowledge-graph.py` rebuild + `staleness-check.py` as weekly cron. Wire results into drift-sweep.
2. **Stale file triage** — process the 98 files flagged by staleness-check. Either update their last-reviewed date or archive them.
3. **Scene card activation** — 3 scenes stuck in shadow >30 days. Use remediation-engine's notify_activation output to decide activate/archive.
4. **Deprecated tool archival** — 19 tools suggested for archival by anti-corrosion-check. Execute the archival.
5. **ADR frontmatter backfill** — use adr-frontmatter-backfill.py to add missing status/lifecycle to any remaining gaps.

### Phase γ: Medium-term (next month)

1. **KB search integration into cockpit** — expose search.py as a cockpit command so humans can query from the CLI entry point
2. **Automated BET claiming** — when a T10 bet's preconditions are met (detected by drift-sweep), auto-create an agent-workflow run
3. **Cross-project test aggregator** — single command that runs each submodule's tests and reports pass/fail
4. **Doc-code divergence detector** — compare script --help output against what runbooks say it does
5. **Scheduled maintenance cron** — monthly drift-sweep + staleness-check + bin-convergence + ADR validity, emits report

### Phase δ: Long-term (next quarter)

1. **Full knowledge graph Phase 2-3** — search UI + automated staleness cron (currently only Phase 1 built)
2. **UHS 90% target** — requires completing all T10 bets + scene activation + value attestation
3. **Broker enforcement** — if concurrent-write contention becomes a real problem (not just noise), implement fcntl-level blocking during gate runs
4. **Multi-agent scheduling optimization** — reduce the 67% human bottleneck by improving agent autonomy within governed boundaries

---

## Part V — Risk Register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Human bottleneck persists | HIGH | Strategic goals stall | Value attestation pipeline makes judgment more efficient |
| Bin/ scripts grow past quota | MEDIUM | Tool bloat slows discovery | Subtraction quota enforced by gate |
| Concurrent agents increase contention | MEDIUM | More gate flakes, slower pushes | Worktree isolation + drift detector |
| Knowledge graph goes stale | MEDIUM | Search becomes misleading | Add weekly cron rebuild |
| Y3 frozen BETs never unfreeze | LOW | 2 strategic capabilities never delivered | External dependency, not solvable internally |
| Key person departure | LOW | System loses its operator | All knowledge documented; agents can operate autonomously |

---

## Part VI — Summary

### What changed in two weeks

The system went through a **phase transition**. Before: a collection of tools with no systematic way to detect or respond to degradation. After: a self-aware system with 16 drift checks, a searchable knowledge graph, actionable remediation plans, and a clear maturity roadmap.

### The core insight

The two weeks of concurrent activity revealed something important about the project's nature: **omostation is not a software project that happens to have agents — it is an agent ecosystem that happens to produce software.**

The most impactful work wasn't writing application code. It was:
- Building the nervous system (drift-sweep, compass_radar, KB graph)
- Building the immune system (gates, anti-corrosion, remediation engine)
- Building the memory (knowledge graph, runbooks, retrospective docs)
- Building the metabolism (value tracking, north star metrics, time ledger)

These are biological metaphors because that's what the system has become: a living infrastructure that maintains itself, detects threats, and grows — with human judgment as the conscious mind directing growth rather than performing every action manually.

### Next step recommendation

**Claim BET-Y1Q3-T10-05 (compass_radar 集成新指标)** as the immediate next action. It connects the new tools (drift-sweep, KB staleness) to the primary health dashboard, which means every future gate run automatically surfaces knowledge staleness and drift findings alongside existing health signals.

This single integration makes everything else built in the last two weeks visible on every dashboard refresh.

---

*End of integration & forward plan.*
