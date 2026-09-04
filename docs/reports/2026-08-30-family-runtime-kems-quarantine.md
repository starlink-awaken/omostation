---
schema_version: report/v1
lifecycle: history
type: implementation-evidence
owner: governance-team
created: 2026-08-30
last_updated: 2026-08-30
bet_id: BET-Y1Q3-T10-93
---

# Family runtime KEMS physical quarantine — implementation evidence

## Scope and commands

- Source scopes: `~/Documents/@家庭生活/_runtime` and
  `~/Documents/@家庭生活/_control/_scripts` only.
- Target scopes: `~/Workspace/runtime/quarantine/documents-family-runtime-symlinks-20260830`
  and `~/Workspace/runtime/quarantine/documents-family-control-runtime-20260830`.
- L4 command: `l4_kernel.content_plane.audit_content_plane(...,
  max_attempts=1)`.
- Consumer command: `documents-domain-owner-job consumer-audit` with the
  fresh receipt at
  `.omo/evidence/20260829T235316Z-bet-execution-0f79f21b/family-consumer-audit-post.json`.
- Transaction command: `lib/documents_runtime_quarantine.py --apply`.
- Apply/postflight observed at `2026-08-29T23:57:17Z`.

## Preflight

- The family `_runtime` audit selected exactly 11 dangling symlinks and no
  regular runtime file. Its only retained entry was `README.md`.
- The family `_control/_scripts` audit selected exactly two regular files:
  `family_search.py` and `restore_knowledge_graph.py`.
- No process held either source scope open.
- Fresh consumer evidence reported `status=ok`, `active=191`,
  `forbidden_executors=0`, and `unmatched=0`. No active consumer record was
  associated with `family-runtime-kems`.
- Both target directories were absent before the transaction.

## Transaction

The quarantine owner moved exactly the selected entries and did not follow or
rewrite any dangling symlink target. No permanent deletion occurred.

| source scope | node type | files | bytes | source/target fingerprint | manifest SHA-256 |
| --- | --- | ---: | ---: | --- | --- |
| `@家庭生活/_runtime` | symlink | 11 | 0 | `sha256:16c51b28b55af10f8608e31dbc043978d4275146be6cf596c5876cc8fbe26e0a` | `sha256:8ae620b70a7ac92a720d2e3d44803f66a6b9f3e207389a860c1a79d876b71630` |
| `@家庭生活/_control/_scripts` | regular | 2 | 6220 | `sha256:962dea7dc21946b1c9276deaeb5bdb8472c587a3a572b175145ebcdfbb368614` | `sha256:1edea8428a3d4068eb7ce9cedd9f86a10417861d621eeee0bc91b31b13c7b9f9` |

Each manifest records the original source path, link target or file hash,
mode, and a reversible rollback instruction. The quarantine package is
protected by `runtime/quarantine/*/` in the Workspace ignore policy.

## Independent postflight

- All 11 symlink source paths and both regular-file source paths are absent;
  target entries exist with matching link targets, hashes, and modes.
- L4 audits are stable (`stability_attempts=1`):
  `@家庭生活/_runtime` reports `content=1` and no runtime/cache entries;
  `@家庭生活/_control` reports `content=36, projection=3`; and
  `_control/_scripts` reports no entries or violations.
- The fresh post-move consumer receipt remains `status=ok` with zero forbidden
  executors and zero unmatched consumers.
- The migration checker remains `ok=True` with zero zero-match and zero
  multiple-match families.
- Adjacent family content, contracts, projections, and facts were not moved.

## Family boundary

This completes the physical quarantine subscopes only. The registry advances
`family-runtime-kems` to `in_progress`; Runtime/Kairon owner parity remains
pending. The quarantined legacy scripts are retained solely for rollback and
must not be treated as the Workspace replacement implementation.
