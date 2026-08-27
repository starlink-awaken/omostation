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

## Remaining consumer tail

T10-42 is registered for the remaining Scheduled health instructions and the
OMO derived task-state projection. The next run must update the Scheduled
skill through a bounded host-file mutation and synchronize `.omo/state` only
through the OMO broker. It must not infer consumer completion from the cron
cutover alone.

The T10-42 state run completed the Scheduled migration and brokered task-counter
sync. The Scheduled file changed from SHA-256
`983aa3db4f09277359bdd3a85a86c0b7852992c8e97adc718ead496d01cf933e` to
`0cac9455eca53b5df444300510642eba25e83cea896a19113d5488eb6041d210`; its
legacy Documents execution references are absent. `omo state sync-tasks`
updated `system.yaml` to completed=290, planned=7, active=1, blocked=1,
total=299 through the broker. The task registry's old Documents evidence
references were replaced with Workspace runtime evidence for the 11 migrated
tasks; before/after hashes are retained in the run evidence. Task inventory
now reports 48 healthy, 3 dormant, 10 paper, 8 drift, 12 proposed, 2 degraded,
and 2 retired tasks; after the final two registry corrections, inventory
reports 49 healthy, 3 dormant, 8 paper, 8 drift, 13 proposed, 2 degraded,
and 2 retired tasks. The remaining drift entries are separately identified
unregistered carriers, not a reason to restore Documents execution.

The live OMO state sync was executed through `omo state sync-tasks` (exit `0`),
which set completed=290, planned=7, active=1, blocked=1, total=299. The live
`system.yaml` after hash is
`4a1c2e08f6d36cdd1c07250f6eaaa28c2578c0a150b12aaff37153cd31fc0680`; the
worktree copy contains the same semantic projection with a separate generated
timestamp. The task-registry before/after hashes are
`7f98e3167490e58c338af109d0543498744c6d217dd1c2a7eea1fe7d9426f0e9` and
`9d012acffa4e01f90c6cb0341bcf0c4012626ad6c1c1c5c846ffc61d718076d6`.
Only the 11 migrated consumer records plus the stale inactive index record and
duplicate controller record changed; the registry backups are retained in the
governed run evidence. The final task-registry hash is
`74d00c73dda09da4a623eed86c69c0192a0c24382914e9df21b30f2fec740666`.

The migration-family registry now covers the 12 previously unmatched gateway
references: `驾驶舱/scripts/**` is `cockpit-runtime`, `@公共/kems-v2/**` is
`public-runtime`, and `学习进化/2-knowledge/基建架构/**` is
`learning-runtime`. The final consumer audit reports `status=ok`,
`forbidden_executors=0`, and `unmatched=0`; gateway instructions remain
classified as content references/read-only owner inputs.

## BOS Neural Mesh state-owner preflight

`lib/bos_neural_mesh_owner.py` now provides a Workspace-owned, fail-closed
entrypoint. Live smoke detected the legacy Documents runner and state DB,
resolved the target state DB to `$HOME/Workspace/runtime/bos-neural-mesh-state.sqlite`,
and invoked zero connectors. The owner reports `writes_documents=false`; it
does not copy the old connector chain into a second runtime. The legacy runner
and state DB remain intact until an accepted-release state-mutation run records
copy/hash/integrity/rollback evidence.

## BOS Neural Mesh state cutover

- Accepted release: `accepted-20260908`, root SHA `576600b12`.
- No active cron or launchd runner existed; the only launchd reference was in
  the archived directory.
- The legacy runner, SQLite DB, and lock were moved to
  `$HOME/Workspace/runtime/quarantine/documents-bos-neural-mesh-20260828/`.
- The canonical DB is `$HOME/Workspace/runtime/bos-neural-mesh-state.sqlite`;
  SQLite integrity is `ok`, and source/target SHA-256 is
  `d4aed59608c3eac58b97741cb5148eb53c55b195c647fb786f4be064fb944092`.
- Post-migration owner smoke reports legacy runner/state `absent`,
  `state_owner=workspace`, `connector_invocations=0`, and
  `writes_documents=false`; connector execution remains fail-closed.
- Quarantine objects retain byte-identical hashes; the exact receipts are under
  the governed state-mutation evidence directory.
