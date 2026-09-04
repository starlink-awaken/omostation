---
schema_version: report/v1
lifecycle: history
type: implementation-evidence
owner: governance-team
created: 2026-08-29
last_updated: 2026-08-29
bet_id: BET-Y1Q3-T10-70
---

# Documents cockpit-runtime quarantine evidence

## Physical transaction

The stable scoped L4 audit selected exactly 9 runtime files below
`/Users/xiamingxing/Documents/@驾驶舱/_runtime`. It selected zero cache and
zero invalid-archive artifacts. The source fingerprint was
`sha256:b16addf2e747725ce8b8f5c41b96ca0bc4d8cd9f24a6e1c3b84221d266c357f4`.

The files were moved into the retention-protected Workspace quarantine:

`/Users/xiamingxing/Workspace/runtime/quarantine/documents-cockpit-runtime-20260829/`

Manifest:

`/Users/xiamingxing/Workspace/runtime/quarantine/documents-cockpit-runtime-20260829/manifest.json`

Manifest facts:

- schema: `documents-runtime-quarantine/v1`
- status: `completed`
- files: `9`
- bytes: `25769`
- source and target fingerprint: `sha256:b16addf2e747725ce8b8f5c41b96ca0bc4d8cd9f24a6e1c3b84221d266c357f4`
- manifest SHA-256: `sha256:7dbfd5cbf444f32a0bf9c0ded91e6435fa09320a6cac474adab8fcb0b2d69e34`
- permanent deletion: `false`

Immediate postflight verified 9/9 source paths absent and 9/9 target files
equal in SHA-256, byte size, and mode. A delayed recheck also found the
manifest present with the same SHA-256.

## Boundary proof

The postflight L4 audit was stable (`stability_attempts=1`) and returned:

`runtime=0`, `cache=0`, `invalid_archive=0`, `content=592`, `contract=16`,
`projection=144`.

The postflight consumer receipt was `documents.consumer-audit.v1`, status `ok`,
with 191 active observations, 179 content references, 12 Workspace read
owners, zero forbidden executors, and zero unmatched consumers. The remaining
`domain_util.py.bak-20260715`, README, and cron files were intentionally left
in Documents as non-runtime content/material.

## Rollback

Before rollback, recheck the manifest target hashes and source absence. Move
each target back to its recorded source path in reverse order, then rerun the
scoped L4 audit and consumer audit. Do not delete the quarantine package.
