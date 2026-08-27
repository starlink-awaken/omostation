---
status: archived
lifecycle: history
owner: unassigned
last-reviewed: 2026-08-27
---
# Accepted Workspace release evidence — 2026-08-27

## Release

- path: `$HOME/.local/share/omostation/accepted-20260827`
- root commit: `7dc90769b843f7bae3a9ea660eea79a41f534c2b`
- L4 child: `f3d697999cd1f0075338f79308f1de2c9ebbf31f`
- Runtime child: `3902785ddba2e9f69fe55bc1a74e6495ca359ef5`
- release is detached and used as a read-only source tree.

## Owner smoke

Against live `/Users/xiamingxing/Documents`:

- consumer audit: schema `documents.consumer-audit.v1`, status `violations`,
  exit 1, 191 active consumers / 12 unmatched;
- freshness audit: schema `documents.freshness-audit.v1`, status `findings`,
  exit 1, 12 missing review metadata;
- both produced Workspace-local evidence and no entrypoint/import error.

The release is now suitable as the code root for the two-line candidate schedule;
host installation remains a separate, explicitly verified operation.
