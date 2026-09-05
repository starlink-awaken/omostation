---
id: ADR-0375
title: Legacy Rule Plane Convergence — container-semantics drift fix + project-registry sync
status: ACCEPTED
lifecycle: spec
owner: governance-team
last-reviewed: 2026-08-05
type: ssot
---

# 0375 — Legacy Rule Plane Convergence Round

> Parent: ADR-0106 (GaC), ADR-0374 (GaC registry convergence), ADR-0121 (GCSI).
> This round closes the `legacy-drift` red reported by `gac-healthcheck`
> (源=105 indexed=5 missing=104 ghost=4) and the `registry-drift` red
> (cockpit version bump not synced).

## Context

`gac-healthcheck.py` reported two remaining reds after ADR-0374:

1. **legacy-drift: 源=105 indexed=5 missing=104 ghost=4** — `gac-ingest-legacy.py
   ::check_drift` computed a set-difference between the **concrete rule IDs**
   inside the 4 legacy source files (X1/X2/X4 policies + L0 constraints,
   105 rules total) and the **container rule IDs** registered in
   governance-checks.yaml (5 `source_type: indexed` rules). But after P79
   consolidation, each legacy *file* is represented by exactly one
   `CR-*-SSOT` container rule (its own id is the *index name*, not a rule
   inside the file). The per-rule set-diff therefore always reports
   105−1 = 104 "missing" and 5−1 = 4 "ghost" — a permanent false positive.
2. **registry-drift: cockpit.version 0.4.0 → 0.5.0** — a concurrent agent
   bumped cockpit's pyproject but did not regenerate
   `docs/project-registry.yaml` (SSOT for project metadata).

## Decision

### D1. G5 — Rewrite `check_drift` to container semantics

`bin/_archive/2026-08-gap-governance-s5/gac-ingest-legacy.py::check_drift` now validates at the **file**
level, matching how consolidation actually models the legacy plane:

| Field | Old (per-rule) | New (per-file) |
|-------|----------------|----------------|
| `missing` | 105 source rule IDs not in indexed IDs | legacy **source files** with no `CR-*-SSOT` container rule covering them |
| `ghost` | indexed IDs not in source rule IDs | indexed container rules whose `source_ref` points at a **deleted** legacy file |
| `ok` | both diffs empty | every legacy source covered + no dangling container |

Coverage test: an indexed rule `source_ref` equals (or prefixes) the
legacy source file path. Ghost test: `source_ref`'s path part lives under
`.omo/_truth/x*` or `projects/ecos/.../registry/` (the legacy trees) but
the file does not exist.

Live result: `ok=True, source_count=4, covered=4, missing=[], ghost=[]`.

### D2. G6 — Regenerate project-registry.yaml

`bin/mof/gen-project-registry.py --write` applied the pending
`cockpit.version 0.4.0 → 0.5.0` sync. `registry-drift` now passes.

### D3. G7 — Regression tests

`tests/test_ingest_legacy_drift.py` (6 tests):
- live registry has no drift (ok=True, 4/4 covered)
- LEGACY_SOURCES covers the 4 canonical files
- container rule covering file passes (unit, WORKSPACE-injected tmp)
- missing container rule flags source (unit)
- ghost container for deleted source (unit)
- CLI `--check --json` exits 0 on live registry

## Consequences

### Positive

- **legacy-drift: 104 missing + 4 ghost → 0/0.** The biggest structural
  debt in `gac-healthcheck` closes. The check now reflects the actual
  (consolidated) model instead of the pre-consolidation one.
- `legacy_count` remains the concrete rule count (105) for observability;
  new `source_count`/`covered_files` report the file-plane coverage.
- **registry-drift closes** with a one-command regen.

### Negative / Trade-offs

- The ghost heuristic only inspects the two known legacy trees
  (`.omo/_truth/x*`, `projects/ecos/.../registry/`). A container rule
  pointing at a deleted file elsewhere is not flagged. Acceptable:
  all 5 indexed rules currently point into those trees.
- Changing `check_drift` semantics means the historical
  "105 missing" number no longer appears; dashboards that relied on it
  must switch to `source_count`/`covered_files`.

## Compliance

- ADR-0106: legacy plane SSOT remains the 4 source files; GaC indexed
  rules are execution containers, not per-rule mirrors.
- ADR-0121 (GCSI): convergence lint now passes (0 ERROR).
- ADR-0374: continues the registry-convergence family (this round is
  the legacy-plane half; ADR-0374 was the GaC/M1 half).
- ADR-0203: this ADR is a requirement iteration; workflow run
  `20260805T...-pyright-sweep-...` with full path coverage.

## Verification

```bash
# G5 — legacy plane aligned
uv run --with pyyaml python bin/_archive/2026-08-gap-governance-s5/gac-ingest-legacy.py --check --json
#   {"ok": true, "source_count": 4, "covered_files": [...4...], "missing": [], "ghost": []}

# G7 — regression
uv run --with pyyaml --with pytest python -m pytest tests/test_ingest_legacy_drift.py -q

# G6 — registry plane aligned
uv run --with pyyaml python bin/mof/gen-project-registry.py   # 0 drift

# Healthcheck closes two more reds
uv run --with pyyaml python bin/gac/gac-healthcheck.py
```

Done when: `gac-ingest-legacy --check --json` ok=true,
`gen-project-registry` 0 drift, 6 new tests pass, healthcheck
legacy-drift + registry-drift both green.
