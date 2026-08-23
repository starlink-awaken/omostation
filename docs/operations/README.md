# Operations Index — Where to Start

> **Purpose**: one file, every operator-essential doc.
> **Last curated**: 2026-08-23 (after the 5-round cleanup session)

## Onboarding (read these in order)

1. [`../PROJECT-COMPLETE-GUIDE.md`](../PROJECT-COMPLETE-GUIDE.md) — full project tour
2. [`../../CLAUDE.md`](../../CLAUDE.md) — session startup protocol for AI agents
3. [`../../AGENTS.md`](../../AGENTS.md) — workspace operating rules

## When health drops (diagnostic recipes)

- [`cleanup-rounds-2026-08-22.md`](cleanup-rounds-2026-08-22.md) — the 5-round cleanup retrospective + **diagnostic order** table for when health < 60

## Standard operations

- [`agent-retirement-handoff-template.md`](agent-retirement-handoff-template.md) — when retiring a long-running agent
- [`AGORA-CI-OPS-NOTES.md`](AGORA-CI-OPS-NOTES.md) — agora CI specific notes
- [`bin-scripts-convergence-audit.md`](bin-scripts-convergence-audit.md) — `bin/` table-area management

## Round-trip safety

When state-freshness drops or observability events pile up, the
diagnostic order in `cleanup-rounds-2026-08-22.md` will identify
the right tool in <30 seconds.

When you're done writing and before pushing, run:
```bash
make gac-local-gate && uv run --with pyyaml python bin/agent-workflow.py compliance
```
Both should report `PASS` and `continue`. If not, **don't push** — fix
the warning first.
