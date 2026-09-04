---
schema_version: report/v1
lifecycle: evidence
type: implementation-evidence
owner: governance-team
created: 2026-08-29
last_updated: 2026-08-29
bet_id: BET-Y1Q3-T10-65
---

# Documents terminal receipt gap

## Observation

On 2026-08-29, a read-only host check confirmed that all eight source paths
listed by `root-oneoff-assets` are absent from `/Users/xiamingxing/Documents`.
The historical rollback reference
`/Users/xiamingxing/Workspace/runtime/quarantine/documents-root-oneoff-20260829/manifest.json`
is absent, and the checked Workspace runtime/quarantine and local backup roots
contain no matching manifest or payload.

This is not sufficient evidence for physical retirement. The family is kept at
`pending` until a fresh, hash-valid rollback package is recovered or a new
physical transaction is independently authorized and verified.

## Guard delivered

`bin/gac/documents-content-plane-migration-check.py` now checks every complete
`verified` or `retired` family evidence block. Its `rollback_ref` must resolve
to a regular, non-symlink file; otherwise the checker fails closed and names the
family and unresolved reference. Non-terminal families retain their existing
coverage behavior.

No Documents content, runtime state, schedule, LaunchAgent, client
configuration, or missing payload was changed or reconstructed by this BET.

## Verification boundary

- A missing terminal receipt is covered by a regression test and fails.
- A real receipt is covered by the positive-path test and passes.
- The current main registry is valid after `root-oneoff-assets` is restored to
  `pending`; terminal retirement remains unproven.
- The previously merged retirement PR is no longer able to pass the migration
  checker if it points at the missing manifest.
