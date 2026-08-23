# Architecture & Strategic Review — 8 Rounds of Cleanup, 11 PRs

> **Author**: deep analysis session, 2026-08-24
> **Audience**: founders, operators, future agents
> **Time window**: 2026-08-22 → 2026-08-24 (~72 hours of cleanup + concurrent work)
> **Scope**: project-grain (eCOS v6 multi-project monorepo)

---

## 0. North-star anchor

> **Purpose of omostation** (verbatim from `CLAUDE.md`):
> *multi-project workspace for knowledge engineering, agent governance, BOS service routing, runtime orchestration, and personal/work knowledge operations.*

**Working hypothesis**: it is a **personal cognitive infrastructure** — an "operating system" for one person's knowledge, agent-managed workflows, and BOS service mesh. This is *not* a SaaS product or a team-scale dev platform; it's a **single-owner system that wants to outlive its owner without losing trust**.

That single sentence explains every architectural decision that follows. If you read this review and disagree with something, check your assumption against that sentence before disagreeing with the design.

---

## 1. Scenario map

The system must support **5 distinct operating scenarios**, ordered by frequency:

| # | Scenario | Frequency | Entry point | Latency budget |
|---|---|---|---|---|
| S1 | Operator opens terminal, runs `make omo-status`, reads system | **daily** | CLI | < 1s |
| S2 | Radar/health probe runs, gates execute, dashboards refresh | **hourly** | cron + CI | < 30s |
| S3 | Agent edits source under P74 workflow, claims path, commits | **per-task** | agent-workflow.py | seconds |
| S4 | Multi-agent contention: two agents push to same worktree | **several/day** | shared main | gate-time |
| S5 | User wants to onboard a new capability (e.g. add a script) | **weekly** | PR | minutes |

**The 8 rounds all addressed failures observed in S1, S2, S4.** S3 and S5 were not broken; they worked because agents and humans were disciplined enough to clean up after themselves.

That asymmetry is the project's real strategic risk. **S3 (workflow discipline) currently depends on the operator being attentive. The cleanup work has reduced the surface where attention is required, but the underlying mechanism is still social, not mechanical.**

---

## 2. Functional inventory

After 8 rounds, the system exposes ~440 scripts in `bin/`. The functional categories:

### 2.1 Governance & audit (~30% of bin/)
- `gac-local-gate.py` — the master checker, 46+ individual checks
- `gac-validate.py` — subtraction-quota (bin script count)
- `state-freshness-check.py` — 5-file contract verifier
- `check-silent-workflows.py` — P74 detector
- `check-silent-loss.py` — companion
- `concurrent-write-drift` — soft topic in gate output
- `governance-evolution.py` — meta-doctor self-healing
- `anti-corruption.py` — CI surface enforcement
- `mof-capabilities-drift-check.py` — capability count parity
- `bin-scripts-convergence-audit.py` — dedup detector

**Pattern**: every check is **a script that returns 0/1** plus emits JSON on `--json`. This uniformity is the project's hidden asset — it makes all checks composable into `gac-local-gate`.

### 2.2 State & observability (~15%)
- `compass_radar.py` — master radar, writes health.yaml + history.jsonl
- `health-trend-chart.py` — ASCII sparkline consumer of history
- `rotate-history.py` — 90-day retention for history.jsonl
- `system-health-check.py` — resident system probe
- `evidence-smoke.py` — bus fallback liveness

**Pattern**: a small number of writers, many readers. The writers are gated by `omo state sync` broker (in theory) and `bin/compass_radar.py` (in practice); readers are free to consume.

### 2.3 Workflow & agent lifecycle (~15%)
- `agent-workflow.py` — the executable runner (start/claim/verify/closeout)
- `prune-locks` — heartbeat-TTL cleanup
- `check-silent-workflows.py` — P74 detection
- `closeout --status blocked` — zombie-run disposal
- `promote_agent_to_role` — role assignment

### 2.4 Migration & cleanup (~20%)
- `sync-planned-to-done.py` — auto-archive stale candidates
- `rotate-history.py` — JSONL trim
- `bin-scripts-convergence-audit.py` — dedup
- `submodule-pointer-transaction.sh` — pointer sync
- `start-cockpit-dashboard.sh` — launchd-style start

