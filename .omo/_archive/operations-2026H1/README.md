---
lifecycle: entry
owner: auto-fix-loop
last_updated: 2026-08-24
title: Operations Index — Where to Start
type: doc
---

# Operations Index — Where to Start

> **Purpose**: one file, every operator-essential doc + tool pointer.
> **Last curated**: 2026-08-23 (after the 8-round cleanup session)
> **Audience**: human operators AND AI agents

## Onboarding (read these in order)

0. **5-minute quickstart for AI agents**: `.agents/skills/agent-quickstart/SKILL.md`
1. [`../PROJECT-COMPLETE-GUIDE.md`](../PROJECT-COMPLETE-GUIDE.md) — full project tour
2. [`../../CLAUDE.md`](../../CLAUDE.md) — session startup protocol for AI agents
3. [`../../AGENTS.md`](../../AGENTS.md) — workspace operating rules
4. Full onboarding (MCP/BOS/cockpit setup): `.agents/skills/agent-onboarding/SKILL.md`

## When health drops (diagnostic recipes)

Start here when `bin/compass_radar.py` reports health < 60:

1. `bin/gac/health-trend-chart.py` — see trend (last 30 days)
2. [`cleanup-rounds-2026-08-22.md`](cleanup-rounds-2026-08-22.md) — 8-round retrospective + **diagnostic order** table

## Standard operations (runbooks by symptom)

- [`runbook-agent-silent.md`](runbook-agent-silent.md) — agent dashboard silent
- [`runbook-ci-red.md`](runbook-ci-red.md) — CI gate red
- [`runbook-constraint-violation.md`](runbook-constraint-violation.md) — P79 violation
- [`runbook-p74-silent-workflow.md`](runbook-p74-silent-workflow.md) — P74 silent workflow (ADR-0130)
- [`runbook-reasoning-engine.md`](runbook-reasoning-engine.md) — reasoning engine issues
- [`runbook-scenario-failure.md`](runbook-scenario-failure.md) — scenario not firing
- [`runbook-state-freshness.md`](runbook-state-freshness.md) — state file stale > 24h

## Standard operations (other docs)

- [`agent-retirement-handoff-template.md`](agent-retirement-handoff-template.md) — when retiring a long-running agent
- [`AGORA-CI-OPS-NOTES.md`](AGORA-CI-OPS-NOTES.md) — agora CI specific notes
- [`bin-scripts-convergence-audit.md`](bin-scripts-convergence-audit.md) — `bin/` table-area management

## Tool reference (built across rounds 1-8)

| Symptom | Tool | What it does |
|---|---|---|
| P0 planned tasks > 0 | `bin/plan/sync-planned-to-done.py --apply` | Move stale candidates to archived/done |
| Health score trending | `bin/gac/health-trend-chart.py` | ASCII sparkline + delta + range |
| 24h observability burst | (deduped automatically since PR #1957) | no tool needed |
| State file stale | `make state-sync && uv run --project projects/omo omo state refresh && uv run --project projects/omo omo debt refresh --now <utc>` | Refresh 5 SSOT files |
| silent workflow | `bin/gac/check-silent-workflows.py --list-silent` | List silent workflows (ADR-0130 P74) |
| History JSONL too big | `bin/gac/rotate-history.py --apply` | Trim records older than 90d (default) |
| Concurrent drift topic in gate | re-run; if persistent, see cleanup-rounds.md | drift detection is soft-warning only |
| Stale lock / zombie run | `bin/agent-workflow.py prune-locks` then compliance | PRUNE stale locks, CLOSE zombie runs |
| Check baseline violation | `bin/gac/gac-validate.py --gate` | Find bin/ scripts added without baseline bump |
| Submodule pointer drift | `git submodule update --init --recursive` then `bin/gac/check-submodule-pointer-drift.py` | Sync + verify |

## Pre-push checklist

```bash
# 1. State and compliance are clean
make gac-local-gate                                    # PASS expected
uv run --with pyyaml python bin/agent-workflow.py compliance  # continue expected

# 2. Submodule pointers reachable
bash bin/ssot/sync-submodules-push.sh                  # no missing

# 3. Doc + lint
make doc-ssot-lint                                     # 0 findings expected
python3 bin/ssot/doc-link-check.py --json              # 0 broken_links expected

# 4. Quick health sanity
uv run --with pyyaml python bin/compass_radar.py | grep -E "health_score|governance_anomaly"
```

## Self-recovery (when gate is red)

When `make gac-local-gate` returns FAIL:
1. Read the first `[FAIL]` line — identifies which check
2. Run that check's tool directly with `--json` to see the actual failure
3. Common patterns:
   - `gac-validate` FAIL → baseline drift, bump `.omo/_truth/registry/governance-checks.yaml`
   - `bin-scripts-convergence-audit` FAIL → see bin-scripts-convergence-audit.md
   - `mof-capabilities-drift-check` FAIL → bump `.omo/_truth/registry/mof-capabilities.yaml`
   - `state-freshness-check` FAIL → run `make state-sync && omo state refresh && omo debt refresh --now <utc>`
   - `findings=concurrent-write-drift` → re-run; concurrent-agent likely wrote mid-run

## See also

- [`docs/operations/cleanup-rounds-2026-08-22.md`](cleanup-rounds-2026-08-22.md) — full retrospective
- [`docs/LOCAL-RUNTIME-STARTUP.md`](../LOCAL-RUNTIME-STARTUP.md) — service startup reference
- [`docs/FUNCTIONAL-CAPABILITY-MAP.md`](../FUNCTIONAL-CAPABILITY-MAP.md) — capability index
