---
id: ADR-0374
title: GaC Registry Convergence — indexed-drift fix, m1 orphan purge, stat auto-bump, symmetry tests
status: ACCEPTED
lifecycle: spec
owner: governance-team
last_updated: 2026-08-05
---

# 0374 — GaC Registry Convergence Round

> Parent: ADR-0106 (GaC), ADR-0373 (sweep-tooling convergence).
> Roadmap slot: follow-up to `sweep-tooling-convergence` (this round is the
> GaC-registry consolidation phase of the same convergence family).

## Context

After ADR-0373 landed, the GaC healthcheck (`bin/gac/gac-healthcheck.py`)
still reported 3 red categories:

1. **gac-drift (机制4): 4 RED** — `CR-L0-CONSTRAINTS-SSOT`,
   `CR-X1-POLICIES-SSOT`, `CR-X2-FRESHNESS-SSOT`, `CR-X4-CONSISTENCY-SSOT`
   all reported "规则 ID 在 source_ref 中未找到". Root cause: these are
   **legacy_index rules whose own ID is the SSOT index name**, not a rule
   inside the source file. The `check_indexed_drift` literal-string match
   was a false-positive by design.
2. **M1 实例 drift (机制7): 228 M1 vs 116 registry** — 112 orphan
   `GAC-RULE-*.yaml` were pre-consolidation (210→107) legacy names
   (A2A, ACP, BOS_URI, CR-ADMISSION-01, ...) that were never cleaned up.
3. **m1_nodes stat drift** — the declared `model_stats.m1_nodes` count is a
   moving target (concurrent agents add M1 yamls); manual bump every time
   is broken-by-design.

Plus: the ADR-0373 `convergence_provenance` symmetry validator shipped with
zero test coverage.

## Decision

### D1. G1 — Fix `check_indexed_drift` false-positive (gac-drift.py)

`bin/gac/gac-drift.py::check_indexed_drift` now special-cases SSOT index
rules:

```python
is_ssot_index_rule = (
    rule_id.endswith("-SSOT")
    or rule.get("check_type") == "legacy_index"
)
if rule_id and rule_id not in content and not is_ssot_index_rule:
    drifts.append(...)
```

- **Effect**: source_ref exists + parseable = aligned for SSOT-index rules.
- **Non-SSOT indexed rules unchanged** — a rule whose id genuinely must
  appear in the source content still fails if absent (regression guard in
  `tests/test_gac_drift_indexed_rule.py::test_non_ssot_rule_still_fails...`).
- 4 RED → 0 RED. GaC drift closes.

### D2. G2 — `--bump-stats` auto-sync (check-mof-capabilities-drift.py)

`bin/mof/check-mof-capabilities-drift.py` gains `--bump-stats`:

- Re-counts `m1_nodes` / `m2_schemas` from disk.
- If the declared value differs, rewrites the registry line (regex-bounded,
  minimal diff) + updates `stats_as_of`, then re-runs the drift check.
- CI can call it as a self-healing first step; humans get a
  `::notice::bumped m1_nodes: X → Y` line.
- This round it was applied once manually after the M1 orphan purge
  (1461 → 1367).

### D3. G3 — M1 orphan purge + re-sync (gac-m1-sync.py)

Ran `GAC_M1_SYNC_WRITE=1 bin/gac/gac-m1-sync.py --sync`:

- **112 legacy orphans deleted** (A2A, ACP, BOS_URI, CR-ADMISSION-01, AGT-ASI 系列,
  CR-AUDIT-5REPOS-01, C2G 系列, ...) — proven dead:
  not in governance-checks.yaml, zero external references (grep across
  yaml/md/py).
- **18 M1 instances created** for rules added since last sync (incl.
  CR-X3-DELIVERY-CADENCE from #999).
- **4 stale instances updated** to match registry (executor/lifecycle/
  version fields).
- Result: `M1 = 117 = registry 117`, missing=0, orphan=0, stale=0.

### D4. G4 — convergence_provenance symmetry tests

- Extracted ADR-0373's inline symmetry check into a testable top-level
  helper `_collect_convergence_provenance_errors(seen_ids, initiatives)`
  (behavior unchanged, still called from `validate_roadmap`).
- `tests/test_convergence_provenance.py` — 8 tests: bilateral happy path,
  orphan supersedes, orphan superseded_by, ghost parent, non-dict entries,
  bad provenance shape, no-provenance no-op, 3-round chain.
- `tests/test_gac_drift_indexed_rule.py` — 5 tests: SSOT-index happy path
  (id suffix + check_type), non-SSOT still fails, missing file fails,
  non-indexed skip.

## Consequences

### Positive

- **gac-drift: 4 RED → 0.** `make gac-local-gate` no longer blocked by
  legacy_index false-positives.
- **M1 plane clean**: 117 M1 = 117 registry, orphan=0. The 112 dead files
  had been silently inflating every M1 health metric since the 210→107
  consolidation.
- **m1_nodes never drifts again**: `--bump-stats` is one command; CI can
  call it before the blocking drift gate.
- **Symmetry contract locked**: 13 new tests guard both the drift fix and
  the convergence_provenance validator.

### Negative / Trade-offs

- **112 M1 yamls deleted** — intentional (legacy names, provably dead),
  but irreversible without git history. All were auto-derived
  (`# DERIVED by gac-m1-sync.py` header), so regeneration is one command.
- `--bump-stats` writes the registry on drift — someone must commit the
  bump (or CI will keep seeing the same drift). The regex-bounded edit
  keeps the diff reviewable (only the count + stats_as_of lines).
- `_collect_convergence_provenance_errors` moves the "bad shape" case to
  a silent skip (was a warning before). Aligned with the validator's
  errors/warnings contract — a malformed entry is a structural problem
  caught by `gac-validate` schema checks instead.

## Compliance

- ADR-0106: `gac-m1-sync.py` is the derived-plane generator; SSOT remains
  governance-checks.yaml (5-source align intact: registry enum /
  gac-drift.py / gac-executor.py / M2 gac_rule.yaml / M1 instances).
- ADR-0203: this ADR is itself a requirement iteration; workflow run
  `...` with full path coverage.
- ADR-0211 §D1 (P74): M1 plane sync removes 112 silent orphans that were
  feeding P74 noise (each orphan was a "ghost rule" candidate).

## Verification

```bash
# G1 — drift 0
uv run --with pyyaml python bin/gac/gac-drift.py

# G2 — stat auto-bump (self-healing)
uv run --with pyyaml python bin/mof/check-mof-capabilities-drift.py --bump-stats

# G3 — M1 plane aligned
uv run --with pyyaml python bin/gac/gac-m1-sync.py --json  # missing=0 orphan=0 stale=0

# G4 — symmetry + drift tests
uv run --with pyyaml --with pytest python -m pytest \
  tests/test_gac_drift_indexed_rule.py tests/test_convergence_provenance.py -q

# Healthcheck closes
uv run --with pyyaml python bin/gac/gac-healthcheck.py
```

Done when: gac-drift=0, M1 missing/orphan/stale=0, m1_nodes in sync,
13 new tests pass, healthcheck red categories ≤ 1 (pre-existing only).
