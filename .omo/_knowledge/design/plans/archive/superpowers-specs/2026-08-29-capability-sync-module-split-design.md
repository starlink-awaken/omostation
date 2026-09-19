---
schema_version: specification/v1
spec_version: 1.0.0
title: Capability-sync verification helper split
bet_id: BET-Y1Q3-T10-60
status: accepted
lifecycle: contract
owner: governance-team
created: 2026-08-29
last-reviewed: 2026-08-29
type: ssot
last_updated: 2026-09-03
---

# Capability-sync verification helper split

## Intent

Reduce the canonical `bin/capability-sync.py` compatibility CLI below the
repository's hard god-module threshold by extracting only its bounded
verification helpers into `lib`. The CLI remains the public entrypoint and
keeps its existing callable names and receipt shapes.

## Constraints

- No new registry writer, dispatcher, provider, authority, or execution path.
- Preserve exact CLI exit codes, JSON schemas, redaction, Python 3.9
  compatibility, and import-by-path behavior.
- Keep `bin/ssot/gen-capability-registry.py` as the sole projection writer.
- Update the generated capability projection only through that canonical
  generator; no hand-edited generated content.
- Do not change capability IDs, discovery semantics, admission, or native
  receipt fields.

## Acceptance

- `bin/capability-sync.py` is at or below 1,500 lines and the god-module check
  no longer reports it as an error.
- Existing capability-sync, native inspection, native receipt, and trace
  binding tests pass, including the Python 3.9 import/probe path.
- `make check-capability-registry` passes after canonical projection sync.
- The extracted helper is a library-only boundary with no second control plane.
