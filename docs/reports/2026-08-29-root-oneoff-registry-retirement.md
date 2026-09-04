---
type: ephemeral
created: 2026-09-03
---

# T10-59 root one-off registry retirement evidence

The physical `root-oneoff-assets` quarantine was completed under the earlier
T10-58 execution attempt and is revalidated here without another move. The
authoritative receipt is:

`/Users/xiamingxing/Workspace/runtime/quarantine/documents-root-oneoff-20260829/manifest.json`

- manifest schema: `documents-root-oneoff-quarantine/v1`
- manifest SHA-256: `sha256:ad1084bf3abb95bc870036d750b1a86192dbccd8b29e265980732a87da957142`
- targets: 8
- total bytes: 4,106,995
- source paths absent: 8/8
- source/target hashes equal: 8/8
- permanent deletion: `false`

Postflight revalidation showed:

- `/Users/xiamingxing/Documents/_inbox`: 110 content, 0 runtime, 0 cache,
  `stability_attempts=1`, `ok=true`;
- consumer audit: `status=ok`, `191 active`, `179 content-reference`, `12
  workspace-owner-read`, `0 forbidden_executors`, `0 unmatched`;
- the other migration families were not changed.

The registry update in this BET is limited to `root-oneoff-assets.status:
retired` and its required evidence fields. The quarantine package remains the
rollback source and is not eligible for permanent deletion in this BET.
