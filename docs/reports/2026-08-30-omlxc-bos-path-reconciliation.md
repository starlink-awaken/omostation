---
schema_version: report/v1
lifecycle: history
type: implementation-evidence
owner: governance-team
created: 2026-08-29
last_updated: 2026-08-29
bet_id: BET-Y1Q3-T10-74
---

# OMLXC BOS service path reconciliation — implementation evidence

## Scope

The five active OMLXC BOS declarations were reconciled to the canonical
`projects/omlxc/examples` scripts. URI names, actions, transport, security,
runtime behavior, and hardware execution were not changed.

## Evidence

- Agora PR #46 is merged at child main commit
  `61af943334f120938f6ad79eda83fbe1535a1405`; PR #47 and its tracker PR #49
  are merged, with child main now at
  `a4c65b305df1b2718489e36a49dd52dae2b4c9b9`.
- The root `projects/agora` gitlink points to the reachable child main commit
  `a4c65b305df1b2718489e36a49dd52dae2b4c9b9`.
- `tests/test_omlxc_bos_path_resolution.py` passes in the child repository.
- The five OMLXC declarations resolve against existing example files when the
  checker uses the command's `--directory projects/omlxc` context.
- The three legacy cache/dflash/cluster demo routes are explicitly
  `unimplemented` and therefore excluded from the routable POC table until
  canonical CLI parity exists; the full L2 gate reports `249/249` and
  `real_gap=0`.
- The actual relative command
  `uv run --directory projects/omlxc python examples/live_v5_evolution_verification.py --help`
  exits `0`; using a root-relative script argument exits `2`.
- The root evidence checker fix is imported from the independently verified
  T10-75 slice and is included in this integration surface.

## Boundary and remaining baseline

No Documents content or runtime payload was changed. The independently owned
OMO state projection is now reconciled in the same root integration: planned
`6`, total `298`, with coherence and SSOT guardian green. The only known
pre-existing ledger lint issue is the missing T10-71 Spec on origin/main; it is
unrelated to OMLXC route reachability.
