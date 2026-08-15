# omlxc model discovery current state — 2026-08-15

> **Trigger**: oMLX App model dir mispoint (e.g. `~/.local/share/omlxc/releases/v3.0.14/app-models`)
> left inventory silently collapsed. User-facing symptom: aliases such as
> `coding` / `coding-fast` still appear in `omlxc models list` while generation
> and routing treat them as gone.
> **Workflow**: `20260815T045424Z-project-doc-change-f0cfb7dc` (audit) +
> `20260815T045424Z-project-code-change-1ea09fa2` (omlxc implementation).
> **Scope**: investigate probe / diagnose / reconcile / models-list naming;
> lock the first inventory-drop PR. No disk scans, no App config edits, no new
> public ports, no AetherForge bypass.

## 1. What already exists

| Surface | Location | What it actually does |
|---|---|---|
| Periodic catalog probe | `CatalogProbe._run` / `_refresh` (`src/omlxc/daemon/composition.py`) | Default `probe_interval_seconds=10`. Calls adapter `discover()` + `list_models()`. Already covers “re-probe if missing”. |
| `omlxc nodes probe` | `ProductionControlService.probe_node` + CLI | Explicit node-scoped catalog refresh. No inference. |
| `omlxc nodes diagnose` | `diagnostics_for_node` + `NodeDiagnosticCode` | Aggregate catalog outcome (timeout / probe failed / available). No inventory baseline. |
| `omlxc models list` | `ProductionControlService.list_models` | **Config-canonical**: TOML `ModelSpec.id` + aliases, joined to placement snapshots. Not raw adapter IDs. |
| Cross-backend sameness | `PlacementConfig.backend_model_id` | Matches `adapter.list_models()` IDs. Naming unification is already this field. |
| `omlxc models reconcile` | `cli.models_reconcile` | `_unsupported`. Not a catalog repair path. |
| Autonomy reconcile loop | `autonomy/runtime.py` | Placement / load-unload, not adapter inventory. |
| Task 5 SQLite | `storage/database.py` `SCHEMA_VERSION=2` | `health_snapshots` is reachability/stale, **not** inventory. Exact-schema tests. |
| `omlxc doctor --direct` | `diagnostics.run_direct_doctor` | Store-free. CLI must not read the daemon DB. |

oMLX App `list_models()` already returns the library (`GET /v1/models`), including
unloaded entries. A mispointed App model dir therefore shows up as a much shorter
successful inventory, not as a probe failure.

## 2. Why aliases “disappeared” without a warning

`models list` enumerates configured model IDs and aliases regardless of adapter
library size. After a dir mispoint:

1. Adapter `list_models()` returns a small set (or empty).
2. Placement `backend_model_id` no longer hits `inventory`.
3. Snapshot `available` / `loaded` go false.
4. Config aliases (`coding`, `coding-fast`) remain in the list.
5. Routing / generation fail. Human sees “aliases are gone”.

That is an **availability** problem, not a naming/alias registry problem.

## 3. Real gap

There is no high-water vs current adapter inventory count.

- Backend fail / timeout already maps to stale + `PROBE_FAILED` / `TIMEOUT`.
- A **successful** probe of a wrongly-pointed but healthy App is not stale.
- `health()` only reports storage `ready` / `degraded`.
- `CatalogProbe` has no storage handle.

## 4. Locked first-PR contract

Decided in grill-me (Q1–Q6, all A):

1. High-water updates only on successful `discover()` + `list_models()` when
   `reachable` and `compatible`. First success seeds, no warning.
2. Backend fail / timeout = existing stale/circuit, **not** inventory drift.
3. WARNING auto-clears when the next healthy snapshot is not a >30% drop.
4. Count-only cliff: `current * 10 < high_water * 7`. No set-diff / names.
5. New table in the same Task 5 SQLite (`SCHEMA_VERSION=3`), not
   `health_snapshots`. Persist count only.
6. Surface: `health()["warnings"]` for `omlxc status` and `omlxc doctor`
   (non-`--direct`). Do **not** set `degraded`. Do **not** implement `--direct`
   comparison (CLI-no-DB).
7. Count unique adapter `list_models()` IDs, including unloaded-in-library.
   Do not count alias/config matches. Warning JSON has no model names.

```
inventory_high_water(node_id, backend_id, high_water_count, observed_at)
PK (node_id, backend_id)

warning = {
  "code": "inventory_drop",
  "node_id": ...,
  "backend_id": ...,
  "baseline": N,
  "current": M
}
```

## 5. Explicitly skipped (and why)

| Idea | Why skipped |
|---|---|
| New periodic probe scheduler | `CatalogProbe` already loops every `probe_interval_seconds`. |
| Unify `models list` to adapter IDs | List is config-canonical by design; sameness is `backend_model_id`. |
| Scan App model directories | Hard constraint: health only via adapter generation/inventory APIs. |
| Edit App config / model path | Human/App ownership. omlxc warns only. |
| doctor `--direct` vs high-water | Would force CLI to read SQLite. Forbidden. |

## 6. Leftovers

- Machines whose App model dir is **already** mispointed will seed a low
  high-water on first successful probe after upgrade. No warning until a later
  healthy cliff. Fix the App path by hand on those hosts.
- Set-diff / named missing models is a later PR if count-only is not enough.
- `models reconcile` remains `_unsupported`.
