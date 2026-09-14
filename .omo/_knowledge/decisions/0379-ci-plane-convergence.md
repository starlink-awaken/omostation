---
id: ADR-0379
title: CI plane convergence — surface SSOT, observability, dedup, registry-driven runner
status: ACCEPTED
lifecycle: spec
owner: governance-team
last-reviewed: 2026-08-05
type: ssot
---

# 0379 — CI Plane Convergence Round

> Parent: ADR-0373..0378 (convergence rounds), ADR-0171 (severity).
> The GaC rule plane was converged to registry→derived→tracked-truth
> (G1-G15). This round applies the same methodology to the **CI
> workflow plane** (42 workflows), which was still hand-maintained
> YAML with no SSOT.

## Context

Architecture analysis of the CI plane (42 workflows) found:

1. **No SSOT** — check existence/triggers/path-filters were duplicated
   across `.github/workflows/*.yml` and `sgf-policy.yaml`, synced by
   hand. `governance-check.yml` embedded 21 `python3 scripts/check-*.py
   || FAILED=1` lines in one bash block (P77 silent-fail history).
2. **Wasted compute** — 9 workflows used `on: [push, pull_request]`,
   so every PR-branch push ran the full check twice (push event +
   pull_request event). The 7-project coverage matrix ran 2× per PR.
3. **No CI self-observability** — no detection for dead workflows,
   orphan check scripts (2 found: `check-future-annotations.py`,
   `check-index-coverage.py`), or overlap (6 found, e.g.
   `check-interfaces.py` in 2 workflows).
4. **Local/CI gate composition drift** — gac-local-gate skip rules vs
   CI strict could disagree.

## Decision

### D1. E-1 — `ci-surfaces.yaml` SSOT

New `.omo/_truth/registry/ci-surfaces.yaml`: every check-type tool
(`scripts/check-*`, `bin/gac|ssot|mof|adr|sweep`) registered with
`tool / workflow / gate / triggers / status`. Bootstrap generated 92
surfaces from actual wiring; 2 unwired scripts registered as
`status: orphan` (explicit acknowledgment). Governed by new rule
**CR-CI-SURFACE-SSOT** (legacy_index container, executor
`ci_gate`+`omo_audit` → red) and L0 constraint **CR-CI-01**
(E-L0-021).

### D2. E-3 — `check-ci-surfaces.py` detector

New detector with 5 checks:
- `unregistered-check` (error) — workflow executes an unregistered tool
- `gate-parity` (error) — sgf-policy gate references unregistered tool
- `orphan-script` (warn) — disk script unwired and unacknowledged
- `overlap` (warn) — same tool in 2+ workflows
- `double-trigger` (error) — `on: [push, pull_request]` without
  main-branch restriction

Registered as sgf-policy gate `ci-surfaces-check` (runs in
gac-local-gate locally and CI strict) and wired into
`gac-healthcheck` as check #14 **CI平面**.

### D3. E-2 — registry-driven runner

`bin/gac/ci-check-runner.py` executes the surfaces registered to a
workflow (`--workflow <file>`), with per-check PASS/FAIL reporting.
`governance-check.yml`'s 21-line bash loop replaced by
`ci-check-runner.py --workflow governance-check.yml` (20 checks);
redundant `check-interfaces.py` removed from the freshness job (has
dedicated `interfaces-enforce.yml`). ci-surfaces.yaml is now the
execution manifest: adding a doc check = one registry entry, and the
unregistered-check detector enforces it.

### D4. E-4 — double-trigger dedup

9 workflows converted from `on: [push, pull_request]` to
`push: {branches: [main]} + pull_request` (ci-python-coverage,
cross-deps-enforce, integration, interfaces-enforce,
port-registry-enforce, pytest, ruff-check, state-goals-enforce,
task-schema-enforce). PR-branch pushes no longer run the same checks
twice; the 7-project coverage matrix runs once per PR.

## Consequences

### Positive

- CI plane is now SSOT-driven and self-observable: `gac-healthcheck`
  16→17 checks including **CI平面** (94 surfaces, 0 errors).
- Unregistered check tools are a hard gate error — adding a CI check
  without registering it fails `gac-local-gate` and PR CI.
- ~30% PR compute reduction (9 workflows × 2→1 runs per push).
- P77 silent-fail class eliminated: the runner reports each check's
  exit, and the registry is the contract.

### Negative / Trade-offs

- 4 remaining `overlap` warnings are intentional defense-in-depth
  (submodule-reachability ×3, gac-local-gate ×2 across scopes) —
  kept as warnings, not errors.
- `ci-check-runner.py` runs `python3` subprocesses serially (300s
  timeout each); parallelization is future work.
- The 2 orphan scripts remain un-wired (registered as orphan);
  wiring or deletion is a follow-up decision.

## Compliance

- ADR-0171: CR-CI-SURFACE-SSOT executor includes `ci_gate` → red
  severity (CI plane integrity is merge-blocking).
- ADR-0376/0377: extends tracked-truth/runtime-plane principles to
  the CI plane.
- ADR-0203: requirement iteration; workflow run registered with path
  coverage.
- ADR-0220 D1: claim `round-0379` (deleted after merge).
- L0: CR-CI-01 constraint (E-L0-021) added to L0-constraints.yaml.

## Verification

```bash
# D2 — detector clean
python3 bin/gac/check-ci-surfaces.py
#   0 errors, 4 overlap warns (defense-in-depth)

# D3 — runner executes governance-check scope
python3 bin/gac/ci-check-runner.py --workflow governance-check.yml
#   20 checks PASS

# D1/D4 — healthcheck includes CI plane
python3 bin/gac/gac-healthcheck.py
#   ▶ CI平面 (ADR-0379): ✅ surfaces=94 wired=83 errors=0 warns=4

# 回归
python3 -m pytest tests/test_ci_surfaces.py -q
#   7 passed
```
