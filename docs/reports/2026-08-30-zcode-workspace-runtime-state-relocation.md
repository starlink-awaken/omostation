---
schema_version: report/v1
lifecycle: history
type: implementation-evidence
owner: governance-team
created: 2026-08-30
last_updated: 2026-08-30
bet_id: BET-Y1Q3-T10-104
---

# ZCode durable client-state relocation and recovery

## Outcome

ZCode 3.10.1 now uses its native `dataBaseDir` at
`/Users/xiamingxing/Library/Application Support/ZCode Data`. Active database,
WAL/SHM, workspace, and plugin handles are under that durable App Support root.
There are zero ZCode handles and zero descendants under `Documents/ZCode`.
Workspace owns the migration code and evidence only; it no longer owns the
long-lived client payload.

## 1.0.0 failure and root-cause boundary

The first attempt moved 161 files and 3,518,236,056 bytes into
`Workspace/runtime/clients/zcode-data`. A green live verify was written at
19:42:47. At 19:43:03 an external operation unlinked the desktop database,
WAL/SHM, credentials, certificates, sessions, checkpoints, crash state, and
workspace directories. ZCode retained link-count-zero database descriptors, so
the process continued temporarily.

The exact deleting process is `UNPROVABLE` from retained logs. Static and live
checks excluded the read-only consumer audit, the minute watcher, and ZCode's
user-confirmed clear-all path. The architectural cause is proven: Workspace
`runtime/` has cleanup semantics and is not an admissible durable application
data root.

macOS hardened runtime rejected debugger attachment to the distribution-signed
ZCode process, and no passwordless administrative path existed. The deleted
open desktop index could not be copied directly. This limitation is retained as
evidence, not hidden.

## Durable recovery

Before releasing the deleted open inode, the recovery transaction preserved:

- SQLite online backup of `~/.zcode/cli/db/db.sqlite`, SHA-256
  `6a0626fa5df7f72e8894b8f879be2810fb08782d2929080eaa295161f62b62ef`,
  `quick_check=ok`, with 171 sessions, 2,368 messages, and 6,273 parts;
- the pre-existing native v2 seed, its valid desktop task index, and 100 legacy
  session files;
- surviving logs and agent configuration;
- byte-identical settings backups and the failed-runtime transaction manifest.

The durable target was built in a sibling temporary directory, verified, then
atomically published. The seed index was valid before startup. ZCode was quit
through Computer Use, process quiescence was proven, and an exact-hash settings
CAS changed only `dataBaseDir`. After restart:

- the visible ZCode window returned;
- target SQLite/WAL/SHM and workspace/plugin handles were present;
- target `PRAGMA quick_check` returned `ok` and schema migration reached ten
  tables;
- the desktop index contains 143 tasks;
- the CLI recovery database still contains 171 sessions, 2,368 messages, and
  6,273 parts;
- consumer audit is `status=ok`, `forbidden_executors=0`, `unmatched=0`.

Recovery manifest:
`/Users/xiamingxing/Library/Application Support/ZCode Recovery/2026-08-30/durable-recovery-manifest.json`,
SHA-256 `234f786349367b7bab586531c100e0c412b17048cbfe53aecb0f3fb5b9d277d8`.
Recovery payloads remain in place and are not deleted by this BET.

## Honest loss boundary

`purged_payload_recovered=false`. The current pre-purge desktop index inode,
current desktop session snapshots, and the 3.2 GB git-checkpoint payload were
not recoverable. Message/session content is preserved in the healthy CLI DB,
and an operational desktop index was restored, but exact pre-purge desktop
equivalence is not claimed.

## Documents and engineering verification

- The full Documents L4 scan completed in one stability attempt with zero
  root-change findings. It remains non-green because of unrelated runtime,
  cache, archive-inventory, and symlink debt.
- The existing registered `documents-zcode-config.py` owner exposes
  `state-inspect/apply/verify/finalize/rollback`; no new `bin/` entry or CI
  workflow was added.
- The two-phase implementation keeps the Documents source until restart
  verification, then moves it into durable recovery on finalize.
- Focused tests cover process identity, active-handle rejection, complete-copy
  verification, insufficient disk, settings preservation, target database
  handles, protected-setting drift, finalize, and rollback.

B.D.S.K. remained `NOT_PROVEN` because the AetherForge compute hop was
unavailable. Principal-bound value remains `NOT_PROVEN`. This report proves the
durable client-state boundary, operational recovery, known-loss accounting, and
Documents write-path removal.

## Mainline closure

Spec 1.0.1 merged through PR #2745. The final implementation and incident
evidence merged through PR #2750 as
`8737b24a14e2de4ca68116a3f5b52f4e2c905c18`. Its initially inherited
capability projection blocker was repaired independently by T10-107 / PR #2753
as `53483be5644444cb0f27b5553a8e469207016929`; #2750 then passed its complete
second CI run.

Fresh mainline replay at closeout preserved `status=relocated`, five target
handles, zero source handles, consumer `forbidden_executors=0` and
`unmatched=0`. The App Support process had remained healthy for 49 minutes 27
seconds with all critical paths present and no link-count-zero target files.
Focused tests were 39/39 and GaC was 57/57 blocking checks green.
