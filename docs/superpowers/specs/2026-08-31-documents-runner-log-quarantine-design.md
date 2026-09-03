---
schema_version: specification/v1
spec_version: 1.0.0
title: Documents retired runner-log exact quarantine
bet_id: BET-Y1Q3-T10-110
status: accepted
lifecycle: contract
owner: governance-team
created: 2026-08-30
last-reviewed: 2026-08-30
type: ssot
last_updated: 2026-09-03
---

# Documents retired runner-log exact quarantine

## Context

T10-109 made the canonical L4 classifier expose machine-generated operational
logs as `cache/L4-CONTENT-009` while preserving arbitrary and archive-governed
historical logs. Two retired files are now truthfully visible but remain in the
Documents content plane:

- `_inbox/hourly_runner.log`;
- `_inbox/hourly_runner_err.log`.

A read-only 2026-08-31 snapshot found both files present, regular, mode `0644`,
zero bytes, and SHA-256
`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.
They had no open handle, process, crontab, LaunchAgent, Claude Scheduled, or
active consumer reference. The current consumer audit remained `status=ok`,
`forbidden_executors=0`, and `unmatched=0`.

The `_inbox` tree also contains human content. A scoped audit rooted directly
at `_inbox` loses the parent `_inbox` path component, so the two logs appear as
ordinary content in that scoped view even though classification against the
full Documents root correctly returns cache. Therefore neither directory-wide
movement nor the existing scoped-runtime selector is safe.

These counts and host facts are a dated preflight snapshot, not durable SSOT.
The implementation must remeasure them immediately before any host mutation.

## Decision

Deepen the existing Workspace-owned
`lib/documents_runtime_quarantine.py` transaction with a backward-compatible
exact-selection mode. Use it to move exactly the two files into:

`/Users/xiamingxing/Workspace/runtime/quarantine/documents-root-inbox-runner-logs-20260831`

The target is the existing recoverable Workspace quarantine namespace covered
by `runtime/quarantine/*/`. It is not content and is not a new authority. The
transaction retains a durable manifest and executable verification/rollback.

No new CLI, registry, dispatcher, artifact ontology, or migration primitive is
created.

## Alternatives

1. **Deepen the canonical quarantine primitive — selected.** Adds exact cache
   selection and recovery semantics once while preserving existing runtime
   callers.
2. **Run two single-file legacy transactions — rejected.** The current
   single-file audit loses `_inbox` context, would produce two manifests, and
   cannot select cache.
3. **Create a runner-log-specific mover — rejected.** It duplicates path,
   hashing, manifest, rollback, and consumer gates as a second migration
   mechanism.
4. **Permanently delete zero-byte logs — rejected.** File size is not authority
   to remove rollback and provenance.

## Compatibility contract

The current CLI defaults and public Python behavior remain unchanged when no
new option is supplied:

- plan remains the default operation;
- `--apply` remains the existing mutation gate;
- default selected kind remains exactly `runtime`;
- directory and single-file legacy callers retain their current inventory and
  manifest semantics;
- `documents-runtime-quarantine/v1` remains the plan/completed-manifest schema.

Exact mode is activated only by one or more `--include-relative` values. It
requires one or more explicit `--artifact-kind` values from the closed set
`runtime|cache`. The T10-110 invocation supplies `cache` only and both exact
relative names.

## Exact inventory contract

For exact mode:

1. Resolve the configured Documents root and source root without following a
   source symlink.
2. Reject empty, absolute, duplicate, dot, dot-dot, or escaping include paths.
3. Require every included node to exist below the source root and remain a
   regular file or safe recorded symlink.
4. Classify every included node against the complete Documents root, then
   rebase its manifest `relative_path` below the source root. This preserves
   `_inbox` semantic context without running an unstable full-tree audit.
5. Require the classification kind to belong to the explicit allowed-kind set.
6. Require the selected path set to equal the expected include set exactly;
   neither an extra violation nor a missing include is tolerated.
7. Sample file type, bytes, mode, SHA-256, and symlink target where applicable
   before and after classification; any drift stops planning.

The resulting T10-110 selected set is exactly:

`hourly_runner.log`, `hourly_runner_err.log`.

## Non-target scope guard

Exact mode snapshots every non-selected regular file and symlink below the
source root without following directory links. The canonical snapshot records
relative path, node type, bytes, mode, content/link digest, file count, byte
count, and one fingerprint.

Immediately before the first move and after the final target verification,
recompute that snapshot. Both values must equal the plan. This proves the
remaining `_inbox` content was not selected or altered by the transaction.
Concurrent non-target change is a circuit breaker, not permission to update the
plan silently.

Legacy non-exact mode does not acquire a new non-target contract or change its
existing behavior.

## Transaction contract

### Preflight

- The fresh consumer receipt must use `documents.consumer-audit.v1`, report
  `status=ok`, and contain zero forbidden and unmatched consumers.
- Two independently generated plans with a fixed `--now` value must be
  byte-identical.
- Both source files must retain their measured path, type, mode, size, hash,
  inode, and mtime immediately before apply.
- `lsof` must show no open handle in two checks separated by the rest of the
  preflight; process, crontab, LaunchAgent, and Scheduled scans must remain
  empty for the exact names.
- The target and manifest must be absent, the target parent must be the actual
  integration Workspace quarantine, and the target must remain outside
  Documents.
- The target path must match the existing quarantine ignore/retention policy.
- The exact selected set and non-target fingerprint must remain stable.

### Apply

1. Revalidate the consumer receipt, exact sources, selected fingerprint,
   non-target fingerprint, and target boundary.
2. Create the target directory only after all preflight checks pass.
3. Move selected files with `os.replace`, preserving relative names and modes.
4. On any failure before durable publication, restore every moved source in
   reverse order; never overwrite a recreated source.
5. Verify target file type, bytes, mode, hash, selected fingerprint, source
   absence, and non-target fingerprint.
6. Atomically write and fsync the completed v1 manifest with
   `permanent_deletion=false`.

Zero-byte files remain real manifest entries. They must not be optimized away.

### Verify

Add a completed-manifest verification path to the existing primitive. It fails
unless:

- schema/status/target/source boundaries are valid;
- the selected target set exactly matches the manifest;
- every target type/mode/size/hash matches;
- every selected source is absent;
- source and target fingerprints match;
- the non-target fingerprint remains equal;
- the manifest states permanent deletion is false.

Verification is read-only and supports fresh mainline replay after host apply.

### Rollback

Add an explicit rollback path that first performs completed-manifest
verification. It then moves targets back in reverse order only when every
source is absent and every target remains manifest-equal. Any collision or
drift stops before overwrite.

After restoring and verifying source metadata, write a separate fsynced
`documents-runtime-quarantine-rollback/v1` receipt in the quarantine target.
Keep the original completed manifest immutable. Do not automatically remove
the evidence directory or permanently delete any file.

## Registry projection

Keep `root-oneoff-assets` as the sole existing family. Append one completed
transaction for the exact runner-log scope with target, file/byte counts,
source/target fingerprint, manifest digest, consumer receipt, and rollback
reference.

The family remains `pending`. Its broad `_inbox/**` scope, unrelated root
assets, and historical missing eight-file rollback package remain unresolved.
T10-110 must not rewrite, waive, or falsely close that evidence gap.

## Host delivery ordering

1. Merge and replay the capability PR before host mutation.
2. From a fresh full-profile mainline clone, collect consumer, handle, schedule,
   source, target, and non-target evidence and compare two dry-run plans.
3. Apply once from main to the actual integration Workspace target.
4. Run completed-manifest verify, fresh consumer audit, exact source absence,
   delayed target/manifest retention, non-target fingerprint, and a stable full
   Documents L4 audit.
5. Append the registry transaction and completion evidence in a separate
   closeout PR.
6. Merge closeout, replay verification from root main, then close workflows.

## Error handling

Unsafe includes, unexpected kind, malformed receipt, missing source, source or
non-target drift, open handle, schedule/consumer discovery, target collision,
path escape, manifest collision, hash/mode/type mismatch, publication failure,
verification failure, rollback collision, or evidence-retention loss returns
nonzero and preserves the most recoverable state.

There is no force, glob include, overwrite, delete, prune, or partial-success
mode.

## Testing

Implementation is test-first. Tests cover:

- existing runtime default compatibility;
- exact include validation and duplicate/path-escape rejection;
- complete-Documents classification with source-relative manifest rebasing;
- closed runtime/cache kind selection and content rejection;
- exact set equality and stable pre/post source sampling;
- non-target snapshot determinism and pre/post drift rejection;
- two zero-byte regular files as real selected entries;
- target collision, source drift, partial-move restoration, durable manifest,
  completed verification, and immutable-manifest rollback receipt;
- safe symlink semantics and existing malformed receipt behavior;
- CLI plan/apply/verify/rollback JSON envelopes;
- root-oneoff transaction append without family terminal-state change;
- retention policy, consumer audit, GaC, required CI, PR merges, and mainline
  replay.

Host acceptance additionally proves two no-handle checks, no active consumer or
schedule, exact two-file source absence, target parity, non-target equality,
delayed manifest retention, and permanent deletion false.

## Non-goals

- No movement or rewrite of the other `_inbox` content.
- No directory-wide cache/runtime quarantine.
- No permanent deletion or log-content interpretation.
- No host schedule, process, LaunchAgent, application, or client mutation.
- No new registry family, CLI entry point, dispatcher, ontology, or control
  plane.
- No repair or waiver of historical `root-oneoff-assets` rollback loss.
- No claim that Documents-wide physical purity or principal-bound value is
  complete.

## Acceptance

- Existing callers remain backward compatible and focused/full transaction
  tests pass from main.
- Exact mode can select only the two cache-classified runner logs and proves all
  non-target `_inbox` nodes unchanged.
- Capability PR, required checks, and mainline replay pass before apply.
- Host apply publishes a durable, hash-valid, explicitly rollback-capable
  package at the fixed integration Workspace target.
- Selected sources are absent, target and manifest remain present and equal on
  delayed recheck, consumer audit remains green, and permanent deletion is
  false.
- Registry transaction, report, retro, completion matrix, closeout PR,
  mainline replay, and workflow closeout pass while the family remains pending.
- Engineering and operational relocation may become proven; principal-bound
  user value and Documents-wide purity remain `NOT_PROVEN`.
