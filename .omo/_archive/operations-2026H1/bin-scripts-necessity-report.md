---
status: superseded
lifecycle: contract
owner: governance-team
last_updated: 2026-08-22
title: scripts 兼容层与并行能力收敛清单（快照）
type: doc
---

# scripts 兼容层与并行能力收敛清单（快照）

> **已退役** (2026-08-21): `scripts/bin/` 工具已迁移到 `bin/`，scripts 仓库已 archive。
> 本文档保留作为历史记录。

- 生成时间: 2026-08-16T03:59:47.605263+00:00
- 清单入口: `docs/operations/bin-scripts-convergence-manifest.json`
- 清单总条目: **213**
- 当前扫描总脚本: 797
- 并行候选（bin/scripts 重名）: 213
- 并行缺口: 0
- 管控并行（managed/high-confidence）: 0, 未控高风险并行: 0

## 说明
- 依据 `(name, bin, scripts, action, owner)` 去重后统计和汇总

## 一、全量分层
- 按 action 统计:
  - `bin-master, scripts-compat-shim`: 168（managed=168 / unmanaged=0）
  - `bin-ssot-master, root-wrapper, scripts-compat-shim`: 2（managed=2 / unmanaged=0）
  - `close-duplicate-gap-first`: 43（managed=43 / unmanaged=0）
- 按 owner 统计:
  - adr: 6
  - collab: 1
  - delivery: 1
  - gac: 24
  - governance: 173
  - mesh: 1
  - mof: 6
  - ssot: 1

