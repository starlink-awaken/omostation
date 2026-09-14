---
schema_version: retrospective/v1
type: retro
title: BET-Y1Q4-T8-05 Closeout Retro — Cockpit Portfolio read-only view
bet_id: BET-Y1Q4-T8-05
status: archived
lifecycle: contract
owner: governance-agent
created: 2026-09-04
last-reviewed: 2026-09-04
---

# BET-Y1Q4-T8-05 Closeout Retro

> **TL;DR**: Child-first PASW delivery. Cockpit `portfolio` consumes only digest-bound `.omo/_control/portfolio-status.json`. Live status is `unavailable` / `missing_control_projection` (T1-08 broker gap). Child tip on root main is `e7d6f576` (includes #131 + dashboard follow-up); delivery SHA `fd884f36`.

## Deliverables
- Child PR: starlink-awaken/omostation-cockpit#131 (squash → `fd884f36`)
- Tag: `bet/BET-Y1Q4-T8-05-20260904T115742Z`
- Files: `commands/portfolio.py`, `tests/test_portfolio_command.py`, `_subcommands.py`, `INTERFACE.yaml`
- Root: `projects/cockpit` gitlink bump + this retro + ledger done

## Q1
Appetite 3 days; delivered same-day after principal Wave auth / T1-08 merge.

## Q2
- status/objectives/critical-path/blockers share one loader: PASS (7 tests)
- missing → unavailable, no Ledger fallback: PASS (live smoke + tests)
- child PR/CI/main/tag then root pointer + reachability `--require-main`: PASS

## Q3
1. `projects/cockpit` ≠ `.subtrees/cockpit` (different inodes); child commits must land in PASW worktree.
2. Control projection still missing broker — Cockpit correctly stays unavailable; do not invent fallback from Markdown/Ledger.
3. Cockpit `uv run` fails on missing kairon path dep in some checkouts; verify via `PYTHONPATH=src pytest`.

## Q4
Child +287 LOC / +2 files; root gitlink only (+ retro/ledger). GaC/ADR/script baseline 0.

## Q5
Next (T1-09): dogfood canary must treat Cockpit unavailable as typed fail until broker lands, or assert unavailable envelope explicitly. Do not write Ledger/Goals/OMO from Cockpit.
