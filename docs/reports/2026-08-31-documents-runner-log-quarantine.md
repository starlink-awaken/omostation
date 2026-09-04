---
lifecycle: history
owner: governance-team
created: 2026-08-30
last_updated: 2026-08-30
title: T10-110 Documents runner-log exact quarantine report
type: doc
---

# T10-110 Documents runner-log exact quarantine report

## Outcome

Exactly two retired machine logs were moved from Documents into the existing
recoverable integration Workspace quarantine:

`/Users/xiamingxing/Workspace/runtime/quarantine/documents-root-inbox-runner-logs-20260831`

The transaction retained an immutable completed manifest and an executable
verify/rollback path. It did not move or alter any other `_inbox` content and
performed no permanent deletion.

## Authoritative delivery

- T10-109 classifier closeout: root PR #2771, merge
  `30b0bac900d5a14d1259e9b91afbd6c7148d7c91`.
- T10-110 design/BET bootstrap: root PR #2772, merge
  `68c4b32f7b41b5fd8ed30a44233b1de0b3a53285`.
- T10-110 capability: root PR #2773, merge
  `700e23f9cfc5fd9bdb3f0aff78bfe2e6898b5c89`.

The capability branch and merged main tree were both
`9a03291feb48ee225729d9aa48440df1fe78ad22`, and capability tests/GaC were
replayed from that equal tree before host mutation.

## TDD and capability verification

Before production edits, 14 legacy tests passed and six new tests failed because
exact inventory, CLI options, verification, and rollback did not exist. A
separate boundary test then failed because a forged outside-Documents source
path was accepted by manifest verification. Production changes were made only
after those RED results.

The merged capability passed 21 quarantine/retention tests, Ruff lint, system
Python 3.9.6 compilation, migration-registry validation, doc SSOT, SSOT
guardian, GaC, AI review, and all required PR checks. Existing whole-file Ruff
format debt in two touched legacy files was replayed from main and not expanded.

## Host preflight

The host run was `20260830T184151Z-bet-execution-af677b34`. A fresh consumer
receipt reported `status=ok`, `forbidden_executors=0`, and `unmatched=0`.

Both sources were regular mode-`0644`, zero-byte files with SHA-256
`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.
Two independent `lsof` checks were empty. Crontab, LaunchAgent, Claude
Scheduled, and process scans found no active consumer. The target was absent
and matched the existing `runtime/quarantine/*/` policy.

Two fixed-time plans were byte-identical. They selected exactly
`hourly_runner.log` and `hourly_runner_err.log` as cache, with summary
`files=2`, `bytes=0`, and selected fingerprint
`sha256:7a754429822f7ea9b807bd56f0da57fb789d7907eb114bf321fb7e53082918cb`.

The non-target guard covered 109 files and 1,081,993 bytes with fingerprint
`sha256:07e392c19d1a690f1f9a732f89b40dfb6735cd5adcd204cd6e76caea6ed77888`.

## Apply and postflight

The merged main capability applied once at `2026-08-31T03:05:00+08:00`.
Completed source and target fingerprints were equal to the planned fingerprint;
the non-target fingerprint remained equal. Both source paths are absent. Both
target files retain zero bytes, mode `0644`, the empty-file hash, original
inodes, and original mtimes.

Manifest:

`/Users/xiamingxing/Workspace/runtime/quarantine/documents-root-inbox-runner-logs-20260831/manifest.json`

Manifest SHA-256:

`sha256:33ddd787f1536c9a91970fcc375e2449896e542d6f1855132887ae6e40170b49`

Two completed-manifest verification receipts were byte-identical across the
full-tree audit delay. They report `status=verified`, exact source/target
fingerprints, `sources_absent=true`, `rollback_available=true`, and
`permanent_deletion=false`.

The postflight consumer audit remained green. A stable one-attempt full
Documents L4 audit remained non-green from unrelated debt: cache 36,867,
runtime 4,907, invalid archive 31,448, and 73,223 total violations. This is
evidence that the two cache artifacts were removed without claiming global
physical purity.

## Registry and rollback boundary

`root-oneoff-assets` receives only this completed transaction. The family
remains `pending`; its broad `_inbox/**` scope, unrelated root assets, and
historical missing eight-file rollback package are unchanged.

Rollback was not executed. It remains available through the merged manifest
command and is gated by target equality and source collision checks. A rollback
would restore both sources, preserve the completed manifest, and write a
separate fsynced rollback receipt. No delete or force mode exists.

## Verdict

- Engineering: `VERIFIED`.
- Exact host relocation: `PROVEN`.
- Non-target `_inbox` preservation: `PROVEN`.
- Root-oneoff family retirement: `NOT_PROVEN` and still pending.
- Principal-bound value: `NOT_PROVEN`.
- Documents-wide physical purity: `NOT_PROVEN`.
