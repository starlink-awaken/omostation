---
schema: md/v1
status: accepted
lifecycle: contract
owner: governance-team
last-reviewed: 2026-09-25
type: ssot
schema_version: specification/v1
spec_version: 1.0.0
title: A4 remote-hygiene cron registry parity recovery
bet_id: BET-Y1Q4-T16-02
created: '2026-09-14'
implementation_authorized: true
value_indicator_policy: false
risk_level: L1
human_gate: false
---


# A4 remote-hygiene cron registry parity recovery

## Problem

PR #3752 installed an hourly `fix-remotes.py` remote-hygiene job in the user
crontab and recorded it in `crontab.new`. PR #3754 corrected the script name
but neither PR registered the job in `.omo/cron/registry.yaml`. As a result
`scheduler-compile.py --check` reports `drift_count=0, orphan_count=1`, and A4
remains red even though the installed job is intentional and its command is
already correct.

This is a declaration-plane parity gap. It must not be hidden through the
registry's known-orphan mechanism.

## Scope

- Register the existing installed job in `.omo/cron/registry.yaml` as an active
  crontab job with owner, SFOP slot, reality, exact command, and reconciliation
  provenance.
- Preserve the installed schedule, command, logs, and runtime behavior exactly.
- Add the bounded child BET and honest initial completion matrix.
- Record the one-time unbound bootstrap waiver and retrospective in the
  governance-state successor lane.

## Non-goals

- Do not change `fix-remotes.py`, scheduler compiler semantics, launchd, CI, or
  installed cron state.
- Do not add the job to `known_orphans`.
- Do not claim A6/A7/A8/A9 admission or any value proof.

## Acceptance

- `python3 bin/scheduler-compile.py --check` exits 0 with
  `drift_count=0` and `orphan_count=0`.
- `python3 bin/plan/bet-ledger.py lint` exits 0.
- The docs bootstrap lane contains only the accepted specification and Ledger
  entry; the registry, waiver, and retro are delivered in the subsequent
  governance-state lane.
- The governance-state PR contains only the claimed registry, waiver, and retro
  paths, and leaves no runtime behavior change.

## Rollback

Revert the registry declaration and governance evidence. No runtime rollback is
required because the installed cron job and command are unchanged.
