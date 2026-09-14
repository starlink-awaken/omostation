---
id: ADR-0380
title: CI plane completion — runner migration, orphan cleanup, concurrent-drift absorption
status: ACCEPTED
lifecycle: spec
owner: governance-team
last-reviewed: 2026-08-06
type: ssot
---

# 0380 — CI Plane Completion Round

> Parent: ADR-0379 (CI plane convergence).
> Closes the ci-plane-convergence initiative at 100%: migrate the
> remaining standalone workflows to the registry runner, zero orphan
> scripts, absorb concurrent-agent drift (M1 39 stale, archived tool
> regression), and document known concurrent test debt.

## Context

After ADR-0379 (PR #1041), the CI plane had an SSOT + detector + runner,
but three loose ends remained: (1) the standalone workflows
(cross-deps/interfaces/port-registry) still invoked their scripts
directly instead of through the registry runner, (2) 4 surfaces were
registered as orphan (2 real orphans + 2 whose wiring was mislabeled),
and (3) concurrent agents (phase8/9/10) had drifted the tree: 39 M1
instances stale, the LLM-gateway tool archived while its gate + rule
stayed registered, and new registry rules without M1 sync.

## Decision

### D1. P0a — Absorb concurrent drift (healthcheck back to green)

- `gac-m1-sync --sync`: re-derived 37 rules (executor/dimension/version
  field changes from phase10), ecos main pushed → M1 131 = registry.
- Rebase conflict on `sgf-policy.yaml` (concurrent LLM-gateway gate)
  resolved: conflict markers cleaned, concurrent `check-llm-gateway-only`
  gate preserved.
- **Archived-tool regression fixed**: `check-llm-gateway-only.py` was
  archived by phase8 while its gate + CR-LLM-GATEWAY-ONLY rule stayed
  registered → gate FAIL. Moved the tool back to `bin/gac/` and
  registered in ci-surfaces (gate-parity requirement).
- ADR-0104 residue check green (concurrent refs cleaned in ADR-0379).

### D2. P1a — Migrate standalone workflows to the registry runner

`cross-deps-enforce.yml`, `interfaces-enforce.yml`,
`port-registry-enforce.yml` now call
`ci-check-runner.py --workflow <file>` instead of direct script
invocation. `check-vault-paths` surface gained `args: [--check-ports]`
for the port-registry scope. ci-surfaces.yaml is now the single
execution manifest for all doc-governance + standalone check workflows.

### D3. P1b — Zero orphan scripts

- `check-index-coverage.py` wired into governance-check scope (active).
- `check-future-annotations.py` wired into pyright-sweep scope (active).
- `check-doc-freshness-gate.py` / `check-metric-trend.py` confirmed
  already wired in gac-gate.yml — status corrected orphan → active.
- `orphan_registered` 4 → 0.

### D4. Known concurrent test debt (not fixed here)

15 `tests/test_agent_workflow.py` failures exist on main after
concurrent omo v10 (#1034) changed lock lifecycle / observe findings
taxonomy (`orphan_lock` → `active_run_missing_locks`) and lint contract
behavior. The root test file is not covered by CI, so the breakage is
silent. Follow-up: align tests to v10 semantics AND add
`test_agent_workflow.py` to CI coverage so this class of regression is
visible.

## Consequences

### Positive

- ci-plane-convergence initiative closed at 100% with closure evidence.
- All check execution is registry-driven; adding/removing a check =
  one ci-surfaces entry, enforced by the detector.
- healthcheck green (M1 131/0/0/0, CI平面 98 surfaces 0 errors,
  0 orphan); gate 40/40.
- Concurrent archived-tool regression caught and fixed by the very
  gate-parity detector built in ADR-0379 (self-verification loop).

### Negative / Trade-offs

- The 15 test_agent_workflow.py failures remain (documented debt,
  owner: omo v10 change).
- mof-update.yml still calls check-vault-paths directly (different
  cadence — scheduled L0 scan); 3 overlap warnings remain as
  intentional defense-in-depth.

## Compliance

- ADR-0379: completes the CI plane SSOT/runner/detector architecture.
- ADR-0203: requirement iteration; workflow run registered with path
  coverage.
- ADR-0220 D1: claim `round-0380` (deleted after merge).

## Verification

```bash
python3 bin/gac/check-ci-surfaces.py --json
#   {"ok": true, "error_count": 0, "orphan_registered": 0, "surfaces": 98}

python3 bin/gac/ci-check-runner.py --workflow governance-check.yml  # 20 PASS
python3 bin/gac/ci-check-runner.py --workflow port-registry-enforce.yml  # 1 PASS

python3 bin/gac/gac-healthcheck.py   # 全绿 (M1 131/0/0/0, CI平面 ✅)
make gac-local-gate                   # 40/40 PASS
```
