---
schema_version: specification/v1
spec_version: 1.0.0
title: Vault daily health Workspace owner cutover
bet_id: BET-Y1Q3-T10-103
status: accepted
lifecycle: contract
owner: governance-team
created: 2026-08-30
last_updated: 2026-08-30
type: ssot
last_updated: 2026-09-03
---

# Vault daily health Workspace owner cutover

## Intent

Cut over the sole forbidden Documents executor proven by T10-102. The active
Claude Scheduled `vault-daily-health` skill still invokes the quarantined
`@学习进化/_control/l4-kernel.sh`; it must call the canonical Workspace
`learning-control-plane all` owner and write its heartbeat under Workspace
runtime state.

## Transaction contract

- Target exactly
  `/Users/xiamingxing/Documents/Claude/Scheduled/vault-daily-health/SKILL.md`.
- Before mutation, record source SHA-256, mode, byte count, and a byte-identical
  backup under
  `/Users/xiamingxing/Workspace/runtime/quarantine/documents-scheduled-vault-daily-health-20260830/`.
- Refuse source fingerprint drift, target collision, missing owner, or any
  second Scheduled file change.
- Replace only the legacy all-command block and the heartbeat command.
- Owner command is system-Python compatible, aggregate/read-only, JSON-output,
  and uses `/Users/xiamingxing/Workspace` as the current Workspace execution
  root because the installed `accepted-20260908` release predates this owner.
- Owner `status=attention` with exit 1 is truthful inspection output; it is not
  converted to success or hidden.
- Postflight requires consumer audit `forbidden_executors=0`, `unmatched=0`,
  source backup equality, and a rollback manifest.

## Non-goals

- No change to any other Claude Scheduled skill, cron, LaunchAgent, Documents
  content domain, owner implementation, cadence, or migration-family status.
- No accepted-release promotion, application restart, or claim that the next
  automatic 08:02 execution has occurred.
- No deletion of the old heartbeat file or quarantine backup.

## Acceptance

- Preflight backup and source fingerprint are complete and recoverable.
- The exact Workspace owner command runs and returns structured
  `writes_documents=false` evidence.
- The Scheduled skill contains no active Documents executor path and writes its
  heartbeat only to `$HOME/Workspace/runtime/heartbeats/vault-daily-health`.
- Fresh consumer audit returns `status=ok`, `forbidden_executors=0`, and
  `unmatched=0`.
- Diff proof shows no other Scheduled file changed; repo evidence, ledger lint,
  doc SSOT, GaC, PR checks, and mainline replay pass.

## Rollback

Recheck the backup hash and current postflight source hash, atomically restore
the backup to the recorded source path, then rerun consumer audit. Keep the
backup package and manifest after rollback.
