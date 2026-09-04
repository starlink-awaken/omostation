---
schema_version: specification/v1
spec_version: 1.0.0
status: accepted
lifecycle: contract
owner: human-principal
created: 2026-08-29
last_updated: 2026-08-29
bet_id: BET-Y1Q3-T10-88
risk_level: L2
human_gate: true
type: ssot
last_updated: 2026-09-03
---

# Documents Weijian cleanup script runtime quarantine

## Decision

Extend the existing `documents_runtime_quarantine.py` owner to accept one
audited regular file as its source, then move only
`~/Documents/@工作文档/卫健委/cleanup-commit.sh` into a protected Workspace
quarantine. Preserve the file bytes and metadata in the rollback manifest.

## Exact scope

- Source file: `~/Documents/@工作文档/卫健委/cleanup-commit.sh` only.
- Selection: stable L4 classification of exactly one regular `runtime` file;
  no directory-wide inventory or neighboring `_storage` scripts may enter the
  plan.
- Target: `~/Workspace/runtime/quarantine/documents-weijian-cleanup-20260830`.
- The owner must enforce lexical containment, reject source symlinks, preserve
  file mode/hash, and retain the existing rollback-on-verification-failure
  behavior.
- Fresh consumer evidence must be `status=ok` with zero forbidden executors
  and zero unmatched consumers.

## Acceptance criteria

1. RED test proves the owner accepts only a single regular runtime file and
   rejects any source expansion or symlink.
2. GREEN implementation supports a single-file source without weakening the
   existing directory and dangling-symlink behavior.
3. Host preflight and postflight prove exact source absence, target hash/mode
   parity, manifest retention, and adjacent health/work content preservation.
4. The final `work-runtime` regular-runtime globs are physically clear while
   other migration families remain independently pending.

## Non-goals

No movement outside the named file, no directory-wide scan, no `_storage`
script movement, no content/contract/cache/schedule/client/public-runtime
change, and no family-level retirement outside the verified work-runtime
family transition.
