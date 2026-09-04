# P98 — Governance Surfaces Completeness

**Pattern observed**: 2026-09-04 in BET-Y1Q4-HITL-01 (PR #3077).

## Problem

`omo.cli governance surfaces` (used by `interface-check` CI) validates that every top-level directory under `.omo/` is registered in `.omo/_truth/registry/omo-governance-surfaces.yaml`. If a runtime directory (created by hooks, agents, or operational scripts) is not registered, the check fails.

## Symptom

```
omo.cli governance surfaces --workspace-root ../.. --json
   "issues": [
     "unregistered top-level asset: _inbox",
     "unregistered top-level asset: locks"
   ],
   "status": "error"
```

## Common Unregistered Runtime Dirs

- `.omo/_inbox/` — agent inbox
- `.omo/locks/` — clone-guard / git hooks locks
- `.omo/_log/` — already gitignored
- `.omo/_delivery/` — already gitignored
- `.omo/_archive/` — already registered

## Fix Pattern

Add an entry to `.omo/_truth/registry/omo-governance-surfaces.yaml`:

```yaml
- id: OMO-<NAME>
  ref: .omo/<name>/
  plane: state_plane
  asset_type: runtime_<name>
  persistence_mode: operational  # or "session_only"
  retention_mode: session_only   # or "manual_cleanup"
  truth_owner: governance
  write_via:
    - clone_guard
    - hook_scripts
  consumed_by:
    - clone_guard
    - git_hooks
  status: active
  runtime: true   # 标记为 runtime 生成的,豁免实际存在性检查
```

**Important**: `runtime: true` is honored by `omo_governance_surfaces_report.py:runtime_top_levels` to skip existence checks (CI fresh checkouts won't have these dirs).

Allowed values:
- `persistence_mode`: `operational`, `archival`, `ephemeral`, `projection`, `compatibility_alias`
- `retention_mode`: `until_replaced`, `manual_cleanup`, `rolling_window`, `append_forever`, `manual_archive`, `alias_only`, `session_only`

## When to Apply

- BEFORE adding a new top-level directory under `.omo/`
- AFTER `clone-guard` or new hooks create new runtime directories
- When `interface-check` fails with "unregistered top-level asset"

## Related

- `bin/ssot/omo-governance-surfaces.py` (validation script)
- `.omo/standards/omo-governance-surfaces.md` (canonical contract)
- `.omo/_truth/registry/omo-governance-surfaces.yaml` (SSOT)
