---
schema_version: specification/v1
spec_version: 1.0.1
title: ZCode durable client-state relocation
bet_id: BET-Y1Q3-T10-104
status: accepted
lifecycle: contract
owner: governance-team
created: 2026-08-30
last_updated: 2026-08-30
type: ssot
last_updated: 2026-09-03
---

# ZCode durable client-state relocation

## Intent

Remove the active ZCode client state from Documents so the Documents tree can
remain a content and contract plane. Reuse ZCode 3.10.1's native
`dataBaseDir` contract and place the complete active `.zcode` state under a
durable macOS application-data root outside both Documents and the Workspace
repository. Workspace owns the migration capability and evidence, not the
client's long-lived data.

## Architecture decision

- Source data root:
  `/Users/xiamingxing/Documents/ZCode/.zcode`.
- Durable configured base directory:
  `/Users/xiamingxing/Library/Application Support/ZCode Data`; ZCode appends
  the fixed `.zcode/v2` suffix.
- Durable recovery root:
  `/Users/xiamingxing/Library/Application Support/ZCode Recovery/2026-08-30`.
- Bootstrap setting:
  `/Users/xiamingxing/.zcode/v2/setting.json::dataBaseDir`.
- Workspace owns the migration command and governed report. ZCode remains the
  sole runtime owner of the relocated state; rollback payloads and manifests
  live under the durable recovery root, not Workspace `runtime/`.
- The app must be quiescent. The transaction must reject any ZCode process,
  open source handle, target collision, insufficient disk space, setting drift,
  or incomplete critical-state inventory.
- Phase A copies the complete source into a sibling temporary target, verifies
  inventory and critical fingerprints, atomically publishes the target, then
  atomically updates only `dataBaseDir`. The Documents source remains intact.
- Phase B restarts ZCode, proves target database handles and continuity, then
  finalizes by moving the now-unused Documents source into the durable recovery
  root. No symlink or partial-file migration is allowed.

## Complete state set

The transaction covers the entire source `.zcode` directory, including the
SQLite database and WAL/SHM sidecars, sessions, logs, checkpoints, crash data,
certificates, credentials, agent configuration, plugin workspace, and default
workspace. The tool records source inode/device, byte and file counts, critical
path metadata, and the settings backup before mutation.

## 1.0.1 incident amendment

The 1.0.0 attempt moved the state first into Workspace `runtime/`. Sixteen
seconds after a green restart verification, an un-attributed external cleanup
unlinked the database, credentials, certificates, sessions, checkpoints, crash
state, and workspace directories while ZCode still held link-count-zero
database handles. Workspace `runtime/` is therefore falsified as a durable
client-state owner. The specific deleting process is `UNPROVABLE` from retained
logs; consumer audit and ZCode's user-confirmed clear-all path were both
excluded as causes.

Before any restart, recovery must preserve the healthy native CLI database by
SQLite online backup and retain the pre-existing native v2 state, surviving
target files, settings backup, and transaction manifest under the durable
recovery root. Incident recovery may rebuild the desktop index from those
durable sources; it must never claim the purged payload was fully recovered.

## Non-goals

- No provider, model, MCP server, task, session, credential, or application
  feature change.
- No silent overwrite or deletion of the older native `~/.zcode/v2` state set;
  incident recovery consumes only a separately copied recovery snapshot.
- No migration of Electron browser state under
  `~/Library/Application Support/ZCode`.
- No long-lived client state under Workspace `runtime/`.
- No deletion of rollback evidence or claim of principal-bound value.

## Acceptance

1. A test-first Workspace transaction tool fails closed for an active app,
   missing SQLite sidecars, source/target drift, target collision, copy or
   fingerprint failure, insufficient disk space, and malformed settings.
2. Preflight proves the current active source, native setting, process/open-file
   state, complete critical inventory, and an absent target.
3. With ZCode quiescent, apply copies and verifies the complete source before
   atomic target publication, preserves unrelated settings, writes a durable
   rollback manifest, and sets the exact App Support base directory while
   retaining the Documents source.
4. After restart, ZCode opens the relocated SQLite/WAL/SHM and crash/state paths,
   no process or file handle references `Documents/ZCode/.zcode`, and the
   task/session state remains visible. Finalize then moves the retained source
   into durable recovery so Documents has no client-state descendants.
5. Documents consumer audit remains green and a stable full-tree L4 audit no
   longer fails because ZCode mutates the Documents root.
6. Incident recovery proves the CLI database backup with SQLite quick-check and
   exact session/message/part counts, records the purged subset honestly, and
   restarts from the durable target without relying on the deleted open inode.
7. Registry status, report, retro, tests, GaC, PR checks, merge, and mainline
   replay are complete. Value remains `NOT_PROVEN`.

## Rollback

Before finalize, quit ZCode, restore the settings backup, and restart against
the still-intact Documents source. After finalize, quit ZCode, verify the
manifest and recovery payload, restore the source from durable recovery, restore
the settings backup, and restart. Never delete the recovery payload as part of
rollback.
