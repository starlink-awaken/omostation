# CI Workflows

> 37 个 GitHub Actions workflow。按类型分组。

## Governance Gates (PR-blocking)

| Workflow | Trigger | Role |
|----------|---------|------|
| `omostation-governance.yml` | PR | OMO governance audit (score >= 95, 0 missing deliverables) |
| `governance-check.yml` | push + schedule (6h) | Full governance check (GaC + SSOT + link + layer digest) |
| `gac-gate.yml` | push | GaC validation gate (rule structure + drift) |
| `evidence-smoke-gate.yml` | push | BOS declaration vs execution gap audit |
| `submodule-freshness-gatekeeper.yml` | push + schedule (daily) | Submodule pointer freshness (push: warn on drift; schedule/dispatch: fail closed) |

## Enforcement (Policy CI)

| Workflow | Trigger | Role |
|----------|---------|------|
| `state-goals-enforce.yml` | push + PR | State/goals alignment enforcement |
| `task-schema-enforce.yml` | push + PR | Task YAML schema enforcement |
| `constraint-validation.yml` | PR | L0 constraint validation |
| `config-check.yml` | push | Configuration check |

> 2026-10-28 删除三个**零信号** workflow：`cross-deps-enforce.yml` /
> `interfaces-enforce.yml` / `port-registry-enforce.yml`。三者都跑
> `ci-check-runner.py --workflow <self>`，而 runner 只认 ci-surfaces 里
> `workflow == <name>` 的条目 —— 它们一条都没有（`cross-deps` / `interfaces` 无条目，
> `port-registry` 的条目挂在 `mof-update.yml` + `also_in`，runner 不认 `also_in`）。
> 于是每次 push/PR 各起一个 job、跑 ~30s、恒绿、零覆盖。
>
> 能力承接：
> - 跨层依赖 → `gac-gate.yml` 的 `check-layers`（`bin/layer-dependency-check.py`）
> - 端口硬编码 → `mof-update.yml` + `quality.yml` 的 pre-commit hook
>   （`bin/ssot/check-hardcoded-ports.py`）
> - **接口契约 → `governance-check.yml`（`bin/ssot/check-interfaces.py`）** ✅ 已补齐
>
> 接口契约的缺口来历：`governance-check.yml` 的注释称 ADR-0379 D3 把 `check-interfaces`
> 从这里移除、「已由独立 workflow `interfaces-enforce.yml` 覆盖」—— 但那个 workflow 是
> 空 job，且它引用的 `bin/ssot/check-interfaces.py` **从未提交进本仓**（`git log --all -- '*check-interfaces.py'`
> 零命中）。该能力自 2026-06-06 起只有悬空引用，被一个恒绿空 job 掩盖至今。
> `bin/ssot/check-interfaces.py` 是该能力的首次真正实现，注册在
> `ci-surfaces.yaml` 的 `governance-check.yml` 下。
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
| `kairon-ci.yml` | push + PR | `projects/knowledge/kairon/**` | kairon (L2) |
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
