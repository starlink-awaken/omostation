---
schema_version: report/v1
status: active
lifecycle: history
type: implementation-evidence
owner: governance-team
created: 2026-08-27
last-reviewed: 2026-08-27
bet_id: BET-Y1Q3-T10-41
---

# Documents execution retirement — implementation evidence

## Current implementation

- `lib/documents_daily_health_preflight.py` reads the Weijian knowledge,
  inbox, manifest, and signals inputs without invoking Documents scripts or
  writing Documents files.
- `lib/documents_kos_preflight.py` reports the canonical Workspace KOS wrapper,
  source-domain readiness, the missing legacy `/usr/local/bin/kos` entry, and
  both log targets without invoking ingest.
- `bin/gac/documents-domain-owner-job.py` exposes both preflight commands as
  Workspace owner entrypoints.

## Evidence

- Focused tests: `4 passed`.
- Ruff and Python compile checks: pass.
- Daily live smoke: `documents.daily-health-preflight.v1`, status `findings`,
  exit `1`; summary `stale_knowledge=679`, `stale_inbox=4`,
  `pending_inbox=0`, `signals=0`.
- KOS live smoke: `documents.kos-preflight.v1`, status `findings`, exit `1`;
  Workspace executable `ready`, eight source domains present, legacy executable
  `missing`, and `writes_documents=false`.
- KOS dry-run against `@工作文档` completed with exit `0`, found 2,622 files,
  indexed `0`, and skipped 2,622.
- Documents Weijian tree snapshot: 14,764 files; content hashes and mtimes
  were identical before and after both preflights.

## Cutover boundary

The candidate schedule uses `accepted-20260906`, writes logs/evidence under
`$HOME/Workspace/runtime`, and sets `KOS_HOME=$HOME/Workspace/kos`. It is not
installed by this implementation commit. Host crontab replacement requires a
separate governed state-mutation run with exact backup, old/new counts,
unrelated-line identity, accepted-release initialization, and rollback proof.

No Documents file has been moved or deleted. The legacy daily-health chain and
KOS schedule remain active until that cutover evidence exists.