### 2.5 Knowledge tools (~20%)
- `adr/adr-trend-insight.py` — ADR analysis
- `compass_radar.py` — also produces knowledge signals
- `meta-doctor.py` — self-watcher
- `health-trend-chart.py` — visualization

**Observation**: there is no central registry of "what does script X do". The retrospective doc + runbooks + ops README are the closest things. **Strategic risk**: as scripts grow (440 now, was 420 at start), discoverability degrades.

---

## 3. User journey

### 3.1 Operator daily journey (S1)

```
T+0s:    open terminal
T+0.5s:  make omo-status          → 6 agents status, lock count, BET count
T+2s:    uv run bin/compass_radar.py  → health 70, anomaly 0/100, freshness 100
T+3s:    read summary in 3 lines: health / anomaly / service-online
T+10s:   if anomaly > 0:
            check p74_silent-workflows topic
            or check stale tasks via bin/plan/sync-planned-to-done
T+30s:   start work
```

**Assessment**: this journey is now well-served by `compass_radar.py` + the trend chart. Before rounds 1-8, step T+2s would show `health_score 28/100` with no actionable signal; now it shows 70/100 with `governance_anomaly_score: 0/100` and a clean sparkline.

### 3.2 Agent working journey (S3)

```
claim path via bin/agent-workflow.py claim <run-id> --path projects/...
edit + test
bin/agent-workflow.py verify --from-diff --execute
bin/agent-workflow.py closeout
git add + commit
bin/gac/gac-worktree.sh submit
```

**Assessment**: this journey is **mechanically well-supported but socially fragile**. The crash risk is not "the script fails" — it's "the agent forgets step 4" or "the agent commits outside a run". The cleanup rounds did not address this; the existing `AGENTS.md` does. **Strategic risk**: if a future agent can't read AGENTS.md or skips it, the entire system has no enforcement.

### 3.3 Multi-agent contention (S4)

```
T+0s:    Agent A starts gate run, snapshots fingerprint
T+10s:   Agent B writes to .omo/state/health.yaml  
T+15s:   Agent A's gate finishes, detects drift
T+15.1s: emits soft topic `concurrent-write-drift`
         gate still PASSES (warn only)
```

**Assessment**: PR #1989 fixed the **observability** of contention but not the contention itself. Drift is detected after-the-fact, not prevented. **Strategic decision deferred**: per retrospective's "did NOT do" list, the broker-enforcement ADR is intentionally pending.

The right time to revisit this is when **two or more concurrent writes cause a real merge conflict**, not before. The current state is "visible, not blocked" which is the correct pre-conflict stance.

---

## 4. Experience layer

### 4.1 What works

- **`make health-trend`** — terminal-native, no browser required. Operators on a slow link or in a tmux session get immediate signal. **Critical for S1**.
- **`runbook-X.md` frontmatter** — every runbook has `status: active`/`type: runbook`/`owner: governance-team`/`last-reviewed: YYYY-MM-DD`. The pattern is consistent across all 7 runbooks; linter (`doc-ssot-lint`) accepts them. **Easy to add new ones** (runbook-state-freshness.md was added in 30 min this session).
- **Self-recovery checklist in retrospective doc** — when health drops below 60, an operator has a literal table to follow. This is the **single highest-leverage documentation artifact** in the project.

### 4.2 What's missing

- **No "what does this PR do" template for agents** — the project has `commit_message_quality` for humans (per system prompt rules), but no analogous pre-PR checklist for agents. When an agent submits a 3-file change, there's no automated sanity check that the change has tests, a doc, and a baseline bump.
- **No "this is broken, here's who owns it" view** — when a check fails, the operator gets a stack trace but not "this is owned by team Y, expected behavior is Z". **Recommended fix**: each check in `governance-checks.yaml` could have an `owner:` and `expected:` field.
- **No "what changed since last session" view** — `make omo-status` shows current state; `git log --since="2 days ago"` shows code changes; but there's no merge of those two. Operators returning after a weekend don't know what broke since they left.
- **Cockpit Web UI is offline by default** — `cockpit status` works in CLI but `cockpit dashboard` (port 8090) requires manual `nohup`. Per retrospective "did NOT do" list, this is intentional ("documented, not implemented"). The downside: non-CLI users have no entry point.

