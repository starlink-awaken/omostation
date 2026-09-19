---
schema_version: specification/v1
spec_version: 1.0.2
title: CC Switch recovery-state relocation from Documents
bet_id: BET-Y1Q3-T10-108
status: accepted
lifecycle: contract
owner: governance-team
created: 2026-08-30
last-reviewed: 2026-08-30
type: ssot
last_updated: 2026-09-03
---

# CC Switch recovery-state relocation from Documents

## Context

Documents must retain human content, contracts, decisions, reports, and bridge
shells, not application databases, SQL recovery workspaces, configuration
backups, or execution logs. Two hidden Documents roots currently violate that
boundary:

- `.codex-optimize-log`: 4 regular files and 208085704 bytes;
- `.cc-switch-recovery2`: 17 regular files and 209687264 bytes.

The active CC Switch database already lives under
`~/Library/Application Support/CC_Switch`. The two Documents roots are inactive
recovery corpora: current inspection found no open handles, and the existing
Documents consumer audit is green with zero forbidden executors and zero
unmatched consumers. L4 currently classifies these extensionless database and
backup files as `content`; that is a known classifier gap, not authority to keep
application recovery state in Documents.

The live recovery corpus contains both repaired databases and one intentionally
retained pre-repair database whose `PRAGMA quick_check` is already non-`ok`.
Recovery relocation preserves that evidence; it must not rewrite corruption as
health or discard the byte-identical pre-repair sample.

## Decision

Create one Workspace-owned, fail-closed recovery relocation transaction. It
moves the complete two-root snapshot to:

`~/Library/Application Support/CC_Switch Recovery/2026-08-30`

The target contains the two original root names plus a durable manifest. The
transaction is code and governance owned by Workspace; the retained payload is
native application recovery state outside both Documents and Workspace runtime.
No second registry, dispatcher, state authority, or human entry point is added.

## Alternatives

1. **Native App Support recovery target — selected.** Correct ownership and
   durable retention semantics; separates application recovery data from
   cleanable Workspace runtime.
2. **Workspace runtime quarantine — rejected.** It would make long-lived client
   recovery data vulnerable to runtime cleanup and repeat the ZCode placement
   error.
3. **Documents content archive — rejected.** Renaming or declaring binary
   database recovery data as content would preserve the physical purity defect
   and hide the classifier gap.

## Components

### Workspace transaction primitive

Deepen the existing registered `bin/gac/documents-domain-owner-job.py` entry
with a narrow `client-recovery` subcommand backed by a focused library. The
library owns inventory, source/target boundary checks, fingerprinting, staging,
publication, verification, rollback, and status. The existing CLI provides
`plan`, `apply`, `verify`, and `rollback` commands with JSON output. This keeps
the bin quota flat and avoids a second Documents governance entry.

The primitive accepts exactly two source roots and the fixed App Support target
for this BET. It must not infer additional Documents paths or follow symlinks.

### Migration-family projection

Keep the existing migration registry as the sole authority. Add a dedicated
`cc-switch-recovery-state` family rather than overloading
`root-oneoff-assets`, whose historical code/cache retirement semantics and
missing eight-file rollback receipt remain unchanged.

The new family owns `.codex-optimize-log/**` and `.cc-switch-recovery2/**` with
`disposition: relocate`, owner `cc-switch`, and the native App Support recovery
target. Remove `.codex-optimize-log/**` from `root-oneoff-assets` only in the
same atomic registry change so no source surface is double-owned or unowned.

## Transaction contract

### Preflight

- Both source roots must be real directories directly below the configured
  Documents root, with no symlink in either root or any selected descendant.
- The inventory must contain exactly all regular files below both roots; any
  socket, FIFO, device, directory symlink, unreadable node, or concurrent tree
  mutation stops the transaction.
- No selected source may have an open handle. The active CC Switch process may
  remain running only if it has no handle below either source root.
- The final target and staging target must be absent, and the target parent must
  resolve below `~/Library/Application Support` but outside the active
  `CC_Switch` directory.
- A fresh Documents consumer receipt must report `status=ok`,
  `forbidden_executors=0`, and `unmatched=0`.
