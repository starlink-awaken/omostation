---
schema_version: report/v1
status: active
lifecycle: history
type: implementation-evidence
owner: governance-team
created: 2026-08-29
last-reviewed: 2026-08-29
bet_id: BET-Y1Q3-T10-74
---

# OMLXC BOS service path reconciliation — implementation evidence

## Scope

The five active OMLXC BOS declarations were reconciled to the canonical
`projects/omlxc/examples` scripts. URI names, actions, transport, security,
runtime behavior, and hardware execution were not changed.

## Evidence

- Agora PR #46 is merged at child main commit
  `61af943334f120938f6ad79eda83fbe1535a1405`.
- The root `projects/agora` gitlink points to that reachable child main commit.
- `tests/test_omlxc_bos_path_resolution.py` passes in the child repository.
- The five OMLXC declarations resolve against existing example files when the
  checker uses the command's `--directory projects/omlxc` context.
- The actual relative command
  `uv run --directory projects/omlxc python examples/live_v5_evolution_verification.py --help`
  exits `0`; using a root-relative script argument exits `2`.
- The root evidence checker fix is imported from the independently verified
  T10-75 slice and is included in this integration surface.

## Boundary and remaining baseline

No Documents content or runtime payload was changed. The root main baseline
still has an unrelated missing T10-71 Spec reference and state-governance
drift; those remain separate evidence items until their owning deliveries land.
