---
schema_version: specification/v1
spec_version: 1.0.0
status: accepted
lifecycle: contract
owner: human-principal
created: 2026-08-28
last-reviewed: 2026-08-28
bet_id: BET-Y1Q3-T10-46
risk_level: L2
human_gate: true
type: ssot
last_updated: 2026-09-03
---

# Installed owner release-root convergence

## Objective

Converge the release root of already-installed Workspace owner/preflight cron
entries to the clean `accepted-20260908` release. This removes mixed-version
runtime roots while preserving each entry's cadence, command, input roots,
output roots, and fail-closed semantics.

## Contract

- Only active cron lines whose executable is a known Workspace owner/preflight
  entry are in scope; the exact line set is captured during preflight.
- Only the `accepted-<date>` release token changes. Cadence, arguments, redirection,
  and all unrelated crontab bytes must remain identical.
- The target release must be clean and contain every referenced entrypoint.
- No Documents content, user configuration beyond the exact crontab lines,
  LaunchAgent, child repository, runtime data, or legacy family semantics change.
- This BET proves release-root convergence only. It does not complete T10-28
  through T10-34 semantic parity or historical cutover evidence.

## Done when

- Every preflight-listed owner/preflight line points to accepted-20260908.
- A complete before/after crontab backup proves only the listed lines changed.
- Help/smoke checks for every target entrypoint return structured results with
  truthful exit semantics.
- Rollback restores the exact preflight crontab snapshot.

## Verification

```bash
git -C ~/.local/share/omostation/accepted-20260908 status --short
crontab -l
python3 bin/gac/documents-domain-owner-job.py consumer-audit --help
```