## 二、`close-duplicate-gap-first`（优先消化）
| name                       | owner      | status  | action                    | round   | due        | risk | bin                                   | scripts                                       |
| -------------------------- | ---------- | ------- | ------------------------- | ------- | ---------- | ---- | ------------------------------------- | --------------------------------------------- |
| adr_drift_apply            | adr        | managed | close-duplicate-gap-first | round7  | 2026-09-01 | 15   | bin/adr/adr-drift-apply.py            | scripts/bin/adr/adr-drift-apply.py            |
| adr_drift_auto_fix         | adr        | managed | close-duplicate-gap-first | round7  | 2026-09-01 | 15   | bin/adr/adr-drift-auto-fix.py         | scripts/bin/adr/adr-drift-auto-fix.py         |
| adr_drift_check            | adr        | managed | close-duplicate-gap-first | round7  | 2026-09-01 | 15   | bin/adr/adr-drift-check.py            | scripts/bin/adr/adr-drift-check.py            |
| adr_drift_classify         | adr        | managed | close-duplicate-gap-first | round7  | 2026-09-01 | 15   | bin/adr/adr-drift-classify.py         | scripts/bin/adr/adr-drift-classify.py         |
| adr_trend_insight          | adr        | managed | close-duplicate-gap-first | round7  | 2026-09-01 | 15   | bin/adr/adr-trend-insight.py          | scripts/bin/adr/adr-trend-insight.py          |
| next_adr_id                | adr        | managed | close-duplicate-gap-first | round7  | 2026-09-01 | 15   | bin/adr/next-adr-id.py                | scripts/bin/adr/next-adr-id.py                |
| control_experiment         | collab     | managed | close-duplicate-gap-first | round10 | 2026-09-22 | 8    | bin/collab/control_experiment.py      | scripts/bin/collab/control_experiment.py      |
| physical_recovery          | delivery   | managed | close-duplicate-gap-first | round10 | 2026-09-22 | 8    | bin/delivery/physical_recovery.py     | scripts/bin/delivery/physical_recovery.py     |
| alert_aggregator           | gac        | managed | close-duplicate-gap-first | round9  | 2026-09-15 | 15   | bin/gac/alert-aggregator.py           | scripts/bin/gac/alert-aggregator.py           |
| alert_mock_p0_notify       | gac        | managed | close-duplicate-gap-first | round9  | 2026-09-15 | 15   | bin/_archive/2026-08-conv3/alert-mock-p0-notify.py       | scripts/bin/_archive/2026-08-conv3/alert-mock-p0-notify.py       |
| auto_merge_lane_policy     | gac        | managed | close-duplicate-gap-first | round9  | 2026-09-15 | 15   | bin/gac/auto-merge-lane-policy.py     | scripts/bin/gac/auto-merge-lane-policy.py     |
| dim_weight                 | gac        | managed | close-duplicate-gap-first | round9  | 2026-09-15 | 15   | bin/gac/dim-weight.py                 | scripts/bin/gac/dim-weight.py                 |
| drift_history_insight      | gac        | managed | close-duplicate-gap-first | round8  | 2026-09-08 | 15   | bin/gac/drift-history-insight.py      | scripts/bin/gac/drift-history-insight.py      |
| event_loop_lint            | gac        | managed | close-duplicate-gap-first | round9  | 2026-09-15 | 15   | bin/gac/event-loop-lint.py            | scripts/bin/gac/event-loop-lint.py            |
| gac_bootstrap              | gac        | managed | close-duplicate-gap-first | round9  | 2026-09-15 | 15   | bin/gac/gac-bootstrap.py              | scripts/bin/gac/gac-bootstrap.py              |
| gac_coverage_lint          | gac        | managed | close-duplicate-gap-first | round9  | 2026-09-15 | 15   | bin/gac/gac-coverage-lint.py          | scripts/bin/gac/gac-coverage-lint.py          |
| gac_gc                     | gac        | managed | close-duplicate-gap-first | round9  | 2026-09-15 | 15   | bin/gac/gac-gc.py                     | scripts/bin/gac/gac-gc.py                     |
| gac_hygiene_check          | gac        | managed | close-duplicate-gap-first | round8  | 2026-09-08 | 15   | bin/gac/gac-hygiene-check.py          | scripts/bin/gac/gac-hygiene-check.py          |
| gac_mof_validate           | gac        | managed | close-duplicate-gap-first | round9  | 2026-09-15 | 15   | bin/gac/gac-mof-validate.py           | scripts/bin/gac/gac-mof-validate.py           |
| governance_alert_dispatch  | gac        | managed | close-duplicate-gap-first | round9  | 2026-09-15 | 15   | bin/gac/governance-alert-dispatch.py  | scripts/bin/gac/governance-alert-dispatch.py  |
| governance_history_insight | gac        | managed | close-duplicate-gap-first | round8  | 2026-09-08 | 15   | bin/gac/governance-history-insight.py | scripts/bin/gac/governance-history-insight.py |
| kos_seed_import            | gac        | managed | close-duplicate-gap-first | round9  | 2026-09-15 | 15   | bin/gac/kos-seed-import.py            | scripts/bin/gac/kos-seed-import.py            |
| m1_closeout_report         | gac        | managed | close-duplicate-gap-first | round9  | 2026-09-15 | 15   | bin/gac/m1-closeout-report.py         | scripts/bin/gac/m1-closeout-report.py         |
| omo_acl_ops_window         | gac        | managed | close-duplicate-gap-first | round9  | 2026-09-15 | 15   | bin/gac/omo-acl-ops-window.sh         | scripts/bin/gac/omo-acl-ops-window.sh         |
| omo_state_write_guard      | gac        | managed | close-duplicate-gap-first | round9  | 2026-09-15 | 15   | bin/gac/omo-state-write-guard.py      | scripts/bin/gac/omo-state-write-guard.py      |
| p0_event_listener          | gac        | managed | close-duplicate-gap-first | round9  | 2026-09-15 | 15   | bin/gac/p0-event-listener.py          | scripts/bin/gac/p0-event-listener.py          |
| phase_gate_check           | gac        | managed | close-duplicate-gap-first | round9  | 2026-09-15 | 15   | bin/gac/phase-gate-check.py           | scripts/bin/gac/phase-gate-check.py           |
| rule_history_insight       | gac        | managed | close-duplicate-gap-first | round8  | 2026-09-08 | 15   | bin/gac/rule-history-insight.py       | scripts/bin/gac/rule-history-insight.py       |
| state_freshness_check      | gac        | managed | close-duplicate-gap-first | round9  | 2026-09-15 | 15   | bin/gac/state-freshness-check.py      | scripts/bin/gac/state-freshness-check.py      |
| x2_freshness_check         | gac        | managed | close-duplicate-gap-first | round9  | 2026-09-15 | 15   | bin/gac/x2-freshness-check.py         | scripts/bin/gac/x2-freshness-check.py         |
| x2_rule_add                | gac        | managed | close-duplicate-gap-first | round9  | 2026-09-15 | 15   | bin/gac/x2-rule-add.py                | scripts/bin/gac/x2-rule-add.py                |
| x2_rule_lint               | gac        | managed | close-duplicate-gap-first | round9  | 2026-09-15 | 15   | bin/gac/x2-rule-lint.py               | scripts/bin/gac/x2-rule-lint.py               |
| cockpit_readiness          | governance | managed | close-duplicate-gap-first | round7  | 2026-09-01 | 15   | bin/cockpit-readiness.py              | scripts/bin/cockpit-readiness.py              |
| git_health_hook            | governance | managed | close-duplicate-gap-first | round10 | 2026-09-22 | 8    | bin/git-health-hook.py                | scripts/bin/git-health-hook.py                |
| submodule_gitlink_check    | governance | managed | close-duplicate-gap-first | round7  | 2026-09-01 | 15   | bin/submodule-gitlink-check.py        | scripts/bin/submodule-gitlink-check.py        |
| mesh_orphan_cleanup        | mesh       | managed | close-duplicate-gap-first | round7  | 2026-09-01 | 15   | bin/mesh/mesh-orphan-cleanup.py       | scripts/bin/mesh/mesh-orphan-cleanup.py       |
| check_doc_claims           | mof        | managed | close-duplicate-gap-first | round8  | 2026-09-08 | 15   | bin/mof/check-doc-claims.py           | scripts/bin/mof/check-doc-claims.py           |
| gen_dependency_baseline    | mof        | managed | close-duplicate-gap-first | round8  | 2026-09-08 | 15   | bin/mof/gen-dependency-baseline.py    | scripts/bin/mof/gen-dependency-baseline.py    |
| gen_project_registry       | mof        | managed | close-duplicate-gap-first | round8  | 2026-09-08 | 15   | bin/mof/gen-project-registry.py       | scripts/bin/mof/gen-project-registry.py       |
| m2_ssot_inventory          | mof        | managed | close-duplicate-gap-first | round8  | 2026-09-08 | 15   | bin/mof/m2-ssot-inventory.py          | scripts/bin/mof/m2-ssot-inventory.py          |
| mof_bootstrap              | mof        | managed | close-duplicate-gap-first | round8  | 2026-09-08 | 15   | bin/mof/mof-bootstrap.py              | scripts/bin/mof/mof-bootstrap.py              |
| mof_m2_coverage            | mof        | managed | close-duplicate-gap-first | round8  | 2026-09-08 | 15   | bin/mof/mof-m2-coverage.py            | scripts/bin/mof/mof-m2-coverage.py            |
| bus_usage_report           | ssot       | managed | close-duplicate-gap-first | round7  | 2026-09-01 | 19   | bin/ssot/bus-usage-report.py          | scripts/bin/ssot/bus-usage-report.py          |


