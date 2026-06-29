# CI Workflows

> 42 个 GitHub Actions workflow。按类型分组。

## Governance Gates (PR-blocking)

| Workflow | Trigger | Role |
|----------|---------|------|
| `omostation-governance.yml` | PR | OMO governance audit (score >= 95, 0 missing deliverables) |
| `governance-check.yml` | push | Full governance check (GaC + SSOT + link + layer digest) |
| `gac-gate.yml` | push | GaC validation gate (rule structure + drift) |
| `evidence-smoke-gate.yml` | push | BOS declaration vs execution gap audit |
| `submodule-freshness-gatekeeper.yml` | push + schedule | Submodule pointer freshness (blocks stale submodules) |

## Enforcement (Policy CI)

| Workflow | Trigger | Role |
|----------|---------|------|
| `port-registry-enforce.yml` | push + PR | Port hardcoding check (via `check-vault-paths.py --check-ports`) |
| `cross-deps-enforce.yml` | push + PR | Cross-layer dependency enforcement |
| `interfaces-enforce.yml` | push + PR | Interface registration enforcement |
| `state-goals-enforce.yml` | push + PR | State/goals alignment enforcement |
| `task-schema-enforce.yml` | push + PR | Task YAML schema enforcement |
| `constraint-validation.yml` | PR | L0 constraint validation |
| `config-check.yml` | push | Configuration check |
| `meta-model-check.yml` | push | MOF meta-model check |

## Code Quality

| Workflow | Trigger | Role |
|----------|---------|------|
| `ci-lint.yml` | push | Workflow + shell lint |
| `ruff-check.yml` | push + PR | Python ruff check |
| `pytest.yml` | push + PR | Root pytest |
| `integration.yml` | push + PR | Integration tests (`run-all.sh`) |
| `ci-python-coverage.yml` | push + PR | Python coverage |
| `quality.yml` | push + PR | Quality checks |

## Per-Project CI

| Workflow | Trigger | Role |
|----------|---------|------|
| `agora-ci.yml` | push + PR | Agora (I0) |
| `cockpit-ci.yml` | push + PR | Cockpit (L3) |
| `ecos-ci.yml` | push + PR | eCOS (L0) |
| `gbrain-ci.yml` | push + PR | gbrain (L2) |
| `kairon-ci.yml` | push + PR | kairon (L2) |
| `metaos-ci.yml` | push + PR | metaos (L2) |
| `runtime-ci.yml` | push + PR | runtime (L1) |
| `family-hub-ci.yml` | push + PR | family-hub (X) |
| `observability-ci.yml` | push + PR | observability (X) |
| `hermes-console-ci.yml` | push + PR | hermes-console (archived, kept for history) |
| `agora-dashboard-ci.yml` | push + PR | agora-dashboard (legacy) |

## Scheduled

| Workflow | Schedule | Role |
|----------|----------|------|
| `mof-update.yml` | weekly Mon 06:00 | MOF check + extract + vault-paths scan |
| `audit-rollout-monthly.yml` | monthly | Audit rollout |
| `c2g-radar-daily.yml` | daily | C2G radar scan |
| `c2g-gc-weekly.yml` | weekly | C2G garbage collection |
| `omo-autopilot.yml` | schedule | OMO autopilot evolutionary loop |

## Publishing

| Workflow | Trigger | Role |
|----------|---------|------|
| `publish-pypi.yml` | push (tags) | Publish Python packages to PyPI |
| `workspace.yml` | push + PR | Workspace CI |

## Other

| Workflow | Trigger | Role |
|----------|---------|------|
| `phase11-ci.yml` | push | Phase 11 CI (legacy) |
| `debt-audit.yml` | push + PR | Debt audit |
| `sharedbrain-kairon-integration.yml` | push | SharedBrain x kairon integration (archived) |
