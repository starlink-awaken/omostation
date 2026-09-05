---
name: agent-quickstart
description: "Minimal 5-minute quickstart for AI agents working in the omostation workspace. Covers: run a gate, claim a path, edit + test, submit a PR, and where to find docs. Use when you're a new agent session and need to know 'what do I actually do'. NOT for full onboarding (use agent-onboarding skill instead)."

last-reviewed: 2026-08-26
type: ssot
owner: governance-team
---

# Agent Quickstart — What Do I Actually Do?

> **Time to first productive action**: ~5 minutes.
> **Audience**: any AI agent (Claude Code, Codex, Cursor) starting a fresh session.

## The 3 Commands You Must Know

```bash
# 1. Check system health before doing anything
make omo-status

# 2. Run governance gate before committing
make gac-local-gate

# 3. Submit your work via worktree + PR
bash bin/gac/gac-worktree.sh claim <your-session-name>
# ... edit files ...
bash bin/gac/gac-worktree.sh submit <your-session-name>
```

## Workflow: Edit → Test → Submit

### Step 1 — Sanity check

```bash
make omo-status
uv run --with pyyaml python bin/compass_radar.py | grep -E "health_score|anomal"
```

If health is below 60, see `docs/operations/cleanup-rounds-2026-08-22.md` for diagnostic order.

### Step 2 — Claim a worktree

```bash
bash bin/gac/gac-worktree.sh claim my-session-$(date +%H%M)
cd ../ws-my-session-*
```

This creates an isolated worktree so concurrent agents don't collide.

### Step 3 — Make changes + test

Edit code. Then:

```bash
# Python tests (workspace root)
uv run --with pyyaml --with pytest python -m pytest tests/ -v

# Project-specific test (example: kairon)
cd projects/knowledge/kairon && make test-diff && cd -

# Doc-only change? Skip pytest, just lint:
make doc-ssot-lint
python3 bin/ssot/doc-link-check.py --json
```

### Step 4 — Governance gate

```bash
make gac-local-gate
```

Expected output: `GaC local gate: PASS (NN checks executed, ALL GREEN)`.

If FAIL, read the first `[FAIL]` line and fix that check. Common patterns:
- `gac-validate` FAIL → baseline drift; bump `.omo/_truth/registry/governance-checks.yaml`
- `state-freshness-check` FAIL → `make state-sync && uv run --project projects/omo omo state refresh`
- `p74-silent-workflows` FAIL → see `docs/operations/runbook-p74-silent-workflow.md`
- `concurrent-write-drift` topic → re-run (soft warning, not blocking)

### Step 5 — Commit + Submit

```bash
git add -A
git commit -m "feat(scope): what this does and why"

# Back to root workspace for submit
cd /Users/xiamingxing/Workspace
bash bin/gac/gac-worktree.sh submit my-session-HHMM
```

This pushes the branch and opens a PR automatically.

### Step 6 — Wait for CI, then merge

```bash
gh pr checks <PR-number> --watch
gh pr merge <PR-number> --merge
bash bin/gac/gac-worktree.sh release my-session-HHMM
```

## Where To Find Things

| Need | Go here |
|---|---|
| Full onboarding (MCP, BOS, cockpit setup) | `.agents/skills/agent-onboarding/SKILL.md` |
| When health drops | `docs/operations/README.md` + `cleanup-rounds-2026-08-22.md` |
| Runbook by symptom | `docs/operations/runbook-*.md` |
| Tool reference table | `docs/operations/README.md` § Tool reference |
| Architecture review | `docs/operations/ARCHITECTURAL-REVIEW-2026-08-24.md` |
| Operating rules | `AGENTS.md` (root), `<project>/AGENTS.md` (per-project) |
| Session startup protocol | `CLAUDE.md` |

## Common Gotchas

1. **Don't commit directly to main** — it's protected. Always use `gac-worktree.sh claim` first.
2. **Submodule pointers drift** — after merging, run `git submodule update --init --recursive` in the main workspace.
3. **Concurrent agents** — expect gate flake from `concurrent-write-drift`. Re-run if you see it.
4. **Baseline drift** — every new script added to `bin/` requires bumping `script_baseline` in `.omo/_truth/registry/governance-checks.yaml`.
5. **Doc updates are mandatory** — if you add a tool, add a row to `docs/operations/README.md` Tool Reference table.
