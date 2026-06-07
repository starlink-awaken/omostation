# CI Workflows

## omostation-governance.yml

PR 触发 omo governance audit:
- PR 改 .omo/tasks/planned/** → 必跑
- PR 改 projects/**/pyproject.toml → 必跑 (BOS URI 跨包影响)
- PR 改 projects/omo/src/omo/omo_*.py → 必跑 (omo 治理核心)
- main push → 必跑 (防回归)

检查项:
- audit 总分 ≥ 95
- 0 missing deliverables (防 P34-W4 揭出的描述式 YAML 回归)
