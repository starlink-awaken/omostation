---
schema_version: report/v1
lifecycle: history
type: implementation-evidence
owner: governance-team
created: 2026-08-29
last_updated: 2026-08-29
bet_id: BET-Y1Q3-T10-92
---

# OPC runtime tools quarantine — implementation evidence

## Scope and preflight

The scoped L4 audit of `/Users/xiamingxing/Documents/@OPC` was stable and
selected exactly two `runtime` artifacts: `cmm.sh` and
`setup-codebase-memory-mcp.sh`. It selected no cache or invalid archive. A
fresh consumer audit returned `status=ok`, with 191 active observations,
`forbidden_executors=0`, `unmatched=0`, and no active consumer for either
selected filename.

## Physical transaction

The existing `documents_runtime_quarantine.py` owner moved the two files to:

`/Users/xiamingxing/Workspace/runtime/quarantine/documents-opc-tools-20260830/`

Manifest SHA-256:
`sha256:116dc7e12e9f6bafd4d878f05b9ae6847de06bebcfa2bca63e69197f6111f05f`.
The manifest records two files and 6403 bytes, preserves their original mode
and SHA-256 values, and declares `permanent_deletion=false`.

Source and target tree fingerprint:
`sha256:26102e4e70a990528e847e285e1955e72b63868cd749892c2e3ca383d5ea7ab7`.

## Postflight

Both original OPC runtime paths are absent, while the two quarantine targets
match the preflight bytes, sizes, and modes. A second stable L4 audit reports
OPC runtime/cache zero while retaining the OPC content, contract, and
projection artifacts. Sample non-target `DOMAIN.yaml`, `CLAUDE.md`,
`_control/STATE.md`, and `_entities/facts.md` hashes remained available and
were not moved.

## Boundary and next state

This transaction advances `opc-tools` only to `in_progress`. It proves a
recoverable physical quarantine and no active consumer, but it does not prove
that a Toolbox or Workspace setup owner has been installed. The quarantine
manifest is the rollback reference until owner parity and pointer-only
Documents guidance are separately accepted.
