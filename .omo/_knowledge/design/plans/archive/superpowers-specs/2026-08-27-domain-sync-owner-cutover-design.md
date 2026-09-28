---
schema: md/v1
status: accepted
lifecycle: contract
owner: human-principal
type: ssot
last-reviewed: 2026-08-27
created: 2026-08-27
last_updated: 2026-09-03
bet_id: BET-Y1Q3-T10-28
---
# Domain sync owner cutover

## Exact scope

Replace only the active daily 06:00 crontab entry that invokes
`$HOME/Documents/@公共/_runtime/domain-sync.py`. Use the accepted Workspace
release's `documents-domain-index.py check` with the same Documents registry and
DOMAIN-INDEX projection as read-only inputs.

## Contract

- Capture and hash the complete current crontab before mutation.
- Require the old line exactly once and the candidate line zero times.
- Preserve all unrelated lines byte-for-byte.
- New execution uses `uv`/Python 3.13 from the accepted release; the legacy
  `/usr/bin/python3` path is known to fail on Python 3.9 (`dataclass(slots=True)`).
- `check` is read-only and may return 1 for projection drift; no Documents file
  is written by this BET.
- Rollback restores the verified pre-cutover crontab snapshot.