## 三、`bin-master, scripts-compat-shim`（兼容入口保留）

共 168 条
| name                                 | owner      | status  | action                          | due | bin                                              | scripts                                                  |
| ------------------------------------ | ---------- | ------- | ------------------------------- | --- | ------------------------------------------------ | -------------------------------------------------------- |
| adr_coverage                         | governance | managed | bin-master, scripts-compat-shim | -   | bin/adr/adr-coverage.py                          | scripts/bin/adr/adr-coverage.py                          |
| adv_fail_report                      | governance | managed | bin-master, scripts-compat-shim | -   | bin/collab/adv-fail-report.py                    | scripts/bin/collab/adv-fail-report.py                    |
| agent_registry                       | governance | managed | bin-master, scripts-compat-shim | -   | bin/delivery/agent_registry.py                   | scripts/bin/delivery/agent_registry.py                   |
| agent_workflow                       | governance | managed | bin-master, scripts-compat-shim | -   | bin/agent-workflow.py                            | scripts/bin/agent-workflow.py                            |
| arcnode_validate                     | governance | managed | bin-master, scripts-compat-shim | -   | bin/ssot/arcnode-validate                        | scripts/bin/ssot/arcnode-validate                        |
| bos_stdio_inventory                  | governance | managed | bin-master, scripts-compat-shim | -   | bin/collab/bos-stdio-inventory.py                | scripts/bin/collab/bos-stdio-inventory.py                |
| bos_tracking_gate                    | governance | managed | bin-master, scripts-compat-shim | -   | bin/ssot/bos-tracking-gate.py                    | scripts/bin/ssot/bos-tracking-gate.py                    |
| bus_dlq                              | governance | managed | bin-master, scripts-compat-shim | -   | bin/ssot/bus-dlq                                 | scripts/bin/ssot/bus-dlq                                 |
| bus_e2e_harness                      | governance | managed | bin-master, scripts-compat-shim | -   | bin/ssot/bus-e2e-harness.py                      | scripts/bin/ssot/bus-e2e-harness.py                      |
| caliber                              | governance | managed | bin-master, scripts-compat-shim | -   | bin/delivery/caliber.py                          | scripts/bin/delivery/caliber.py                          |
| change_lane_check                    | governance | managed | bin-master, scripts-compat-shim | -   | bin/change-lane-check.py                         | scripts/bin/change-lane-check.py                         |
| check_adversarial_effectiveness      | governance | managed | bin-master, scripts-compat-shim | -   | bin/gac/check-adversarial-effectiveness.py       | scripts/bin/gac/check-adversarial-effectiveness.py       |
| check_boundary                       | governance | managed | bin-master, scripts-compat-shim | -   | bin/ssot/check-boundary.py                       | scripts/bin/ssot/check-boundary.py                       |
| check_branch_redundant               | governance | managed | bin-master, scripts-compat-shim | -   | bin/ssot/check-branch-redundant.py               | scripts/bin/ssot/check-branch-redundant.py               |
| check_cockpit_ui_dist                | governance | managed | bin-master, scripts-compat-shim | -   | bin/ssot/check-cockpit-ui-dist.py                | scripts/bin/ssot/check-cockpit-ui-dist.py                |
| check_cross_refs                     | governance | managed | bin-master, scripts-compat-shim | -   | bin/ssot/check-cross-refs.py                     | scripts/bin/ssot/check-cross-refs.py                     |
| check_cross_repo_consistency         | governance | managed | bin-master, scripts-compat-shim | -   | bin/ssot/check-cross-repo-consistency.py         | scripts/bin/ssot/check-cross-repo-consistency.py         |
| check_dashboard_registry_consistency | governance | managed | bin-master, scripts-compat-shim | -   | bin/ssot/check-dashboard-registry-consistency.py | scripts/bin/ssot/check-dashboard-registry-consistency.py |
| check_domain_m1_alignment            | governance | managed | bin-master, scripts-compat-shim | -   | bin/ssot/check-domain-m1-alignment.py            | scripts/bin/ssot/check-domain-m1-alignment.py            |
| check_dual_track_purity              | governance | managed | bin-master, scripts-compat-shim | -   | bin/gac/check-dual-track-purity.py               | scripts/bin/gac/check-dual-track-purity.py               |
| check_god_module                     | governance | managed | bin-master, scripts-compat-shim | -   | bin/ssot/check-god-module.py                     | scripts/bin/ssot/check-god-module.py                     |
| check_governance_ratio               | governance | managed | bin-master, scripts-compat-shim | -   | bin/gac/check-governance-ratio.py                | scripts/bin/gac/check-governance-ratio.py                |
| check_hardcoded_ports                | governance | managed | bin-master, scripts-compat-shim | -   | bin/ssot/check-hardcoded-ports.py                | scripts/bin/ssot/check-hardcoded-ports.py                |
| check_health_ssot                    | governance | managed | bin-master, scripts-compat-shim | -   | bin/check_health_ssot.py                         | scripts/bin/check_health_ssot.py                         |
| check_index_drift                    | governance | managed | bin-master, scripts-compat-shim | -   | bin/ssot/check-index-drift.py                    | scripts/bin/ssot/check-index-drift.py                    |
| check_layer_call_direction           | governance | managed | bin-master, scripts-compat-shim | -   | bin/ssot/check-layer-call-direction.py           | scripts/bin/ssot/check-layer-call-direction.py           |
| check_mcptool_impl_drift             | governance | managed | bin-master, scripts-compat-shim | -   | bin/ssot/check-mcptool-impl-drift.py             | scripts/bin/ssot/check-mcptool-impl-drift.py             |
| check_mof_capabilities_drift         | governance | managed | bin-master, scripts-compat-shim | -   | bin/mof/check-mof-capabilities-drift.py          | scripts/bin/mof/check-mof-capabilities-drift.py          |
| check_redline_coverage               | governance | managed | bin-master, scripts-compat-shim | -   | bin/gac/check-redline-coverage.py                | scripts/bin/gac/check-redline-coverage.py                |
| check_severity_registry              | governance | managed | bin-master, scripts-compat-shim | -   | bin/gac/check-severity-registry.py               | scripts/bin/gac/check-severity-registry.py               |
| check_silent_loss                    | governance | managed | bin-master, scripts-compat-shim | -   | bin/gac/check-silent-loss.py                     | scripts/bin/gac/check-silent-loss.py                     |
| check_toolbox_ssot                   | governance | managed | bin-master, scripts-compat-shim | -   | bin/ssot/check-toolbox-ssot.py                   | scripts/bin/ssot/check-toolbox-ssot.py                   |
| check_work_landed                    | governance | managed | bin-master, scripts-compat-shim | -   | bin/gac/check-work-landed.py                     | scripts/bin/gac/check-work-landed.py                     |
| check_workorder_schema               | governance | managed | bin-master, scripts-compat-shim | -   | bin/gac/check-workorder-schema.py                | scripts/bin/gac/check-workorder-schema.py                |
| commit_assist                        | governance | managed | bin-master, scripts-compat-shim | -   | bin/commit-assist.py                             | scripts/bin/commit-assist.py                             |
| compass_radar                        | governance | managed | bin-master, scripts-compat-shim | -   | bin/compass_radar.py                             | scripts/bin/compass_radar.py                             |
| current_state_coherence              | governance | managed | bin-master, scripts-compat-shim | -   | bin/ssot/current-state-coherence.py              | scripts/bin/ssot/current-state-coherence.py              |
| debt_closed_per_feature              | governance | managed | bin-master, scripts-compat-shim | -   | bin/gac/debt-closed-per-feature.py               | scripts/bin/gac/debt-closed-per-feature.py               |
| debt_integrity_check                 | governance | managed | bin-master, scripts-compat-shim | -   | bin/gac/debt-integrity-check.py                  | scripts/bin/gac/debt-integrity-check.py                  |
| dir_hygiene_check                    | governance | managed | bin-master, scripts-compat-shim | -   | bin/ssot/dir-hygiene-check.py                    | scripts/bin/ssot/dir-hygiene-check.py                    |
| doc_governance_check                 | governance | managed | bin-master, scripts-compat-shim | -   | bin/ssot/doc-governance-check.py                 | scripts/bin/ssot/doc-governance-check.py                 |
| doc_governance_migrate               | governance | managed | bin-master, scripts-compat-shim | -   | bin/_archive/2026-08-conv3/doc-governance-migrate.py               | scripts/bin/_archive/2026-08-conv3/doc-governance-migrate.py               |
| doc_link_check                       | governance | managed | bin-master, scripts-compat-shim | -   | bin/ssot/doc-link-check.py                       | scripts/bin/ssot/doc-link-check.py                       |
| doc_ssot_lint                        | governance | managed | bin-master, scripts-compat-shim | -   | bin/ssot/doc-ssot-lint.py                        | scripts/bin/ssot/doc-ssot-lint.py                        |
| ecos_link                            | governance | managed | bin-master, scripts-compat-shim | -   | bin/mof/ecos-link                                | scripts/bin/mof/ecos-link                                |
| emergence                            | governance | managed | bin-master, scripts-compat-shim | -   | bin/delivery/emergence.py                        | scripts/bin/delivery/emergence.py                        |
| evidence_smoke                       | governance | managed | bin-master, scripts-compat-shim | -   | bin/gac/evidence-smoke.py                        | scripts/bin/gac/evidence-smoke.py                        |
| export_dualtrack                     | governance | managed | bin-master, scripts-compat-shim | -   | bin/collab/export-dualtrack.py                   | scripts/bin/collab/export-dualtrack.py                   |
| external_activation_preflight        | governance | managed | bin-master, scripts-compat-shim | -   | bin/ssot/external-activation-preflight.py        | scripts/bin/ssot/external-activation-preflight.py        |
| external_resource_catalog            | governance | managed | bin-master, scripts-compat-shim | -   | bin/ssot/external-resource-catalog.py            | scripts/bin/ssot/external-resource-catalog.py            |
| external_resource_pack               | governance | managed | bin-master, scripts-compat-shim | -   | bin/ssot/external-resource-pack.py               | scripts/bin/ssot/external-resource-pack.py               |
| external_scene_trial                 | governance | managed | bin-master, scripts-compat-shim | -   | bin/ssot/external-scene-trial.py                 | scripts/bin/ssot/external-scene-trial.py                 |
| gac_branch_protection                | governance | managed | bin-master, scripts-compat-shim | -   | bin/gac/gac-branch-protection.sh                 | scripts/bin/gac/gac-branch-protection.sh                 |
| gac_compute_onboard                  | governance | managed | bin-master, scripts-compat-shim | -   | bin/gac/gac-compute-onboard.py                   | scripts/bin/gac/gac-compute-onboard.py                   |
| gac_consensus_inject                 | governance | managed | bin-master, scripts-compat-shim | -   | bin/gac/gac-consensus-inject.py                  | scripts/bin/gac/gac-consensus-inject.py                  |
| gac_daemon                           | governance | managed | bin-master, scripts-compat-shim | -   | bin/gac/gac-daemon.py                            | scripts/bin/gac/gac-daemon.py                            |
| gac_drift                            | governance | managed | bin-master, scripts-compat-shim | -   | bin/gac/gac-drift.py                             | scripts/bin/gac/gac-drift.py                             |
| gac_executor                         | governance | managed | bin-master, scripts-compat-shim | -   | bin/gac/gac-executor.py                          | scripts/bin/gac/gac-executor.py                          |
| gac_export_agents                    | governance | managed | bin-master, scripts-compat-shim | -   | bin/gac/gac-export-agents.py                     | scripts/bin/gac/gac-export-agents.py                     |
| gac_healthcheck                      | governance | managed | bin-master, scripts-compat-shim | -   | bin/gac/gac-healthcheck.py                       | scripts/bin/gac/gac-healthcheck.py                       |
| gac_hook_pre_edit                    | governance | managed | bin-master, scripts-compat-shim | -   | bin/gac/gac-hook-pre-edit.py                     | scripts/bin/gac/gac-hook-pre-edit.py                     |
| gac_ingest_legacy                    | governance | managed | bin-master, scripts-compat-shim | -   | bin/_archive/2026-08-gap-governance-s5/gac-ingest-legacy.py                     | scripts/bin/_archive/2026-08-gap-governance-s5/gac-ingest-legacy.py                     |
| gac_local_gate                       | governance | managed | bin-master, scripts-compat-shim | -   | bin/gac/gac-local-gate.py                        | scripts/bin/gac/gac-local-gate.py                        |
| gac_m1_sync                          | governance | managed | bin-master, scripts-compat-shim | -   | bin/gac/gac-m1-sync.py                           | scripts/bin/gac/gac-m1-sync.py                           |
| gac_mesh_router                      | governance | managed | bin-master, scripts-compat-shim | -   | bin/_archive/2026-08-conv3/gac-mesh-router.py                       | scripts/bin/_archive/2026-08-conv3/gac-mesh-router.py                       |
| gac_severity                         | governance | managed | bin-master, scripts-compat-shim | -   | bin/gac/gac_severity.py                          | scripts/bin/gac/gac_severity.py                          |
| gac_validate                         | governance | managed | bin-master, scripts-compat-shim | -   | bin/gac/gac-validate.py                          | scripts/bin/gac/gac-validate.py                          |
| gac_worktree                         | governance | managed | bin-master, scripts-compat-shim | -   | bin/gac/gac-worktree.sh                          | scripts/bin/gac/gac-worktree.sh                          |
| gac_worktree_cleanup                 | governance | managed | bin-master, scripts-compat-shim | -   | bin/gac/gac-worktree-cleanup.sh                  | scripts/bin/gac/gac-worktree-cleanup.sh                  |
| gac_worktree_guard                   | governance | managed | bin-master, scripts-compat-shim | -   | bin/gac/gac-worktree-guard.sh                    | scripts/bin/gac/gac-worktree-guard.sh                    |
| gac_worktree_prune                   | governance | managed | bin-master, scripts-compat-shim | -   | bin/gac/gac-worktree-prune.sh                    | scripts/bin/gac/gac-worktree-prune.sh                    |
| gen_agent_redlines                   | governance | managed | bin-master, scripts-compat-shim | -   | bin/mof/gen-agent-redlines.py                    | scripts/bin/mof/gen-agent-redlines.py                    |
| gen_agents_index                     | governance | managed | bin-master, scripts-compat-shim | -   | bin/ssot/gen-agents-index.py                     | scripts/bin/ssot/gen-agents-index.py                     |
| gen_capability_registry              | governance | managed | bin-master, scripts-compat-shim | -   | bin/ssot/gen-capability-registry.py                               | scripts/bin/ssot/gen-capability-registry.py                               |
| gen_help_docs                        | governance | managed | bin-master, scripts-compat-shim | -   | bin/ssot/gen-help-docs.py                                          | scripts/bin/ssot/gen-help-docs.py                                          |
| gen_knowledge_index                  | governance | managed | bin-master, scripts-compat-shim | -   | bin/ssot/gen-knowledge-index.py                  | scripts/bin/ssot/gen-knowledge-index.py                  |
| gen_projects_index                   | governance | managed | bin-master, scripts-compat-shim | -   | bin/ssot/gen-projects-index.py                   | scripts/bin/ssot/gen-projects-index.py                   |
| gen_service_configs                  | governance | managed | bin-master, scripts-compat-shim | -   | bin/mof/gen-service-configs.py                   | scripts/bin/mof/gen-service-configs.py                   |
| gen_tools_index                      | governance | managed | bin-master, scripts-compat-shim | -   | bin/ssot/gen-tools-index.py                      | scripts/bin/ssot/gen-tools-index.py                      |
| generate_brief                       | governance | managed | bin-master, scripts-compat-shim | -   | bin/mof/generate-brief.py                        | scripts/bin/mof/generate-brief.py                        |
| git_divergence_check                 | governance | managed | bin-master, scripts-compat-shim | -   | bin/gac/git-divergence-check.py                  | scripts/bin/gac/git-divergence-check.py                  |
| git_safe                             | governance | managed | bin-master, scripts-compat-shim | -   | bin/ssot/git-safe                                | scripts/bin/ssot/git-safe                                |
| god_module_13_error_list             | governance | managed | bin-master, scripts-compat-shim | -   | bin/ssot/god-module-13-error-list.py             | scripts/bin/ssot/god-module-13-error-list.py             |
| god_module_roadmap                   | governance | managed | bin-master, scripts-compat-shim | -   | bin/ssot/god-module-roadmap.py                   | scripts/bin/ssot/god-module-roadmap.py                   |
| governance_convergence_lint          | governance | managed | bin-master, scripts-compat-shim | -   | bin/gac/governance-convergence-lint.py           | scripts/bin/gac/governance-convergence-lint.py           |
| governance_dashboard                 | governance | managed | bin-master, scripts-compat-shim | -   | bin/gac/governance-dashboard.py                  | scripts/bin/gac/governance-dashboard.py                  |
| governance_evolution                 | governance | managed | bin-master, scripts-compat-shim | -   | bin/gac/governance-evolution.py                  | scripts/bin/gac/governance-evolution.py                  |
| governance_history_stats             | governance | managed | bin-master, scripts-compat-shim | -   | bin/gac/governance-history-stats.py              | scripts/bin/gac/governance-history-stats.py              |
| governance_readiness                 | governance | managed | bin-master, scripts-compat-shim | -   | bin/gac/governance-readiness.py                  | scripts/bin/gac/governance-readiness.py                  |
| governance_semantic_gate             | governance | managed | bin-master, scripts-compat-shim | -   | bin/gac/governance-semantic-gate.py              | scripts/bin/gac/governance-semantic-gate.py              |
| governance_trend_report              | governance | managed | bin-master, scripts-compat-shim | -   | bin/gac/governance-trend-report.py               | scripts/bin/gac/governance-trend-report.py               |
| install_watch_agent                  | governance | managed | bin-master, scripts-compat-shim | -   | bin/gac/install-watch-agent.py                   | scripts/bin/gac/install-watch-agent.py                   |
| knowledge_foundry_cron               | governance | managed | bin-master, scripts-compat-shim | -   | bin/gac/knowledge-foundry-cron.py                | scripts/bin/gac/knowledge-foundry-cron.py                |
| kos                                  | governance | managed | bin-master, scripts-compat-shim | -   | bin/gac/kos                                      | scripts/bin/gac/kos                                      |
| latency_stats                        | governance | managed | bin-master, scripts-compat-shim | -   | bin/delivery/latency_stats.py                    | scripts/bin/delivery/latency_stats.py                    |
| layer_dependency_check               | governance | managed | bin-master, scripts-compat-shim | -   | bin/layer-dependency-check.py                    | scripts/bin/layer-dependency-check.py                    |
| m4_health_score                      | governance | managed | bin-master, scripts-compat-shim | -   | bin/mof/m4-health-score.py                       | scripts/bin/mof/m4-health-score.py                       |
| management_cross_ref_check           | governance | managed | bin-master, scripts-compat-shim | -   | bin/ssot/management-cross-ref-check.py           | scripts/bin/ssot/management-cross-ref-check.py           |
| matrix_consistency_lint              | governance | managed | bin-master, scripts-compat-shim | -   | bin/ssot/matrix-consistency-lint.py              | scripts/bin/ssot/matrix-consistency-lint.py              |
| mcp_server_kos                       | governance | managed | bin-master, scripts-compat-shim | -   | bin/gac/mcp-server-kos.py                        | scripts/bin/gac/mcp-server-kos.py                        |
| mcp_tool_data_complete               | governance | managed | bin-master, scripts-compat-shim | -   | bin/gac/mcp-tool-data-complete.py                | scripts/bin/gac/mcp-tool-data-complete.py                |
| measure_all                          | governance | managed | bin-master, scripts-compat-shim | -   | bin/delivery/measure_all.py                      | scripts/bin/delivery/measure_all.py                      |
| measure_physical                     | governance | managed | bin-master, scripts-compat-shim | -   | bin/delivery/measure_physical.py                 | scripts/bin/delivery/measure_physical.py                 |
| mof_act                              | governance | managed | bin-master, scripts-compat-shim | -   | bin/mof/mof-act                                  | scripts/bin/mof/mof-act                                  |
| mof_analyze                          | governance | managed | bin-master, scripts-compat-shim | -   | bin/mof/mof-analyze                              | scripts/bin/mof/mof-analyze                              |
| mof_assign                           | governance | managed | bin-master, scripts-compat-shim | -   | bin/mof/mof-assign                               | scripts/bin/mof/mof-assign                               |
| mof_autonomous                       | governance | managed | bin-master, scripts-compat-shim | -   | bin/mof/mof-autonomous                           | scripts/bin/mof/mof-autonomous                           |
| mof_decide                           | governance | managed | bin-master, scripts-compat-shim | -   | bin/mof/mof-decide                               | scripts/bin/mof/mof-decide                               |
| mof_drift                            | governance | managed | bin-master, scripts-compat-shim | -   | bin/mof/mof-drift                                | scripts/bin/mof/mof-drift                                |
| mof_enforce                          | governance | managed | bin-master, scripts-compat-shim | -   | bin/mof/mof-enforce                              | scripts/bin/mof/mof-enforce                              |
| mof_evolution                        | governance | managed | bin-master, scripts-compat-shim | -   | bin/mof/mof-evolution                            | scripts/bin/mof/mof-evolution                            |
| mof_export                           | governance | managed | bin-master, scripts-compat-shim | -   | bin/mof/mof-export                               | scripts/bin/mof/mof-export                               |
| mof_graph                            | governance | managed | bin-master, scripts-compat-shim | -   | bin/mof/mof-graph                                | scripts/bin/mof/mof-graph                                |
| mof_io                               | governance | managed | bin-master, scripts-compat-shim | -   | bin/mof/mof-io                                   | scripts/bin/mof/mof-io                                   |
| mof_manage                           | governance | managed | bin-master, scripts-compat-shim | -   | bin/mof/mof-manage                               | scripts/bin/mof/mof-manage                               |
| mof_scan                             | governance | managed | bin-master, scripts-compat-shim | -   | bin/mof/mof-scan                                 | scripts/bin/mof/mof-scan                                 |
| mof_version                          | governance | managed | bin-master, scripts-compat-shim | -   | bin/mof/mof-version                              | scripts/bin/mof/mof-version                              |
| mypy_baseline_gate                   | governance | managed | bin-master, scripts-compat-shim | -   | bin/ssot/mypy-baseline-gate                      | scripts/bin/ssot/mypy-baseline-gate                      |
| network_path                         | governance | managed | bin-master, scripts-compat-shim | -   | bin/delivery/network_path.py                     | scripts/bin/delivery/network_path.py                     |
| omlxc_node_wakeup                    | governance | managed | bin-master, scripts-compat-shim | -   | bin/gac/omlxc-node-wakeup.py                     | scripts/bin/gac/omlxc-node-wakeup.py                     |
| omo_manage                           | governance | managed | bin-master, scripts-compat-shim | -   | bin/gac/omo-manage                               | scripts/bin/gac/omo-manage                               |
| omo_runtime_stamp_policy             | governance | managed | bin-master, scripts-compat-shim | -   | bin/gac/omo-runtime-stamp-policy.py              | scripts/bin/gac/omo-runtime-stamp-policy.py              |
| omo_state_projection_guard           | governance | managed | bin-master, scripts-compat-shim | -   | bin/gac/omo-state-projection-guard.py            | scripts/bin/gac/omo-state-projection-guard.py            |
| omo_validate                         | governance | managed | bin-master, scripts-compat-shim | -   | bin/gac/omo-validate                             | scripts/bin/gac/omo-validate                             |
| omostation_bootloader                | governance | managed | bin-master, scripts-compat-shim | -   | bin/gac/omostation-bootloader.py                 | scripts/bin/gac/omostation-bootloader.py                 |
| physical_client                      | governance | managed | bin-master, scripts-compat-shim | -   | bin/delivery/physical_client.py                  | scripts/bin/delivery/physical_client.py                  |
| physical_node                        | governance | managed | bin-master, scripts-compat-shim | -   | bin/delivery/physical_node.py                    | scripts/bin/delivery/physical_node.py                    |
| port_governance_deck                 | governance | managed | bin-master, scripts-compat-shim | -   | bin/_archive/2026-08-conv3/port-governance-deck.py                | scripts/bin/_archive/2026-08-conv3/port-governance-deck.py                |
| project_layer_index                  | governance | managed | bin-master, scripts-compat-shim | -   | bin/mof/project-layer-index.py                   | scripts/bin/mof/project-layer-index.py                   |
| recommend_mode                       | governance | managed | bin-master, scripts-compat-shim | -   | bin/collab/recommend_mode.py                     | scripts/bin/collab/recommend_mode.py                     |
| resolve_root_remote                  | governance | managed | bin-master, scripts-compat-shim | -   | bin/gac/resolve-root-remote.sh                   | scripts/bin/gac/resolve-root-remote.sh                   |
| role_collab                          | governance | managed | bin-master, scripts-compat-shim | -   | bin/delivery/role_collab.py                      | scripts/bin/delivery/role_collab.py                      |
| role_memory                          | governance | managed | bin-master, scripts-compat-shim | -   | bin/delivery/role_memory.py                      | scripts/bin/delivery/role_memory.py                      |
| scenario_lib                         | governance | managed | bin-master, scripts-compat-shim | -   | bin/collab/scenario_lib.py                       | scripts/bin/collab/scenario_lib.py                       |
| scene_card_candidates                | governance | managed | bin-master, scripts-compat-shim | -   | bin/ssot/scene-card-candidates.py                | scripts/bin/ssot/scene-card-candidates.py                |
| scene_card_intake                    | governance | managed | bin-master, scripts-compat-shim | -   | bin/ssot/scene-card-intake.py                    | scripts/bin/ssot/scene-card-intake.py                    |
| scene_card_review                    | governance | managed | bin-master, scripts-compat-shim | -   | bin/ssot/scene-card-review.py                    | scripts/bin/ssot/scene-card-review.py                    |
| scheduler                            | governance | managed | bin-master, scripts-compat-shim | -   | bin/delivery/scheduler.py                        | scripts/bin/delivery/scheduler.py                        |
| shared_context_cli                   | governance | managed | bin-master, scripts-compat-shim | -   | bin/delivery/shared-context-cli.py               | scripts/bin/delivery/shared-context-cli.py               |
| shared_context_store                 | governance | managed | bin-master, scripts-compat-shim | -   | bin/delivery/shared_context_store.py             | scripts/bin/delivery/shared_context_store.py             |
| ssot_guardian                        | governance | managed | bin-master, scripts-compat-shim | -   | bin/ssot/ssot-guardian.py                        | scripts/bin/ssot/ssot-guardian.py                        |
| ssot_watcher                         | governance | managed | bin-master, scripts-compat-shim | -   | bin/ssot-watcher.py                              | scripts/bin/ssot-watcher.py                              |
| ssot_writeback                       | governance | managed | bin-master, scripts-compat-shim | -   | bin/ssot/ssot-writeback.py                       | scripts/bin/ssot/ssot-writeback.py                       |
| state_stale_emit                     | governance | managed | bin-master, scripts-compat-shim | -   | bin/gac/state-stale-emit.py                      | scripts/bin/gac/state-stale-emit.py                      |
| state_sync                           | governance | managed | bin-master, scripts-compat-shim | -   | bin/delivery/state_sync.py                       | scripts/bin/delivery/state_sync.py                       |
| submodule_autobump                   | governance | managed | bin-master, scripts-compat-shim | -   | bin/ssot/submodule-autobump.sh                   | scripts/bin/ssot/submodule-autobump.sh                   |
| submodule_bump_check                 | governance | managed | bin-master, scripts-compat-shim | -   | bin/ssot/submodule-bump-check.py                 | scripts/bin/ssot/submodule-bump-check.py                 |
| submodule_pointer_transaction        | governance | managed | bin-master, scripts-compat-shim | -   | bin/ssot/submodule-pointer-transaction.sh        | scripts/bin/ssot/submodule-pointer-transaction.sh        |
| swarm_discipline                     | governance | managed | bin-master, scripts-compat-shim | -   | bin/gac/swarm_discipline.py                      | scripts/bin/gac/swarm_discipline.py                      |
| swarm_discipline_cli                 | governance | managed | bin-master, scripts-compat-shim | -   | bin/gac/swarm-discipline-cli.py                  | scripts/bin/gac/swarm-discipline-cli.py                  |
| swarm_git                            | governance | managed | bin-master, scripts-compat-shim | -   | bin/gac/swarm-git                                | scripts/bin/gac/swarm-git                                |
| sync_bos_registry                    | governance | managed | bin-master, scripts-compat-shim | -   | bin/ssot/sync-bos-registry.py                    | scripts/bin/ssot/sync-bos-registry.py                    |
| sync_submodule_pointers              | governance | managed | bin-master, scripts-compat-shim | -   | bin/ssot/sync-submodule-pointers.sh              | scripts/bin/ssot/sync-submodule-pointers.sh              |
| sync_submodules                      | governance | managed | bin-master, scripts-compat-shim | -   | bin/sync-submodules.sh                           | scripts/bin/sync-submodules.sh                           |
| test_bus_e2e_harness                 | governance | managed | bin-master, scripts-compat-shim | -   | bin/_archive/2026-08-conv3/test_bus-e2e-harness.py                | scripts/bin/_archive/2026-08-conv3/test_bus-e2e-harness.py                |
| test_coverage_check                  | governance | managed | bin-master, scripts-compat-shim | -   | bin/gac/test-coverage-check.py                   | scripts/bin/gac/test-coverage-check.py                   |
| test_gac_engine                      | governance | managed | bin-master, scripts-compat-shim | -   | bin/ssot/test-gac-engine.py                      | scripts/bin/ssot/test-gac-engine.py                      |
| test_mcp_kos                         | governance | managed | bin-master, scripts-compat-shim | -   | bin/ssot/test-mcp-kos.py                         | scripts/bin/ssot/test-mcp-kos.py                         |
| test_zones_check                     | governance | managed | bin-master, scripts-compat-shim | -   | bin/_archive/2026-08-conv3/test_zones_check.py                    | scripts/bin/_archive/2026-08-conv3/test_zones_check.py                    |
| ts_analyze                           | governance | managed | bin-master, scripts-compat-shim | -   | bin/ssot/ts-analyze.mjs                          | scripts/bin/ssot/ts-analyze.mjs                          |
| ts_file_analyze                      | governance | managed | bin-master, scripts-compat-shim | -   | bin/ssot/ts-file-analyze.py                      | scripts/bin/ssot/ts-file-analyze.py                      |
| venv_yaml_check                      | governance | managed | bin-master, scripts-compat-shim | -   | bin/ssot/venv-yaml-check.py                      | scripts/bin/ssot/venv-yaml-check.py                      |
| verify_omo                           | governance | managed | bin-master, scripts-compat-shim | -   | bin/ssot/verify-omo.sh                           | scripts/bin/ssot/verify-omo.sh                           |
| workspace                            | governance | managed | bin-master, scripts-compat-shim | -   | bin/workspace                                    | scripts/bin/workspace                                    |
| workspace_audit                      | governance | managed | bin-master, scripts-compat-shim | -   | bin/ssot/workspace-audit                         | scripts/bin/ssot/workspace-audit                         |
| write_owner_audit                    | governance | managed | bin-master, scripts-compat-shim | -   | bin/ssot/write-owner-audit.py                    | scripts/bin/ssot/write-owner-audit.py                    |
| write_owner_repair_draft             | governance | managed | bin-master, scripts-compat-shim | -   | bin/_archive/2026-08-conv3/write-owner-repair-draft.py             | scripts/bin/_archive/2026-08-conv3/write-owner-repair-draft.py             |
| yaml_validate                        | governance | managed | bin-master, scripts-compat-shim | -   | bin/ssot/yaml-validate.py                        | scripts/bin/ssot/yaml-validate.py                        |

## 四、`bin-ssot-master, root-wrapper, scripts-compat-shim`（SSOT wrapper）

共 2 条
| name                        | owner      | status  | action                                             | due | bin                                     | scripts                                         |
| --------------------------- | ---------- | ------- | -------------------------------------------------- | --- | --------------------------------------- | ----------------------------------------------- |
| submodule_reachability_gate | governance | managed | bin-ssot-master, root-wrapper, scripts-compat-shim | -   | bin/ssot/submodule-reachability-gate.py | scripts/bin/ssot/submodule-reachability-gate.py |
| sync_submodules_push        | governance | managed | bin-ssot-master, root-wrapper, scripts-compat-shim | -   | bin/ssot/sync-submodules-push.sh        | scripts/bin/ssot/sync-submodules-push.sh        |


## 五、实施建议

- **阶段策略**：
  - 第一优先：保持 `close-duplicate-gap-first` 组 manifest 约定不变，按 owner 落地到对应项目或子域。
  - 第二优先：每周执行一次 `make bin-tool-registry-scripts-necessity`，复核新增并行缺口并回填 manifest。
  - 第三优先：对高频调用脚本，确保根 `bin` 与 `scripts/bin` 的 shim 行为一致，并保留兼容入口。
