---
schema_version: specification/v1
spec_version: 1.0.0
status: accepted
lifecycle: contract
owner: human-principal
created: 2026-08-28
last_updated: 2026-08-27
bet_id: BET-Y1Q3-T10-36
risk_level: L1
type: ssot
last_updated: 2026-09-03
---

# Consumer audit execution-mode design

## Problem

The current consumer audit treats every reference to `~/Documents` as the same
kind of active consumer. That makes a Workspace-only owner such as
`controller-preflight --documents-root ~/Documents` indistinguishable from a
Documents-side executable and prevents a truthful zero-executor claim.

## Contract

Every consumer receives:

- `execution_mode`: `documents-executor`, `workspace-owner-read`, or
  `content-reference`;
- `writes_documents`: boolean;
- `forbidden_executor`: boolean, true only for an active command that executes
  a Documents runtime/script/tool/app path or writes a Documents state/output
  path.

The summary keeps `total`/`active` for compatibility and adds independent
counts for `forbidden_executors`, `workspace_read_owners`, and
`content_references`. Any active Documents executable remains a violation;
Workspace owners that explicitly read Documents content are not forbidden.

Classification is based on the command surface and source kind, not merely the
presence of a Documents path. A `--documents-root` argument paired with an
accepted Workspace owner is read-only. A direct command such as
`/usr/bin/python3 ~/Documents/@公共/_runtime/foo.py` is a forbidden executor.

## Acceptance

Existing audit JSON remains parseable, tests cover both positive and negative
classification cases, and live output can report `forbidden_executors=0` even
when read-only Workspace owners still consume Documents content.