### 4.3 UX friction I personally hit

- **`gac-worktree.sh claim <name>` sometimes blocks for 60s** on cold submodule init. The user sees a 60-second pause with no progress indicator. **Fix candidate**: tail `-f` on the submodule init log.
- **`compass_radar.py` output is dense** — 30+ lines of structured info. Good for grep, bad for glance. A `--summary` flag with one-line output would help.
- **P74 silent-workflow detection has no dashboard** — it surfaces in gate output, but there's no "show me all currently-silent workflows" view that's less noisy than a full gate run.

---

## 5. Goal / vision alignment

### 5.1 Is the project aligned with its stated goal?

**Stated goal** (inferred from architecture docs): *"single owner's cognitive infrastructure that outlives the owner."*

| Dimension | Aligned? | Evidence |
|---|---|---|
| Trust persistence (audit trail) | ✅ | `governance-history.jsonl` (2064 records), events.jsonl, all artifacts immutable |
| Agent independence (can be re-instantiated) | ✅ | 16/16 workflows active, agent-workflow.py is the entry point |
| Mechanical enforcement (not just docs) | ✅ | 49 gate checks, 4 of them blocking |
| Drift detection (not prevention) | ✅ | drift detector, dedup, snapshot comparison |
| Owner bottleneck | ⚠️ | 67% tasks owned by `human` — **the goal is undermined by the current state** |
| Velocity (time-to-add-a-capability) | ⚠️ | ~5–15 min for a script, ~30 min for a gate, ~1 day for a new layer |

### 5.2 The 67% owner concentration is the biggest strategic threat

Look at the L3-task + owner-concentration anomalies. The system is **structurally healthy but operationally bottlenecked** on a single human. This is the inverse of the goal.

**Concrete consequence**: any feature that requires the human's judgment blocks. The 2 human-owned L3 BETs (`bet-y3h1-t7-01`, `bet-y3h2-t7-01`) are blocked on external events (用户借调国转中心, 政策申报). The system cannot unblock them; only the human can.

**The cleanup rounds did not address this.** They made the system more observable but did not redistribute the load. That is correct (the L3 tasks genuinely need the human), but it should be acknowledged: **the system's bottleneck is now explicitly visible as a stat**.

### 5.3 Implicit goal: zero-friction self-extension

Reading the 5 rounds of optimization as a whole, an implicit goal emerges: **the system should be self-extensible without the operator's attention**. Each round added something the operator would otherwise have to remember to do:

