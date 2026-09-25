---
type: execution-environment-snapshot
status: evidence
captured_at_utc: '2026-09-20T08:46:45Z'
projection_generated_at_utc: '2026-09-20T08:45:54.193215Z'
---

# Agent OS execution environment snapshot — 2026-09-20T08:46Z

## Verdict

A1–A9, RF0, and RC-DL are all `PASS`. `code_root_health` is now `PASS`, so
`OMO_SINGLE_CONTROL_PLANE` is also `PASS`. Claims remains healthy in shadow at
`435/1440` samples with `0` errors and max gap `60.37s`. Business value remains
`NOT_PROVEN` at `0/30` qualifying v2 samples.

## Managed code-main alignment

The deployment root advanced from `22ee77d...` to `25adbd70...` by a safe
registry stash + `merge --ff-only origin/main` + registry pop. Three clean
submodule checkouts were restored to their exact superproject pins. Scheduler
replay remains `drift=0`, `orphan=0`, with one known external orphan.

## Projection incident

An intermediate generation with origin/main's unpatched collector exposed the
known T10-170 gap by projecting prior-attempt history as an invalid gap. The
already-deployed patched host collector was used to restore the correct
current-run projection. This incident strengthens, but does not replace, the
case for exact T10-170 approval and merge.
