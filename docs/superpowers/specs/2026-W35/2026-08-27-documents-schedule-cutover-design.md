---
schema_version: specification/v1
spec_version: 1.0.0
status: accepted
lifecycle: contract
owner: human-principal
created: 2026-08-27
last-reviewed: 2026-08-27
bet_id: BET-Y1Q3-T10-26
risk_level: L2
type: ssot
last_updated: 2026-09-03
---

# Documents schedule cutover

## Exact scope

On the current macOS user crontab, replace exactly these two active entries:

1. daily `25 6`: Documents `@公共/_runtime/async-audit.py` → Workspace
   `documents-domain-owner-job consumer-audit`;
2. Monday `35 6`: Documents `@公共/_runtime/control-plane-freshness-audit.py
   --report` → Workspace `documents-domain-owner-job freshness-audit`.

No other crontab line, LaunchAgent, Scheduled skill, Documents file, or user
content is changed. The candidate schedule is the source of the replacement
commands.

## Safety contract

- Before mutation, capture the complete `crontab -l` output and SHA-256 under the
  run's Workspace evidence directory.
- Abort if either old entry is absent, duplicated, or the candidate command is
  already present; do not guess around drift.
- Construct the new crontab from the backup by exact line replacement, then pass
  it to `crontab` once. Preserve every unrelated byte/line.
- Immediately verify old count=0, new count=1 for each job and compare unrelated
  lines byte-for-byte.
- Run both owner commands manually after cutover. `freshness-audit` may return
  exit 1 for its known missing metadata findings; that is truthful evidence, not
  a reason to revert. Revert only on route/write/command errors.
- Rollback is `crontab <backup-file>` after verifying the backup SHA-256.

## Observation boundary

This BET changes only two schedules. The remaining Documents execution families
stay active until their owner parity, consumer scan, and rollback evidence pass.
No Documents physical migration or deletion occurs here.
