---
type: ssot
---

# Agent Quickstart — omostation

## Before You Start
1. Read `.omo/AGENTS.md` (5 min) — .omo state boundaries
2. Read `AGENTS.md` §1.1 RED LINE (2 min) — workflow mandate
3. Run `make agent-workflow-bootstrap` (10s) — verify environment

## Starting Work
1. `uv run --with pyyaml python bin/agent-workflow.py suggest --from-diff --profile <your-profile>`
2. `uv run --with pyyaml python bin/agent-workflow.py start <workflow-id> --profile <your-profile> --bet <BET-ID> --objective "<summary>"`
3. Record the `<run-id>` returned

## During Work
- Claim paths before editing: `bin/agent-workflow.py claim <run-id> --path <path>`
- Edit, test, verify: `bin/agent-workflow.py verify <run-id> --from-diff --execute`
- Check gate: `make gac-local-gate` (or `make ci-local-fast` for full suite)

## Finishing Work
1. `bin/agent-workflow.py closeout` (or `make agent-workflow-closeout RUN_ID=<run-id>`)
2. `git add -A && git commit -m "type(scope): description"`
3. `bash bin/gac/gac-worktree.sh submit <session>` (if in worktree)

## If Something Breaks
1. Health check: `uv run python3 bin/compass_radar.py`
2. Stale locks: `bin/gac/prune-locks`
3. Silent workflows: `bin/gac/check-silent-workflows.py --list-silent`
4. State freshness: `bin/gac/state-freshness-check.py`

## Key Rules
- Never commit secrets
- Never push directly to main (use worktree + PR)
- Never edit `.omo/state/*.yaml` directly (use `omo state sync`)
- Never run `git reset --hard` without 3 confirmations
- Always update related docs in the same PR
