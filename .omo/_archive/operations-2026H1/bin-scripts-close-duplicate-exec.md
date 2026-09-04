---
status: superseded
lifecycle: contract
owner: governance-team
last_updated: 2026-08-22
title: scripts close-duplicate-gap-first 执行计划与结果
type: doc
---

# scripts close-duplicate-gap-first 执行计划与结果

> **已退役** (2026-08-21): `scripts/bin/` 工具已迁移到 `bin/`，scripts 仓库已 archive。
> 本文档保留作为历史记录。

- 生成时间: 2026-08-16T12:30:26
- 数据源: `docs/operations/bin-scripts-convergence-manifest.json`
- Round 筛选: all
- 模式: apply
- 条目数: 43

## 按 round 分布
- round10: 3
- round7: 10
- round8: 10
- round9: 20

## 按 owner 分布
- adr: 6
- collab: 1
- delivery: 1
- gac: 24
- governance: 3
- mesh: 1
- mof: 6
- ssot: 1

## 执行清单
| name                       | owner      | round   | status  | result  | reason    | bin                                   | scripts                                       |
| -------------------------- | ---------- | ------- | ------- | ------- | --------- | ------------------------------------- | --------------------------------------------- |
| control_experiment         | collab     | round10 | managed | removed | identical | bin/collab/control_experiment.py      | scripts/bin/collab/control_experiment.py      |
| physical_recovery          | delivery   | round10 | managed | removed | identical | bin/delivery/physical_recovery.py     | scripts/bin/delivery/physical_recovery.py     |
| git_health_hook            | governance | round10 | managed | removed | identical | bin/git-health-hook.py                | scripts/bin/git-health-hook.py                |
| adr_drift_apply            | adr        | round7  | managed | removed | identical | bin/adr/adr-drift-apply.py            | scripts/bin/adr/adr-drift-apply.py            |
| adr_drift_auto_fix         | adr        | round7  | managed | removed | identical | bin/adr/adr-drift-auto-fix.py         | scripts/bin/adr/adr-drift-auto-fix.py         |
| adr_drift_check            | adr        | round7  | managed | removed | identical | bin/adr/adr-drift-check.py            | scripts/bin/adr/adr-drift-check.py            |
| adr_drift_classify         | adr        | round7  | managed | removed | identical | bin/adr/adr-drift-classify.py         | scripts/bin/adr/adr-drift-classify.py         |
| adr_trend_insight          | adr        | round7  | managed | removed | identical | bin/adr/adr-trend-insight.py          | scripts/bin/adr/adr-trend-insight.py          |
| next_adr_id                | adr        | round7  | managed | removed | identical | bin/adr/next-adr-id.py                | scripts/bin/adr/next-adr-id.py                |
| cockpit_readiness          | governance | round7  | managed | removed | identical | bin/cockpit-readiness.py              | scripts/bin/cockpit-readiness.py              |
| submodule_gitlink_check    | governance | round7  | managed | removed | identical | bin/submodule-gitlink-check.py        | scripts/bin/submodule-gitlink-check.py        |
| mesh_orphan_cleanup        | mesh       | round7  | managed | removed | identical | bin/mesh/mesh-orphan-cleanup.py       | scripts/bin/mesh/mesh-orphan-cleanup.py       |
| bus_usage_report           | ssot       | round7  | managed | removed | identical | bin/ssot/bus-usage-report.py          | scripts/bin/ssot/bus-usage-report.py          |
| drift_history_insight      | gac        | round8  | managed | removed | identical | bin/gac/drift-history-insight.py      | scripts/bin/gac/drift-history-insight.py      |
| gac_hygiene_check          | gac        | round8  | managed | removed | identical | bin/gac/gac-hygiene-check.py          | scripts/bin/gac/gac-hygiene-check.py          |
| governance_history_insight | gac        | round8  | managed | removed | identical | bin/gac/governance-history-insight.py | scripts/bin/gac/governance-history-insight.py |
| rule_history_insight       | gac        | round8  | managed | removed | identical | bin/gac/rule-history-insight.py       | scripts/bin/gac/rule-history-insight.py       |
| check_doc_claims           | mof        | round8  | managed | removed | identical | bin/mof/check-doc-claims.py           | scripts/bin/mof/check-doc-claims.py           |
| gen_dependency_baseline    | mof        | round8  | managed | removed | identical | bin/mof/gen-dependency-baseline.py    | scripts/bin/mof/gen-dependency-baseline.py    |
| gen_project_registry       | mof        | round8  | managed | removed | identical | bin/mof/gen-project-registry.py       | scripts/bin/mof/gen-project-registry.py       |
| m2_ssot_inventory          | mof        | round8  | managed | removed | identical | bin/mof/m2-ssot-inventory.py          | scripts/bin/mof/m2-ssot-inventory.py          |
| mof_bootstrap              | mof        | round8  | managed | removed | identical | bin/mof/mof-bootstrap.py              | scripts/bin/mof/mof-bootstrap.py              |
| mof_m2_coverage            | mof        | round8  | managed | removed | identical | bin/mof/mof-m2-coverage.py            | scripts/bin/mof/mof-m2-coverage.py            |
| alert_aggregator           | gac        | round9  | managed | removed | identical | bin/gac/alert-aggregator.py           | scripts/bin/gac/alert-aggregator.py           |
| alert_mock_p0_notify       | gac        | round9  | managed | removed | identical | bin/_archive/2026-08-conv3/alert-mock-p0-notify.py       | scripts/bin/_archive/2026-08-conv3/alert-mock-p0-notify.py       |
| auto_merge_lane_policy     | gac        | round9  | managed | removed | identical | bin/gac/auto-merge-lane-policy.py     | scripts/bin/gac/auto-merge-lane-policy.py     |
| dim_weight                 | gac        | round9  | managed | removed | identical | bin/gac/dim-weight.py                 | scripts/bin/gac/dim-weight.py                 |
| event_loop_lint            | gac        | round9  | managed | removed | identical | bin/gac/event-loop-lint.py            | scripts/bin/gac/event-loop-lint.py            |
| gac_bootstrap              | gac        | round9  | managed | removed | identical | bin/gac/gac-bootstrap.py              | scripts/bin/gac/gac-bootstrap.py              |
| gac_coverage_lint          | gac        | round9  | managed | removed | identical | bin/gac/gac-coverage-lint.py          | scripts/bin/gac/gac-coverage-lint.py          |
| gac_gc                     | gac        | round9  | managed | removed | identical | bin/gac/gac-gc.py                     | scripts/bin/gac/gac-gc.py                     |
| gac_mof_validate           | gac        | round9  | managed | removed | identical | bin/gac/gac-mof-validate.py           | scripts/bin/gac/gac-mof-validate.py           |
| governance_alert_dispatch  | gac        | round9  | managed | removed | identical | bin/gac/governance-alert-dispatch.py  | scripts/bin/gac/governance-alert-dispatch.py  |
| kos_seed_import            | gac        | round9  | managed | removed | identical | bin/gac/kos-seed-import.py            | scripts/bin/gac/kos-seed-import.py            |
| m1_closeout_report         | gac        | round9  | managed | removed | identical | bin/gac/m1-closeout-report.py         | scripts/bin/gac/m1-closeout-report.py         |
| omo_acl_ops_window         | gac        | round9  | managed | removed | identical | bin/gac/omo-acl-ops-window.sh         | scripts/bin/gac/omo-acl-ops-window.sh         |
| omo_state_write_guard      | gac        | round9  | managed | removed | identical | bin/gac/omo-state-write-guard.py      | scripts/bin/gac/omo-state-write-guard.py      |
| p0_event_listener          | gac        | round9  | managed | removed | identical | bin/gac/p0-event-listener.py          | scripts/bin/gac/p0-event-listener.py          |
| phase_gate_check           | gac        | round9  | managed | removed | identical | bin/gac/phase-gate-check.py           | scripts/bin/gac/phase-gate-check.py           |
| state_freshness_check      | gac        | round9  | managed | removed | identical | bin/gac/state-freshness-check.py      | scripts/bin/gac/state-freshness-check.py      |
| x2_freshness_check         | gac        | round9  | managed | removed | identical | bin/gac/x2-freshness-check.py         | scripts/bin/gac/x2-freshness-check.py         |
| x2_rule_add                | gac        | round9  | managed | removed | identical | bin/gac/x2-rule-add.py                | scripts/bin/gac/x2-rule-add.py                |
| x2_rule_lint               | gac        | round9  | managed | removed | identical | bin/gac/x2-rule-lint.py               | scripts/bin/gac/x2-rule-lint.py               |


## 2026-08-24 配额清偿归档 (BET-Y1Q3-T6-05)

| name | 归档位置 | 依据 |
|------|---------|------|
| test_zones_check | bin/_archive/quota-clearance-2026-08-24/ | git grep 零引用 |
| test_bus_e2e_harness | bin/_archive/quota-clearance-2026-08-24/ | git grep 零引用 |
| port_governance_deck | bin/_archive/quota-clearance-2026-08-24/ | git grep 零引用 |
| dormant_adapter(+test) | bin/_archive/quota-clearance-2026-08-24/ | PACKS 域休眠, 不在 manifest |
| memory_os_consolidate_deck | bin/_archive/quota-clearance-2026-08-24/ | 零引用, 不在 manifest |
