---
schema_version: report/v1
lifecycle: history
type: implementation-evidence
owner: governance-team
created: 2026-08-30
last_updated: 2026-08-30
bet_id: BET-Y1Q3-T10-96
---

# Learning runtime legacy helper quarantine — implementation evidence

## Scope and preflight

- Source scope was limited to four individual regular files under
  `~/Documents/@学习进化/_control/scripts/`:
  `backfill-knowledge-type.py`, `backfill-knowledge-type.sh`,
  `concept-weave.py`, and `run-monthly-weave.sh`.
- Each single-file L4 audit was stable and selected exactly one runtime file.
- Fresh consumer evidence at
  `.omo/evidence/20260830T011432Z-bet-execution-49ce5800/learning-consumer-audit-post.json`
  remained `status=ok`, `active=191`, `forbidden_executors=0`, and
  `unmatched=0`. The only learning-runtime record was a content reference to
  an already absent historical validator path.
- No selected file was held by a process and all four Workspace targets were
  absent before apply.

## Transactions

Four independent `documents_runtime_quarantine.py --apply` transactions moved
the files to protected Workspace retention. Each manifest records source path,
regular-file hash, mode, bytes, and rollback instructions; no permanent
deletion occurred.

| source file | bytes | SHA-256 | target package | manifest SHA-256 |
| --- | ---: | --- | --- | --- |
| `backfill-knowledge-type.py` | 8020 | `4dd8c18c4a10631f199b12d222a3636864bddd40428baf42d671c0d9417cbc0b` | `documents-learning-backfill-py-20260830` | `sha256:8ef8384b18ef7a85bd82343d94ddf29f06d2e3088c9a1a4d51cb10c4db6af931` |
| `backfill-knowledge-type.sh` | 8805 | `6ee4ba65bfc414664fafabec1364ea6648ec908d1be5ba24d4c2bc45bc64d4d5` | `documents-learning-backfill-sh-20260830` | `sha256:2739e4c356f21e41e46db97108a98b1952020349db42842c49324617329c12dc` |
| `concept-weave.py` | 11346 | `eb854847c30315dee3e98f8cce9f1266181798180b9613fc2b5c6a8cce500b79` | `documents-learning-concept-weave-20260830` | `sha256:7a14cd9dcfd7656d324768526b6e11d25a95b912d25e820c2b563fd9363ab64c` |
| `run-monthly-weave.sh` | 6391 | `e971db32d15c8a8b03b66551d0c4f4c897a62cd08df0f2b4447cc1f844267fd2` | `documents-learning-monthly-weave-20260830` | `sha256:af7487e0ccc48b9c7d40e035affae16f420f5a2f932193fd5dbc20e3252c71b1` |

Total moved payload: 34,562 bytes across four regular files.

## Independent postflight

- All four source paths are absent; all targets are regular files with matching
  hashes, modes, and bytes, and source/target fingerprints match per manifest.
- Stable L4 residual audits report `@学习进化/_control`:
  `content=39, projection=3, runtime=14`; `_control/scripts`:
  `content=2, runtime=1`; `_inbox`: `content=5, contract=1, runtime=1`;
  `.githooks`: `runtime=1`.
- The residual 16 runtime objects remain deliberately untouched because their
  owner/cutover contract is not yet proven. Learning content and projections
  remain in Documents.
- Post-move consumer evidence remains zero forbidden and zero unmatched.

## Family boundary

Only four legacy helper subscopes are complete. `learning-runtime` advances to
`in_progress`; owner parity remains pending. The existing Workspace
`documents_concept_weave_preflight` owner covers read-only health measurement,
but write-capable mesh/bridge/decay and other learning executors still require
separate owner contracts before further physical removal.
