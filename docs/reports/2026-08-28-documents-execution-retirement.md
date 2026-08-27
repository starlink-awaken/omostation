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

## Accepted-release cutover

- Accepted release: `accepted-20260906`, root SHA `1797fd3ca`.
- Crontab evidence: `.omo/evidence/20260827T220124Z-governance-state-mutation-9a4b31b6/`;
  before SHA-256 `f3c7584e7221dfe806e9e57c7582a897ab3124d04d201796d77a275de9c82113`;
  after SHA-256 `2e78e757f48e778deab409b03018e2b66bd98a290658ca9fbc55964ef6da3196`.
- Daily-health old line `1 → 0`, new Workspace owner line `0 → 1`.
- KOS old line `1 → 0`, new Workspace owner line `0 → 1`.
- Unrelated crontab lines were byte-identical.
- Post-cutover daily-health smoke: `findings`, exit `1`, with
  `stale_knowledge=679`, `stale_inbox=4`, `pending_inbox=0`, `signals=0`.
- Post-cutover KOS smoke: `ok`, exit `0`; all eight source domains returned
  exit `0`, and all writes were directed to Workspace `KOS_HOME`.
- Post-cutover Documents tree: 14,764 files before and after; digest
  `12243d9f7c6b5ada1b31700346dfb4bc3c05337c44e8a111f5dca75d558f9b7b` on both
  sides.

## Cutover boundary

The installed schedule uses `accepted-20260906`, writes logs/evidence under
`$HOME/Workspace/runtime`, and sets `KOS_HOME=$HOME/Workspace/kos`. Rollback is
restoring the verified crontab backup after checking its SHA-256.

No Documents file has been moved or deleted. The legacy scripts remain intact
as rollback material; their active schedules are no longer installed.
