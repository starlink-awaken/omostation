---
schema_version: specification/v1
spec_version: 1.0.0
status: accepted
lifecycle: contract
owner: human-principal
created: 2026-08-28
last-reviewed: 2026-08-28
bet_id: BET-Y1Q3-T10-45
risk_level: L1
human_gate: true
type: ssot
last_updated: 2026-09-03
---

# Domain-index owner release-root reconciliation

## Objective

Update the already-installed daily domain-index owner schedule from the stale
`accepted-20260827` release to the clean accepted release
`accepted-20260908`. This is a release-root reconciliation only; it does not
claim the original Documents `domain-sync.py` migration as complete.

## Contract

- Change exactly the active `0 6 * * *` domain-index owner line in the current
  user crontab.
- Target release is the clean detached
  `~/.local/share/omostation/accepted-20260908` root.
- Preserve cadence, command semantics, Documents read-only boundary, and every
  unrelated crontab byte.
- Capture a complete before/after crontab snapshot and rollback command before
  installation.
- Do not modify Documents content, the domain index, other schedules, launchd,
  or any child repository.

## Done when

- Exactly one stale `0 6` owner line is replaced with the accepted-20260908
  owner line.
- No unrelated crontab line changes and the new command passes a direct smoke.
- The release provenance and rollback snapshot are recorded.
- The original T10-28 Documents-to-Workspace migration remains separately
  tracked and is not marked complete by this BET.

## Verification

```bash
git -C ~/.local/share/omostation/accepted-20260908 status --short
python3 ~/.local/share/omostation/accepted-20260908/bin/gac/documents-domain-index.py --help
python3 ~/.local/share/omostation/accepted-20260908/bin/gac/documents-domain-index.py check ...
```
