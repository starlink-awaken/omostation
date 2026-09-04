---
schema_version: specification/v1
spec_version: 1.0.0
status: accepted
lifecycle: contract
owner: human-principal
created: 2026-08-28
last_updated: 2026-08-27
bet_id: BET-Y1Q3-T10-30
risk_level: L2
type: ssot
last_updated: 2026-09-03
---

# OCR preflight schedule cutover

## Exact scope

Replace exactly the one active `0 10 1,16 * *` crontab entry invoking
`/Users/xiamingxing/Documents/@工作文档/卫健委/_runtime/cron/ocr-incremental.sh`
with the accepted-20260828 Workspace `ocr-preflight` command from the canonical
candidate schedule.

## Safety contract

- Backup and hash the complete crontab before mutation.
- Require old count=1 and new count=0; abort on drift.
- Preserve all unrelated lines byte-for-byte.
- The new command only checks the missing OCR source and engine readiness; it does
  not execute OCR or write Documents.
- Keep the legacy runner and its source data intact for later OCR parity work.
- Rollback restores the verified pre-cutover crontab backup.
