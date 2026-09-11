---
schema: bet-retro/v1
bet_id: BET-Y1Q4-T16
status: completed
lifecycle: history
owner: governance-team
last-reviewed: 2026-09-11
type: ephemeral
---

# BET-Y1Q4-T16 retrospective — ops registry drift guard

## Q1. What was intended?

Deliver the two gates defined by the accepted specification:

- `bin/ops/cli.py check-signals` detects drift between enabled service declarations
  and their cron, launchd, or file anchors.
- `bin/mof/gen-service-configs.py --validate` rejects invalid enabled cron
  declarations while grandfathering disabled legacy placeholders.

The delivery also needed regression coverage for the `omo` versus `omostation`
token-boundary false positive and placeholder cron entrypoint cases.

## Q2. What happened?

The implementation was delivered in the original T16 change and then converged
through two follow-up fixes:

- PR #3558 added the drift detector, cron admission rule, and registry entry.
- PR #3568 removed a duplicate `check-signals` parser and command definition
  that caused startup to fail with a conflicting subparser error.
- PR #3570 removed the duplicate `cron.ops_signal_drift_check` registry
  declaration, preserving the canonical `python3` entry with the
  `ops-signal-drift` token.

PR #3570 was squash-merged to `origin/main` as
`cbf5eb98918d2c920d616ed04fd3c9161e153209`. The merged main tree contains one
`check-signals` parser/handler pair and one signal-drift service declaration.

## Q3. What changed during implementation?

- The CLI now has one registered `check-signals` subcommand and one handler.
- The service registry has one canonical `cron.ops_signal_drift_check` entry.
- The canonical service uses `python3`, the `bin/ops/cli.py` entrypoint, and the
  `ops-signal-drift` crontab token.
- The accepted specification and its digest binding were preserved.
- No runtime data migration or scheduler mutation was performed.

## Q4. Lessons and evidence

### Verification evidence

The final merged worktree produced:

```text
OMOSTATION_ROOT=<t16-worktree> python3 bin/mof/gen-service-configs.py --validate
-> {"ok": true, "violation_count": 0, "violations": []}

OMOSTATION_ROOT=<t16-worktree> python3 bin/ops/cli.py check-signals --json
-> {"checked": 26, "drifts": [], "drift_count": 0, "crontab_error": null}
```

The PR #3570 governance run completed successfully, including the full
governance verification, GaC local gate, document governance, interface check,
and submodule pointer drift check. The PR had 22 passing checks, no failures,
and only documented skips.

### Known unrelated blocker

The workspace-level `ssot-guardian` check in the active workflow still reports
pre-existing dirty submodule pointers for `projects/aetherforge`,
`projects/ecos`, `projects/l4-kernel`, and `projects/omo`. Those pointers were
not changed by T16 and were intentionally not reverted or included in this
delivery. The authoritative PR checks passed on the merged commit; this local
workspace drift remains an environment-level closeout note rather than a T16
acceptance failure.

### Lessons

- A registry change can pass a normal loader while still containing duplicate
  entries across the full YAML document; uniqueness checks must parse all
  documents and inspect the complete service list.
- A command registration must be exercised at process startup, not only through
  static or focused function tests.
- Squash merge reachability should be recorded using the actual merge commit,
  while preserving the original implementation commits in the PR history.

### Rollback

Rollback is a content-only revert of PR #3570 followed, if required, by a
revert of PR #3568. No database, ledger, or scheduler state migration is
required.
