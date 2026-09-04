---
type: ephemeral
created: 2026-09-03
---

# Accepted Workspace release evidence — 2026-08-28 refresh

## Release

- path: `$HOME/.local/share/omostation/accepted-20260908`
- root commit: `c5187900d4ae77e16631c512571cdb82a35dcafb`
- L4 child: `f3d697999cd1f0075338f79308f1de2c9ebbf31f`
- Runtime child: `3902785ddba2e9f69fe55bc1a74e6495ca359ef5`
- release is detached and used as a read-only source tree.

## Owner smoke

Against live `/Users/xiamingxing/Documents`:

- consumer audit: schema `documents.consumer-audit.v1`, status `ok`, exit 0,
  191 active consumers / 0 unmatched / 0 forbidden executors;
- freshness audit: schema `documents.freshness-audit.v1`, status `findings`,
  exit 1, 12 missing review metadata and no execution error;
- both produced Workspace-local evidence and no entrypoint/import error.

The release is clean, detached, and contains the same owner entrypoint hashes as
the current root main for consumer audit, freshness owner, and the shared owner
wrapper. It is suitable as the code root for the two-line candidate schedule;
host installation remains a separate, explicitly verified operation.
