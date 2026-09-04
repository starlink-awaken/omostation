---
type: ephemeral
created: 2026-09-03
---

# T10-59 Documents root one-off quarantine evidence

## Result

Exactly eight inactive runtime/cache objects were moved from Documents to the
recoverable Workspace quarantine:

`/Users/xiamingxing/Workspace/runtime/quarantine/documents-root-oneoff-20260829/`

The quarantine manifest is the authoritative physical receipt:

`runtime/quarantine/documents-root-oneoff-20260829/manifest.json`

It records `documents-root-oneoff-quarantine/v1`, the T10-58 run id, source and
target paths, modes, sizes, SHA-256 values, and a reversible rename-back
procedure. Total moved bytes: **4,106,995**. Permanent deletion: **false**.
Manifest SHA-256: `sha256:ad1084bf3abb95bc870036d750b1a86192dbccd8b29e265980732a87da957142`.

| source relative path | bytes | source SHA-256 | target SHA-256 |
| --- | ---: | --- | --- |
| `_inbox/2026-08-02-cleanup-gz-artifacts.sh` | 2,208 | `sha256:e2448be2af1b5c65182f1f7386c5c776b9b97e70ad93b20d1f8f39105d6e849b` | `sha256:e2448be2af1b5c65182f1f7386c5c776b9b97e70ad93b20d1f8f39105d6e849b` |
| `_inbox/2026-08-03-kems-repair.py` | 22,410 | `sha256:b8ae0b5b67a6e8856c92540980a5e2d5ddb3e9e71baf80d51a67b146d64a5542` | `sha256:b8ae0b5b67a6e8856c92540980a5e2d5ddb3e9e71baf80d51a67b146d64a5542` |
| `_inbox/2026-08-03-老化知识处理脚本.sh` | 4,360 | `sha256:d2538c10d23570d4fdaca3e106b8e97b13c8fcae3569619e19fbe8a53005b186` | `sha256:d2538c10d23570d4fdaca3e106b8e97b13c8fcae3569619e19fbe8a53005b186` |
| `cron-service-db-fix.py` | 2,372 | `sha256:1ae6f58b32e79e495d8de1481dae93a331511cd0a2d4a2dab4f45abecf8558e4` | `sha256:1ae6f58b32e79e495d8de1481dae93a331511cd0a2d4a2dab4f45abecf8558e4` |
| `cron-service-error-reset.py` | 951 | `sha256:f2c774a4aab0ad2b64c9e1233db4f13a83cbccfa55ab3a82fc27d19f293991fa` | `sha256:f2c774a4aab0ad2b64c9e1233db4f13a83cbccfa55ab3a82fc27d19f293991fa` |
| `cron-service-fix.sh` | 2,040 | `sha256:3d3e1973aa6fa7ef9a4823598d62f1668417df5c0f68458c841d28ca7c2e8314` | `sha256:3d3e1973aa6fa7ef9a4823598d62f1668417df5c0f68458c841d28ca7c2e8314` |
| `kos-index.sqlite` | 20,480 | `sha256:1a2ce31bdc103620a346961c6b86aa60e25d590a373272038ee9c7fd38c92a34` | `sha256:1a2ce31bdc103620a346961c6b86aa60e25d590a373272038ee9c7fd38c92a34` |
| `index-BYqQMscj.js` | 4,052,174 | `sha256:4306ee6901a3645931e0f9d98eb5b94257173f17e6ca8ce568617194a9fb9dbe` | `sha256:4306ee6901a3645931e0f9d98eb5b94257173f17e6ca8ce568617194a9fb9dbe` |

## Preflight and postflight

- All eight sources were regular files and had no open handles at preflight and
  immediately before rename.
- The existing consumer audit contained no active execution consumer for the
  exact targets; its postflight summary remained `191 active`, `179
  content-reference`, `12 workspace-owner-read`, `0 forbidden_executors`, and
  `0 unmatched`.
- The remaining Documents `_inbox` was audited independently: `110 content`,
  `0 runtime`, `0 cache`, `stability_attempts=1`, `ok=true`.
- All eight source paths are absent; every target hash equals its preflight
  source hash; the manifest is complete.
- No other `_inbox` content, domain file, crontab line, LaunchAgent, or
  Scheduled skill was intentionally changed.

## Failed attempts and control response

Two initial whole-batch attempts were rolled back because the operation-boundary
check included expected parent-directory metadata changes. A root-only attempt
also exposed and corrected staging cleanup order, and the first inbox attempt
exposed and corrected a missing destination-parent creation. Each attempt
restored all sources and hash-checked them before continuing. The final split
transactions compare non-target regular files within the touched parent and
keep the source/target rollback manifest.

## Boundary

This is physical quarantine, not permanent deletion and not completion of all
Documents purification. The migration registry's `root-oneoff-assets` status
will be updated in a separate declared governance write. The other 14 migration
families remain pending/in progress.
