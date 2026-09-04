---
schema_version: specification/v1
spec_version: 1.0.0
title: Learning content mutation owner convergence
bet_id: BET-Y1Q3-T10-100
status: accepted
lifecycle: contract
owner: governance-team
created: 2026-08-30
last-reviewed: 2026-08-30
risk_level: L2
human_gate: true
type: ssot
last_updated: 2026-09-03
---

# Learning content mutation owner convergence

## Intent

Remove the last two learning-domain executable implementations from
Documents while retaining their useful behavior behind a single Workspace
owner entry. Documents remains content and declarations; Workspace owns the
plan, approval boundary, mutation transaction, rollback evidence, and CLI.

## Existing behavior

- `@学习进化/_control/scripts/knowledge-decay.sh mark-stale` finds draft,
  zero-reference concepts older than the configured threshold and inserts a
  `stale_since` frontmatter field.
- `@学习进化/_inbox/inbox-router.sh` classifies the first five lines of each
  inbox file by deterministic keyword rules. Internal targets are moved inside
  the learning vault; cross-domain targets are reported but not moved.
- Neither operation has a safe Workspace owner, optimistic concurrency check,
  rollback package, or a single canonical installed entry.

## Canonical owner

```text
python3 bin/gac/documents-domain-owner-job.py learning-control decay mark-stale --dry-run
python3 bin/gac/documents-domain-owner-job.py learning-control inbox route --dry-run
```

`--apply` is never the default. It requires
`--expected-fingerprint <sha256>` produced by the preceding plan and writes a
manifest under Workspace `runtime/quarantine` before touching Documents.
Every selected source is rehashed immediately before mutation. A collision,
source drift, or partial failure aborts and reverses already-applied changes.

## Data and safety contract

- The owner reads only the declared concept/inbox roots below the supplied
  Documents root and rejects absolute paths, traversal, symlink escapes, and
  overlapping Workspace/ Documents roots.
- Plans expose relative paths, source hashes, modes, byte sizes, proposed
  destination/frontmatter operation, and a tree fingerprint; they do not print
  source text.
- Decay plans use valid `last-reviewed` when present and otherwise file mtime;
  the threshold and date are explicit in the plan. A missing/invalid date is
  reported as unavailable rather than silently fresh.
- Inbox plans preserve the legacy internal keyword mapping and explicitly mark
  external-domain targets as deferred. They never move into another domain.
- Apply preserves original bytes and mode in a Workspace rollback package,
  uses atomic replacement for frontmatter writes, and performs same-volume
  renames for internal inbox moves. Signals are not silently appended; the
  Workspace manifest is the mutation receipt.

## Acceptance

1. Unit tests prove plan determinism and all failure guards.
2. A real read-only canary over the current concept and inbox scopes succeeds
   with truthful aggregate output and no Documents mutation.
3. A fresh consumer audit has zero forbidden executors and zero unmatched
   consumers before physical quarantine.
4. The two legacy scripts are moved to protected Workspace quarantine with
   source/target hash, mode, byte, and rollback evidence. No other learning
   runtime family is terminalized.
