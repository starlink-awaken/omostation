---
schema_version: report/v1
lifecycle: history
type: implementation-evidence
owner: governance-team
created: 2026-08-29
last_updated: 2026-08-29
bet_id: BET-Y1Q3-T10-69
---

# Documents public-runtime quarantine evidence and loss gap

## Current truth

The transaction below completed at the time of the postflight check, but a
subsequent read-only recheck found both the quarantine directory and its
manifest absent while the 58 Documents source files remained absent. Searches
of the checked Workspace runtime/quarantine, local backup, agent, and temporary
roots found no matching payload. Therefore this report is historical evidence
of an attempted reversible move, not current rollback proof; the registry keeps
`public-runtime` at `pending`.

## Physical transaction

The scoped L4 audit selected exactly 58 runtime files below
`/Users/xiamingxing/Documents/@公共/_runtime`, including the `kems-v2`
subtree. It selected zero cache and zero invalid-archive artifacts. The
preflight source fingerprint was
`sha256:ef9a8195ad2c4994842ff918cbadebd2e84301d591836a3887f9a2a48cefc76c`.

The files were moved, not copied-and-deleted, to:

`/Users/xiamingxing/Workspace/runtime/quarantine/documents-public-runtime-20260829/`

The quarantine manifest is:

`/Users/xiamingxing/Workspace/runtime/quarantine/documents-public-runtime-20260829/manifest.json`

Manifest facts:

- schema: `documents-runtime-quarantine/v1`
- status: `completed`
- files: `58`
- bytes: `346217`
- source and target fingerprint: `sha256:ef9a8195ad2c4994842ff918cbadebd2e84301d591836a3887f9a2a48cefc76c`
- manifest SHA-256: `sha256:1fe9d462263861d18ff21ca3931365c62a3f6c46604a66d18c207dfad18ca8f9`
- permanent deletion: `false`

At the first postflight, 58/58 source paths were absent and 58/58 target files equal in
SHA-256, byte size, and mode. The transaction restores already moved files on
any pre-manifest failure.

## Boundary proof

The first postflight L4 audit was stable (`stability_attempts=1`) and returned:

`runtime=0`, `cache=0`, `invalid_archive=0`, `content=105`, `contract=11`,
`projection=3`, `bridge=1`.

The consumer receipt was `documents.consumer-audit.v1`, status `ok`, with 191
active observations, 179 content references, 12 Workspace read owners, zero
forbidden executors, and zero unmatched consumers. Public/cockpit references
remain classified as content references; they were not executed or rewritten.

At the time of that postflight, only the 58 selected runtime files moved. Markdown/content, contracts,
projections, bridges, host schedules, LaunchAgents, client configuration, and
permanent deletion were outside this transaction.

## Rollback status

Rollback is currently **not available** because the physical manifest and
payload cannot be located. Do not mark this family terminal and do not delete,
recreate, or overwrite any path until a new protected receipt transaction is
authorized and its source/target bytes are independently verified.

## Intended rollback procedure

Before rollback, recheck the manifest target hashes and source absence. Move
each target back to its recorded source path in reverse order, then rerun the
scoped L4 audit and consumer audit. Do not delete the quarantine package.
