---
id: ADR-0376
title: M1 tracked-truth convergence — health checks read git HEAD, not working tree
status: ACCEPTED
lifecycle: spec
owner: governance-team
last-reviewed: 2026-08-05
type: ssot
---

# 0376 — M1 Tracked-Truth Convergence Round

> Parent: ADR-0106 (GaC), ADR-0374 (GaC registry convergence).
> This round makes M1 consistency checks read the **merged commit state**
> (git HEAD / root pointer) instead of the `projects/ecos` working tree,
> which concurrent agents constantly pollute with untracked M1 nodes and
> branch switches.

## Context

After ADR-0374 aligned M1 = 117 = registry on the tracked state, the
`gac-healthcheck` #13 M1 check still reported red in live operation:

- **worktree mode: `missing=19, orphan=110`** — while the tracked state
  (ecos at `b931c5d`) was perfectly aligned (117/0/0). The 19 missing
  and 110 orphan were **untracked working-tree files** left by concurrent
  agents mid-round, not real drift.

Root cause: `gac-m1-sync.py` and `gac-healthcheck.py` enumerated
`projects/ecos/.../m1/governance/GAC-RULE-*.yaml` with `Path.glob`,
which reads the **working tree**. In a multi-agent workspace the working
tree of the ecos submodule is not a stable truth plane: agents checkout
their own branches (`ea0ad56` with 19-21 untracked M1) or leave
half-written derivations behind. Every concurrent round therefore
tripped a false health red on M1, masking the real signal.

Second finding: even on the clean tracked state, 3 rules were stale
(`executor` gained `ci_gate`, `lifecycle` draft→active,
`version` 0.1.0→1.0.0) because their registry entries were updated after
the ADR-0374 M1 sync. Count aligned, fields drifted.

## Decision

### D1. G8 — `gac-m1-sync.py --tracked` reads git HEAD

New `_tracked_m1_files()` enumerates `GAC-RULE-*.yaml` via
`git -C projects/ecos ls-tree -r --name-only HEAD` (excluding
`GAC-RULE-METAMODEL.yaml`), and `load_m1_nodes(tracked=True)` reads each
file's content via `git show HEAD:<path>`. Working-tree-only files
(untracked pollution, other-branch checkouts) are invisible to the
check. `--tracked` is a flag on the existing CLI; default behavior is
unchanged.

### D2. G9 — `gac-healthcheck.py` M1 check runs `--tracked`

Check #13 now invokes `bin/gac/gac-m1-sync.py --tracked --json`. The
health dashboard reflects the merged commit state; concurrent agents'
uncommitted work can no longer flip the M1 light.

### D3. G10 — Re-derive 3 stale M1 instances

`GAC_M1_SYNC_WRITE=1 gac-m1-sync.py --sync --tracked` re-derived
CR-P77-3-2-PREFIX-PATTERN, CR-P77-6-2-TIER-FALLBACK-TEST and
CR-P79-4-CATALOG-HEALTH-METRIC from the registry SSOT (executor adds
`ci_gate`, lifecycle `active`, version `1.0.0`), committed in ecos
`3330ce2`. Tracked drift is now 117/0/0/0.

### D4 — Regression tests

`tests/test_gac_m1_tracked_truth.py` (3 tests) writes an untracked
fixture with a **brand-new** `properties.id: BRAND-NEW` (a same-id copy
would be deduped and prove nothing):

| Test | Expectation |
|------|-------------|
| worktree mode detects untracked pollution | `orphan_in_m1` contains `BRAND-NEW` (baseline) |
| tracked mode ignores untracked pollution | `orphan_in_m1` empty, 0 orphans (the fix) |
| tracked instances match root pointer | `registry_rules == m1_instances`, 0/0/0 |

## Consequences

### Positive

- **M1 health light reflects merged truth.** Worktree dirt from
  concurrent rounds no longer reports `missing=19, orphan=110`; the
  check answers "is the committed state consistent", not "is someone
  mid-edit".
- **tracked-truth principle established** for the M1 plane: derived
  governance state is judged on what is merged, matching how CI and
  gac gates evaluate the repo.
- stale=9 closed to 0, closing the last real M1 drift.

### Negative / Trade-offs

- A deliberately-intended but **uncommitted** M1 change is invisible to
  the health check until merged. That is by design: the M1 plane is
  derived (SSOT is governance-checks.yaml), so uncommitted derivations
  are work-in-progress, not state.
- `--tracked` shells out to `git ls-tree`/`git show` (subprocess) with a
  30s timeout; a broken submodule (missing dir, not a repo) degrades to
  empty node set. CI gates still surface that via submodule-reachability.

## Compliance

- ADR-0106: M1 remains the derived plane; SSOT unchanged; the sync
  mechanism now has a tracked-truth input mode.
- ADR-0374: continues the registry-convergence family (M1 count
  alignment in G3, now field-level freshness + pollution resistance).
- ADR-0203: requirement iteration; workflow run registered with path
  coverage on the touched files.
- ADR-0220 D1: claim `round-0376` (deleted after merge).

## Verification

```bash
# D1/D3 — tracked state fully aligned
python3 bin/gac/gac-m1-sync.py --tracked --json
#   {"registry_rules": 117, "m1_instances": 117,
#    "diff": {"missing_in_m1": [], "orphan_in_m1": [], "stale": []}}

# D2 — healthcheck M1 green
python3 bin/gac/gac-healthcheck.py
#   M1实例drift (机制7): registry=117 M1=117 缺=0 多余=0 过期=0

# D4 — regression
python3 -m pytest tests/test_gac_m1_tracked_truth.py -q
#   3 passed
```