- Available disk space must exceed the source byte count plus manifest/staging
  overhead.
- Every recognizable SQLite file is checked. Healthy files are recorded `ok`;
  pre-existing failures are recorded `corrupt-preserved` with a digest of the
  quick-check result. At least one recognizable SQLite file must be `ok`.

### Apply and publication

1. Recompute the complete source inventory immediately before mutation.
2. Move each selected regular file into a private sibling staging directory,
   preserving relative path and mode. A failure restores every moved file in
   reverse order.
3. Verify file count, byte count, mode, SHA-256, and canonical tree fingerprint.
4. For every non-empty file whose header is `SQLite format 3`, run
   `PRAGMA quick_check`. Require every source status and result digest to replay
   identically after movement: healthy files remain `ok`, while known damaged
   recovery files remain byte-identical `corrupt-preserved`. Zero-byte and
   non-SQLite recovery artifacts remain byte-preserved.
5. Write and fsync a `documents-client-recovery-relocation/v1` manifest, then
   atomically publish staging as the final target.
6. Remove only now-empty source directories. Permanent deletion is forbidden.

### Verify and rollback

`verify` fails unless every manifest target is present and byte/mode equal,
every manifest source is absent, source roots contain no residual file, the
target fingerprint matches, SQLite classifications replay exactly with at least
one healthy database, and the consumer audit still has no forbidden or
unmatched consumer.

`rollback` is allowed only when target hashes still match and both source roots
are absent. It moves payload files back in reverse order, re-verifies source
hashes and modes, retains a rollback receipt outside Documents, and never
overwrites a newly created source path.

## Error handling

All errors use stable machine-readable codes. Boundary drift, source drift,
target collision, open handles, insufficient disk, malformed receipts,
non-regular nodes, missing healthy SQLite recovery, changed SQLite
classification/result digest, hash/mode mismatch, publication failure, or
rollback failure returns nonzero and preserves the most recoverable state.
No `--force`, implicit overwrite, partial-success, or permanent-delete mode is
permitted.

## Testing

Tests must be written first and prove RED before implementation. They cover:

- exact two-root inventory and deterministic fingerprinting;
- symlink and non-regular-node rejection;
- target boundary and active-data-directory rejection;
- open-handle, disk-space, consumer-receipt, source-drift, and collision gates;
- move, staging verification, atomic publication, and reverse-order rollback;
- valid, pre-corrupt, zero-byte, and non-SQLite recovery artifacts, including
  exact `corrupt-preserved` replay;
- manifest/status/rollback idempotence and Python 3.9 compatibility;
- registry ownership uniqueness and required CI wiring.

Host acceptance additionally requires a dry-run plan, a second quiescence
check immediately before apply, postflight manifest replay, a fresh consumer
audit, and a stable full-tree Documents audit.

## Non-goals

- No active `~/Library/Application Support/CC_Switch` database, logs, exports,
  backups, configuration, process, or schema mutation.
- No iCloud `SharedConf/CC_Switch*` mutation.
- No L4 classifier behavior change and no `_inbox/hourly_runner*.log` movement;
  each is a separate follow-up BET.
- No recovery-data deduplication, compression, pruning, interpretation, or
  permanent deletion.
- No claim that historical `root-oneoff-assets` or `public-runtime` rollback
  gaps are repaired.

## Acceptance

- The design, implementation plan, tests, deepened registered Workspace owner,
  migration-family projection, report, retro, and rollback contract are merged.
- A host plan identifies exactly 21 files and 417772968 bytes unless a new
  preflight snapshot is explicitly reviewed; any drift stops apply.
- Apply and verify prove source absence, target completeness, healthy SQLite
  databases remain `ok`, known damaged recovery databases remain byte-identical
  `corrupt-preserved`, manifest durability, and zero forbidden/unmatched
  consumers.
- Required CI, PR merge, mainline replay, and workflow closeout pass.
- Engineering may become `VERIFIED` and operational may become `PROVEN`; user
  value remains `NOT_PROVEN` without principal-bound adjudication.
