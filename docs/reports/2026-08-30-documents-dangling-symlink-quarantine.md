---
schema_version: report/v1
lifecycle: history
type: implementation-evidence
owner: governance-team
created: 2026-08-30
last_updated: 2026-08-30
bet_id: BET-Y1Q3-T10-73
---

# Documents dangling symlink quarantine evidence

## Scope

The stable Weijian `_runtime` audit identified 12 symlink objects whose targets
were absent because the referenced public-runtime files had already been lost.
T10-73 selected only those dangling symlinks. It did not select the 17 regular
runtime files in the same subtree.

## Transaction

The 12 symlink objects were moved without following their targets to:

`/Users/xiamingxing/Workspace/runtime/quarantine/documents-weijian-symlinks-20260829/`

Manifest:

`/Users/xiamingxing/Workspace/runtime/quarantine/documents-weijian-symlinks-20260829/manifest.json`

Facts:

- schema: `documents-runtime-quarantine/v1`
- status: `completed`
- files: `12`
- bytes: `0` (symlink objects; target bytes were not reconstructed)
- source and target fingerprint: `sha256:5ffd9cc38b1b6f04a350621bea1fba3e28c63fd5de76c606647bafafd92eb4a4`
- manifest SHA-256: `sha256:e9628b1e34317fbe710ca2f722e35f6d19db71dfe97337204cfe3f80eb785df0`
- permanent deletion: `false`

Immediate postflight verified 12/12 source links absent and 12/12 target
`readlink` values identical. A delayed recheck found the manifest present with
the same SHA-256. The quarantine path is protected by
`runtime/quarantine/*/`.

## Boundary proof

Postflight L4 audit of
`/Users/xiamingxing/Documents/@工作文档/卫健委/_runtime` was stable and
reported `runtime=17`, `cache=0`, `invalid_archive=0`; these 17 regular runtime
files were intentionally left for a separate wave. Consumer evidence was
status `ok`, with 191 active observations, 179 content references, zero
forbidden executors, and zero unmatched consumers.

No target script bytes were read through or recreated. No regular runtime,
business content, contract, projection, `_storage`, schedule, LaunchAgent, or
client configuration was changed. The broader `work-runtime` family remains
non-terminal.

## Rollback

Recheck the manifest target link values and source absence, then move each
quarantined symlink back to its recorded source path in reverse order. Do not
resolve, execute, or recreate any missing link target.
