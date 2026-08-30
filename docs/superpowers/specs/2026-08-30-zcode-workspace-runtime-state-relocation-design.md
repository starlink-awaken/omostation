---
schema_version: specification/v1
spec_version: 1.0.0
title: ZCode Workspace runtime state relocation
bet_id: BET-Y1Q3-T10-104
status: accepted
lifecycle: contract
owner: governance-team
created: 2026-08-30
last-reviewed: 2026-08-30
---

# ZCode Workspace runtime state relocation

## Intent

Remove the active ZCode client state from Documents so the Documents tree can
remain a content and contract plane. Reuse ZCode 3.10.1's native
`dataBaseDir` contract and place the complete active `.zcode` state under
Workspace's ignored runtime plane, without merging it into the older native
`~/.zcode/v2` state set.

## Architecture decision

- Source data root:
  `/Users/xiamingxing/Documents/ZCode/.zcode`.
- Native configured base directory:
  `/Users/xiamingxing/Workspace/runtime/clients/zcode-data`; ZCode appends the
  fixed `.zcode/v2` suffix.
- Bootstrap setting:
  `/Users/xiamingxing/.zcode/v2/setting.json::dataBaseDir`.
- Workspace owns the migration transaction, manifest, and rollback evidence;
  ZCode remains the sole runtime owner of the relocated client state.
- The app must be quiescent. The transaction must reject any ZCode process,
  open source handle, target collision, cross-device move, setting drift, or
  incomplete critical-state inventory.
- Move the complete `.zcode` directory with one same-filesystem rename, then
  atomically update only `dataBaseDir`. Do not copy selected files, merge the
  old native state, or introduce a symlink.

## Complete state set

The transaction covers the entire source `.zcode` directory, including the
SQLite database and WAL/SHM sidecars, sessions, logs, checkpoints, crash data,
certificates, credentials, agent configuration, plugin workspace, and default
workspace. The tool records source inode/device, byte and file counts, critical
path metadata, and the settings backup before mutation.

## Non-goals

- No provider, model, MCP server, task, session, credential, or application
  feature change.
- No merge, overwrite, cleanup, or activation of the older 41 MB
  `~/.zcode/v2` state set beyond the single bootstrap `dataBaseDir` field.
- No migration of Electron browser state under
  `~/Library/Application Support/ZCode`.
- No deletion of rollback evidence or claim of principal-bound value.

## Acceptance

1. A test-first Workspace transaction tool fails closed for an active app,
   missing SQLite sidecars, source/target drift, target collision, cross-device
   movement, and malformed settings.
2. Preflight proves the current active source, native setting, process/open-file
   state, complete critical inventory, and an absent target.
3. With ZCode quiescent, apply atomically moves the entire source `.zcode`,
   preserves unrelated settings, writes a rollback manifest, and sets the
   exact Workspace runtime base directory.
4. After restart, ZCode opens the relocated SQLite/WAL/SHM and crash/state paths,
   no process or file handle references `Documents/ZCode/.zcode`, and the old
   task/session state remains visible to the application.
5. Documents consumer audit remains green and a stable full-tree L4 audit no
   longer fails because ZCode mutates the Documents root.
6. Registry status, report, retro, tests, GaC, PR checks, merge, and mainline
   replay are complete. Value remains `NOT_PROVEN`.

## Rollback

Quit ZCode and require zero source/target handles. Verify the manifest and
current target identity, atomically restore the saved settings file, then rename
the target `.zcode` directory back to the original Documents source. Restart
ZCode and verify that its handles return to the original source. Never merge
either state set during rollback.
