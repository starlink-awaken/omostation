---
status: superseded
lifecycle: contract
owner: governance-team
last_updated: 2026-08-22
title: scripts close-duplicate-gap-first 执行清单
type: doc
---

# scripts close-duplicate-gap-first 执行清单

> **已退役** (2026-08-21): `scripts/bin/` 工具已迁移到 `bin/`，scripts 仓库已 archive。
> 本文档保留作为历史记录。

- 生成时间: 2026-08-16T12:23:12
- 数据源: `docs/operations/bin-scripts-convergence-manifest.json`
- Round 筛选: all
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

## 任务清单（按 round -> due -> risk desc）
| name                       | owner      | round   | due        | risk | status  | bin                                   | scripts                                       |
| -------------------------- | ---------- | ------- | ---------- | ---- | ------- | ------------------------------------- | --------------------------------------------- |
| control_experiment         | collab     | round10 | 2026-09-22 | 8    | managed | bin/collab/control_experiment.py      | scripts/bin/collab/control_experiment.py      |
| git_health_hook            | governance | round10 | 2026-09-22 | 8    | managed | bin/git-health-hook.py                | scripts/bin/git-health-hook.py                |
| physical_recovery          | delivery   | round10 | 2026-09-22 | 8    | managed | bin/delivery/physical_recovery.py     | scripts/bin/delivery/physical_recovery.py     |
| bus_usage_report           | ssot       | round7  | 2026-09-01 | 19   | managed | bin/ssot/bus-usage-report.py          | scripts/bin/ssot/bus-usage-report.py          |
| adr_drift_apply            | adr        | round7  | 2026-09-01 | 15   | managed | bin/adr/adr-drift-apply.py            | scripts/bin/adr/adr-drift-apply.py            |
| adr_drift_auto_fix         | adr        | round7  | 2026-09-01 | 15   | managed | bin/adr/adr-drift-auto-fix.py         | scripts/bin/adr/adr-drift-auto-fix.py         |
| adr_drift_check            | adr        | round7  | 2026-09-01 | 15   | managed | bin/adr/adr-drift-check.py            | scripts/bin/adr/adr-drift-check.py            |
| adr_drift_classify         | adr        | round7  | 2026-09-01 | 15   | managed | bin/adr/adr-drift-classify.py         | scripts/bin/adr/adr-drift-classify.py         |
| adr_trend_insight          | adr        | round7  | 2026-09-01 | 15   | managed | bin/adr/adr-trend-insight.py          | scripts/bin/adr/adr-trend-insight.py          |
| cockpit_readiness          | governance | round7  | 2026-09-01 | 15   | managed | bin/cockpit-readiness.py              | scripts/bin/cockpit-readiness.py              |
| mesh_orphan_cleanup        | mesh       | round7  | 2026-09-01 | 15   | managed | bin/mesh/mesh-orphan-cleanup.py       | scripts/bin/mesh/mesh-orphan-cleanup.py       |
| next_adr_id                | adr        | round7  | 2026-09-01 | 15   | managed | bin/adr/next-adr-id.py                | scripts/bin/adr/next-adr-id.py                |
| submodule_gitlink_check    | governance | round7  | 2026-09-01 | 15   | managed | bin/submodule-gitlink-check.py        | scripts/bin/submodule-gitlink-check.py        |
| check_doc_claims           | mof        | round8  | 2026-09-08 | 15   | managed | bin/mof/check-doc-claims.py           | scripts/bin/mof/check-doc-claims.py           |
| drift_history_insight      | gac        | round8  | 2026-09-08 | 15   | managed | bin/gac/drift-history-insight.py      | scripts/bin/gac/drift-history-insight.py      |
| gac_hygiene_check          | gac        | round8  | 2026-09-08 | 15   | managed | bin/gac/gac-hygiene-check.py          | scripts/bin/gac/gac-hygiene-check.py          |
| gen_dependency_baseline    | mof        | round8  | 2026-09-08 | 15   | managed | bin/mof/gen-dependency-baseline.py    | scripts/bin/mof/gen-dependency-baseline.py    |
| gen_project_registry       | mof        | round8  | 2026-09-08 | 15   | managed | bin/mof/gen-project-registry.py       | scripts/bin/mof/gen-project-registry.py       |
| governance_history_insight | gac        | round8  | 2026-09-08 | 15   | managed | bin/gac/governance-history-insight.py | scripts/bin/gac/governance-history-insight.py |
| m2_ssot_inventory          | mof        | round8  | 2026-09-08 | 15   | managed | bin/mof/m2-ssot-inventory.py          | scripts/bin/mof/m2-ssot-inventory.py          |
| mof_bootstrap              | mof        | round8  | 2026-09-08 | 15   | managed | bin/mof/mof-bootstrap.py              | scripts/bin/mof/mof-bootstrap.py              |
| mof_m2_coverage            | mof        | round8  | 2026-09-08 | 15   | managed | bin/mof/mof-m2-coverage.py            | scripts/bin/mof/mof-m2-coverage.py            |
| rule_history_insight       | gac        | round8  | 2026-09-08 | 15   | managed | bin/gac/rule-history-insight.py       | scripts/bin/gac/rule-history-insight.py       |
| alert_aggregator           | gac        | round9  | 2026-09-15 | 15   | managed | bin/gac/alert-aggregator.py           | scripts/bin/gac/alert-aggregator.py           |
| alert_mock_p0_notify       | gac        | round9  | 2026-09-15 | 15   | managed | bin/_archive/2026-08-conv3/alert-mock-p0-notify.py       | scripts/bin/_archive/2026-08-conv3/alert-mock-p0-notify.py       |
| auto_merge_lane_policy     | gac        | round9  | 2026-09-15 | 15   | managed | bin/gac/auto-merge-lane-policy.py     | scripts/bin/gac/auto-merge-lane-policy.py     |
| dim_weight                 | gac        | round9  | 2026-09-15 | 15   | managed | bin/gac/dim-weight.py                 | scripts/bin/gac/dim-weight.py                 |
| event_loop_lint            | gac        | round9  | 2026-09-15 | 15   | managed | bin/gac/event-loop-lint.py            | scripts/bin/gac/event-loop-lint.py            |
| gac_bootstrap              | gac        | round9  | 2026-09-15 | 15   | managed | bin/gac/gac-bootstrap.py              | scripts/bin/gac/gac-bootstrap.py              |
| gac_coverage_lint          | gac        | round9  | 2026-09-15 | 15   | managed | bin/gac/gac-coverage-lint.py          | scripts/bin/gac/gac-coverage-lint.py          |
| gac_gc                     | gac        | round9  | 2026-09-15 | 15   | managed | bin/gac/gac-gc.py                     | scripts/bin/gac/gac-gc.py                     |
| gac_mof_validate           | gac        | round9  | 2026-09-15 | 15   | managed | bin/gac/gac-mof-validate.py           | scripts/bin/gac/gac-mof-validate.py           |
| governance_alert_dispatch  | gac        | round9  | 2026-09-15 | 15   | managed | bin/gac/governance-alert-dispatch.py  | scripts/bin/gac/governance-alert-dispatch.py  |
| kos_seed_import            | gac        | round9  | 2026-09-15 | 15   | managed | bin/gac/kos-seed-import.py            | scripts/bin/gac/kos-seed-import.py            |
| m1_closeout_report         | gac        | round9  | 2026-09-15 | 15   | managed | bin/gac/m1-closeout-report.py         | scripts/bin/gac/m1-closeout-report.py         |
| omo_acl_ops_window         | gac        | round9  | 2026-09-15 | 15   | managed | bin/gac/omo-acl-ops-window.sh         | scripts/bin/gac/omo-acl-ops-window.sh         |
| omo_state_write_guard      | gac        | round9  | 2026-09-15 | 15   | managed | bin/gac/omo-state-write-guard.py      | scripts/bin/gac/omo-state-write-guard.py      |
| p0_event_listener          | gac        | round9  | 2026-09-15 | 15   | managed | bin/gac/p0-event-listener.py          | scripts/bin/gac/p0-event-listener.py          |
| phase_gate_check           | gac        | round9  | 2026-09-15 | 15   | managed | bin/gac/phase-gate-check.py           | scripts/bin/gac/phase-gate-check.py           |
| state_freshness_check      | gac        | round9  | 2026-09-15 | 15   | managed | bin/gac/state-freshness-check.py      | scripts/bin/gac/state-freshness-check.py      |
| x2_freshness_check         | gac        | round9  | 2026-09-15 | 15   | managed | bin/gac/x2-freshness-check.py         | scripts/bin/gac/x2-freshness-check.py         |
| x2_rule_add                | gac        | round9  | 2026-09-15 | 15   | managed | bin/gac/x2-rule-add.py                | scripts/bin/gac/x2-rule-add.py                |
| x2_rule_lint               | gac        | round9  | 2026-09-15 | 15   | managed | bin/gac/x2-rule-lint.py               | scripts/bin/gac/x2-rule-lint.py               |