- Round 2: auto-archive stale tasks (operator no longer needs to)
- Round 3: auto-mirror debt dashboard (operator no longer needs to)
- Round 4: auto-dedup observability events (operator no longer needs to)
- Round 5: auto-detect silent workflows (operator no longer needs to)
- Round 6: auto-detect concurrent drift (operator no longer needs to)
- Round 7: auto-collect trend + auto-launch cockpit (operator no longer needs to)
- Round 8: auto-trim history + auto-bump baseline (operator doesn't need to track num scripts)

This is **the actual philosophy of the project**: encode human memory as machine checks. The next round of work (9+) should continue this pattern.

---

## 6. Long-term operations

### 6.1 Operational metrics now

| Metric | Value | Trend |
|---|---|---|
| Health score | 70/100 | stable since round 5 |
| governance_anomaly_score | 0–17/100 | varies with obs events |
| service_online_ratio | 100% | stable |
| Active runs | 0 | healthy |
| Stale locks | 0 | healthy |
| History records | 15 (in 1 day) | low — radar runs infrequently |
| Worktrees | 6 active | normal concurrent activity |
| PRs merged | 11 (this session) | high |
| Bin scripts | 440 | growing ~10/session |
| Concurrent agents | 4–6 | high but normal |

### 6.2 What 30 days from now will look like

**Without intervention**:
- Bin scripts will reach ~470 (continuing +10/session)
- Worktree count will stay at 6-8 (sessions open and close)
- Health will stay at 65-75 (real signal: 4 L3 blocked tasks)
- Stale stashes will grow back to 55+ (concurrent agents accumulate)

**With monthly cleanup** (matching current rhythm):
- Bin scripts stay manageable
- Gates catch regressions early
- Health stays in the 70s

**With quarterly review**:
- Drift compounds; one-off work accumulates
- Eventually a 2-day cleanup session is needed

**Strategic decision**: the project needs either **scheduled monthly maintenance** OR a **self-healing mechanism**. The current silent-workflow detection is one form of self-healing (for workflows); it does not exist for other artifact types (skills, runbooks, governance-checks rules).

### 6.3 Sub-project health

I cannot directly assess sub-project health from the root workspace. The bin scripts touch them, but the actual sub-project state (commits, tests, branches) is opaque. **Recommendation**: add a `bin/meta/sub-project-health.py` that aggregates status from each submodule's `make test-diff` or similar.

---

## 7. Anti-corruption (防腐)

### 7.1 What the cleanup rounds actively protected against

- **Drift between code and SSOT** — the `governance-history.jsonl` shows when SSOT was last updated vs when code referenced it. Drift = bug.
- **Schema drift** — `mof-capabilities.yaml` declares 1402 nodes; the actual count is 1402. If someone added 1 node in ecos without bumping the registry, the next drift check would catch it.
- **L0 constraint violations** — `check-l0-constraints.py` validates that L0 protocol doesn't leak upward. If someone violates L0, gate fails.
- **P79 write contention** — drift detector catches torn reads (soft, not hard).

### 7.2 What is NOT yet protected

- **Knowledge rot** — ADRs get stale. There's no "this ADR references a path that no longer exists" check.
- **Skill rot** — `.agents/skills/` exists but I don't know if there's a check that ensures each SKILL.md is still functional.
- **Runbook rot** — runbooks are written once and never re-verified against current tools. If `bin/gac/check-silent-workflows.py` is renamed, runbook-p74-silent-workflow.md becomes stale.
- **Doc-code drift** — `doc-link-check.py` checks links but not that commands in runbooks still exist as described.

### 7.3 Anti-corruption as a continuous function

The current model: **anti-corruption runs as a gate (PR-blocking)**. This catches regressions before they merge.

The missing model: **anti-corruption runs as a scheduled sweep (weekly)**. This catches regressions that escape gates (e.g. via direct push to main, which is now blocked but historically was allowed).

**Recommendation**: add `bin/gac/drift-sweep.py` that runs all drift checks + runbook validity + ADR link validity + emits a weekly report.

---

## 8. Constraints

### 8.1 Hard constraints (architectural)

- **Single worktree = main, all agents share** — every agent must work on `main` (or a worktree but merge back to `main`). This is a deliberate constraint.
- **Single-owner model** — only one human, multiple agents. Reverse the model is unsupported.
- **Submodules = independent repos** — each `projects/*` has its own commits, releases, tests. The root can't dictate submodule internals.
- **macOS-first** — `~/Library/LaunchAgents/` paths, `lsof`, `pkill` are macOS-specific.
- **Python 3.13** — pinned by `projects/omo/pyproject.toml` and others.

### 8.2 Soft constraints (cultural)

- **No global rewrites** — refactors are scoped to a single PR, not a "rewrite-everything" campaign.
- **Bots are agents, not code** — agents live in `.agents/`, capabilities live in `bin/`. Never the other way.
- **Drift is visible, not silenced** — soft topics instead of hard fails. The system tells the operator "this happened" rather than blocking.
- **Doc updates are PR-time** — the doc-update-lint enforces this.

### 8.3 Tension points

- **Cleanliness vs velocity** — every round added ~5 min of cleanup per session. At some point, the maintenance cost exceeds the benefit.
- **Mechanical vs social enforcement** — P79 drift detection is mechanical. The "agent must claim a path before editing" rule is social.
- **Single-worktree vs single-submodule** — when one submodule is "ahead" (e.g. concurrent agent bumps it), the root sees drift but doesn't block. This is intentional but surprising.

---

## 9. Strategic recommendations (10)

### 9.1 Priorities (now → next quarter)

1. **🔴 HIGH — Drift sweep tool** (`bin/gac/drift-sweep.py`). One-shot run of all drift checks + runbook validity + ADR link validity. Catches the "soft" rot before it compounds.

2. **🔴 HIGH — Health auto-remediation** for L3 anomalies. The L3 high-risk tasks with `evidence_required` should be detected as drift and surfaced with the exact remediation command.

3. **🟡 MEDIUM — Runbook validity CI check**. Before each merge, verify that every `bin/X` referenced in any runbook still exists.

4. **🟡 MEDIUM — Cockpit dashboard auto-start**. The launchd plist already exists (~/Library/LaunchAgents/com.cockpit.dashboard.plist). But the command in the plist is outdated (`cockpit.dashboard_server` instead of `cockpit-dashboard`). Fix and reload.

5. **🟡 MEDIUM — Skill registry verification**. List all `SKILL.md` files under `.agents/skills/`, verify each has a corresponding `bin/` entry or external doc, alert on orphans.

6. **🟢 LOW — Sub-project health aggregator**. Single command that runs each submodule's `make test-diff` or equivalent, reports pass/fail counts.

7. **🟢 LOW — Knowledge indexing** (`bin/kb/index.md`). The retrospective mentions a "future dashboard". Building that needs a knowledge graph index of bin/, docs/, .agents/.

8. **🟢 LOW — ADR link validity check**. ADRs reference file paths. If those paths change, the ADR is silently broken.

9. **🟢 LOW — Scheduled cleanup cron**. A monthly `bin/gac/maintenance.py` that runs drift checks + bin-scripts-convergence + ADR validity + runbook validity + emits a report. Not a gate, just a report.

10. **🟢 LOW — Agent-experience layer**. Add a `.agents/skills/quickstart/SKILL.md` for new agents that summarizes: how to start a run, how to claim a path, how to close out, where to find docs. Currently the agent has to read CLAUDE.md + AGENTS.md + retrospective. A 1-page quickstart is missing.

### 9.2 Anti-patterns to avoid

- **Adding more gates without reading existing ones** — every new gate is a tax on every PR. The current 49-check gate is already 30-60s. Diminishing returns are real.
- **Auto-fix scripts without audit log** — if `bin/gac/auto-fix-X.py` mutates state, the mutation must be in events.jsonl so it's reversible.
- **Adding more agents without checking concurrency** — every concurrent agent increases the rate of contention. The 67% owner concentration problem is partly *because* there are too many agents.

### 9.3 What NOT to do (intentional non-goals)

- **Don't build a central dashboard** — it's in the retrospective as "did NOT do" for good reason. Cockpit is the right entry.
- **Don't write a "best practices" doc** — the retrospective + runbooks are the practice. Another doc adds noise.
- **Don't optimize L3 task routing** — the L3 tasks are correctly routed to the human. Optimizing would mean automating judgment calls that shouldn't be automated.
- **Don't make the drift detector blocking** — it's correct that it's soft. Hard-blocking would cause false-positive flakes from concurrent agents.

---

## 10. Summary scorecard

| Dimension | Score | Notes |
|---|---|---|
| Structural health | **8/10** | All gates pass, drift detected, history retained |
| Operational health | **7/10** | 67% human bottleneck is the weak point |
| Documentation | **8/10** | 7 runbooks + ops README + retrospective + AGENTS.md |
| Discoverability | **6/10** | 440 scripts without central registry |
| Anti-corruption | **7/10** | Gates catch most drift; runbook/code drift not guarded |
| User experience | **7/10** | CLI is excellent; cockpit UI offline by default |
| Goal alignment | **9/10** | Single-owner cognitive infrastructure preserved mechanically |
| **Overall** | **7.4 / 10** | Strong foundation, clear improvement path |

---

## 11. Final note

**The cleanup rounds transformed the project from "structurally healthy but operationally fragile" to "structurally healthy and operationally observable."**

The next phase (drift sweep, health auto-remediation, runbook validity, cockpit auto-start) is incremental, not transformative. Each adds one specific failure mode to the detected set.

The largest **strategic** gap is the human bottleneck. It cannot be solved by automation (the L3 decisions need a human). It can only be solved by **reducing the number of L3 decisions needed**, which means: do fewer L3 things.

The current trajectory is healthy. Continue at the current pace.

— End of analysis —
