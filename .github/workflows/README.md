# CI Workflows

> 37 个 GitHub Actions workflow。按类型分组。

## Governance Gates (PR-blocking)

| Workflow | Trigger | Role |
|----------|---------|------|
| `omostation-governance.yml` | PR | OMO governance audit (score >= 95, 0 missing deliverables) |
| `governance-check.yml` | push + schedule (6h) | Full governance check (GaC + SSOT + link + layer digest) |
| `gac-gate.yml` | push | GaC validation gate (rule structure + drift) |
| `evidence-smoke-gate.yml` | push | BOS declaration vs execution gap audit |
| `submodule-freshness-gatekeeper.yml` | push + schedule (daily) | Submodule pointer freshness (blocks stale submodules) |

## Enforcement (Policy CI)

| Workflow | Trigger | Role |
|----------|---------|------|
| `port-registry-enforce.yml` | push + PR | Port hardcoding check |
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
| `ci-lint.yml` | schedule (weekly) | Workflow + shell lint |
| `ruff-check.yml` | push + PR | Python ruff check |
| `pytest.yml` | push + PR | Root pytest |
| `integration.yml` | push + PR | Integration tests (`run-all.sh`) |
| `ci-python-coverage.yml` | push + PR | Python coverage |
| `quality.yml` | push + PR | Quality checks |

## Per-Project CI (path-filtered)

| Workflow | Trigger | Path Filter | Role |
|----------|---------|-------------|------|
| `agora-ci.yml` | push + PR | `projects/agora/**` | Agora (I0) |
| `cockpit-ci.yml` | push + PR | `projects/cockpit/**` | Cockpit (L3) |
| `ecos-ci.yml` | push + PR | `projects/ecos/**` | eCOS (L0) |
| `kairon-ci.yml` | push + PR | `projects/kairon/**` | kairon (L2) |
| `metaos-ci.yml` | push + PR | `projects/metaos/**` | metaos (L2) |
| `family-hub-ci.yml` | push + PR | `projects/family-hub/**` | family-hub (X) |
| `observability-ci.yml` | push + PR | `projects/observability/**` | observability (X) |
| `gbrain-ci.yml` | manual only | — | no-op (CI lives in gbrain repo) |
| `runtime-ci.yml` | manual only | — | no-op (CI lives in runtime repo) |
| `cockpit-ui-ci.yml` | manual only | — | no-op (CI lives in cockpit-ui repo) |

## Scheduled

| Workflow | Schedule | Role |
|----------|----------|------|
| `mof-update.yml` | weekly Mon 06:00 | MOF check + extract + vault-paths scan |
| `audit-rollout-monthly.yml` | monthly 1st 01:00 | Audit rollout + §17 metrics |
| `c2g-radar-daily.yml` | daily 09:00 | C2G radar scan |
| `c2g-gc-weekly.yml` | weekly Mon 09:00 | C2G garbage collection |
| `omo-autopilot.yml` | schedule | OMO autopilot evolutionary loop |
| `governance-check.yml` | every 6h | Governance doc-freshness + interface check |
| `debt-audit.yml` | weekly Mon 09:00 | Debt audit report |

## Publishing

| Workflow | Trigger | Role |
|----------|---------|------|
| `publish-pypi.yml` | push (tags) | Publish Python packages to PyPI |
| `workspace.yml` | push + PR | Workspace CI |

## Deleted (cleanup 2026-07-01)

| Workflow | Reason |
|----------|--------|
| `agora-dashboard-ci.yml` | agora-dashboard archived to `_archived/` |
| `sharedbrain-kairon-integration.yml` | SharedBrain archived, all jobs `if: false` |
| `phase11-ci.yml` | Legacy, fully redundant with `pytest.yml` + `ci-python-coverage.yml` |
