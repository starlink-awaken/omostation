---
schema_version: report/v1
status: active
lifecycle: history
type: implementation-evidence
owner: governance-team
created: 2026-08-30
last-reviewed: 2026-08-30
bet_id: BET-Y1Q3-T10-75
---

# Evidence smoke relative-script resolution — implementation evidence

## Root cause

`bin/gac/evidence-smoke.py` classified a direct `.py` argument relative to the
Workspace root even when the service command declared `--directory`. The real
command contract is `uv run --directory projects/omlxc python examples/<file>.py`,
so the checker reported five false `script not found` gaps for valid OMLXC
commands.

## Implementation

The L2 resolver now joins a relative direct script to the declared directory.
Absolute paths keep their existing behavior, and commands without
`--directory` remain Workspace-relative. No BOS declaration or runtime command
was changed.

## Verification

- RED: the new directory-relative regression test failed against the old
  resolver (`1 failed, 2 passed`).
- GREEN: `tests/test_evidence_smoke_paths.py` passed `3 passed`.
- Ruff: `bin/gac/evidence-smoke.py` and its focused tests passed.
- Syntax: both files compiled successfully.
- Integration: against Agora main `61af943334f120938f6ad79eda83fbe1535a1405`,
  all five OMLXC declarations resolved `True` using the existing
  `projects/omlxc/examples` files.
- The real relative command `uv run --directory projects/omlxc python
  examples/live_v5_evolution_verification.py --help` exited `0`; the
  root-relative variant exited `2`, confirming the declaration must remain
  directory-relative.

## Known boundary

This slice does not update the Workspace `projects/agora` gitlink. The root
integration remains a separate T10-74 delivery and must land together with this
checker fix before the root evidence gate can be re-run as a clean mainline
claim.
