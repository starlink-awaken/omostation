from __future__ import annotations

import json
from pathlib import Path

import yaml
from omo.omo_governance import main as omo_governance_main
from omo.omo_governance_surfaces import build_governance_surfaces_report


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _write_yaml(path: Path, payload: dict) -> None:
    _write(path, yaml.dump(payload, allow_unicode=True, sort_keys=False))


def _seed_workspace(root: Path) -> None:
    omo = root / ".omo"
    for rel in [
        "_truth/registry",
        "_truth/goals/history",
        "standards",
        "_control",
        "_knowledge",
        "_delivery",
        "_delivery/evidence-legacy",
        "_archive",
        "tasks/planned",
        "state",
        "debt",
        "workers",
    ]:
        (omo / rel).mkdir(parents=True, exist_ok=True)
    (omo / "evidence").symlink_to("_delivery/evidence-legacy")
    (omo / "goals").symlink_to("_truth/goals")
    _write_yaml(
        omo / "_truth" / "goals" / "current.yaml",
        {
            "goals": [
                {
                    "id": "G1",
                    "desc": "seed goal",
                    "progress": 0.0,
                    "status": "pending",
                    "tasks": [],
                }
            ]
        },
    )

    _write(
        omo / "standards" / "omo-governance-surfaces.md",
        "# OMO Governance Surfaces Standard\n",
    )
    _write_yaml(
        omo / "_truth" / "registry" / "omo-governance-surfaces.yaml",
        {
            "assets": [
                {
                    "ref": ".omo/_truth/",
                    "status": "active",
                    "plane": "state_plane",
                    "asset_type": "authority",
                    "persistence_mode": "authoritative",
                    "retention_mode": "until_replaced",
                },
                {
                    "ref": ".omo/_control/",
                    "status": "active",
                    "plane": "state_plane",
                    "asset_type": "control_state",
                    "persistence_mode": "operational",
                    "retention_mode": "rolling_window",
                },
                {
                    "ref": ".omo/_knowledge/",
                    "status": "active",
                    "plane": "state_plane",
                    "asset_type": "knowledge_state",
                    "persistence_mode": "durable",
                    "retention_mode": "manual_cleanup",
                },
                {
                    "ref": ".omo/_delivery/",
                    "status": "active",
                    "plane": "state_plane",
                    "asset_type": "delivery_state",
                    "persistence_mode": "append_only",
                    "retention_mode": "manual_archive",
                },
                {
                    "ref": ".omo/_archive/",
                    "status": "active",
                    "plane": "state_plane",
                    "asset_type": "archived_state",
                    "persistence_mode": "archival",
                    "retention_mode": "manual_archive",
                },
                {
                    "ref": ".omo/tasks/",
                    "status": "active",
                    "plane": "state_plane",
                    "asset_type": "workflow_state",
                    "persistence_mode": "operational",
                    "retention_mode": "manual_archive",
                },
                {
                    "ref": ".omo/state/",
                    "status": "active",
                    "plane": "state_plane",
                    "asset_type": "runtime_ssot",
                    "persistence_mode": "operational",
                    "retention_mode": "until_replaced",
                },
                {
                    "ref": ".omo/debt/",
                    "status": "active",
                    "plane": "state_plane",
                    "asset_type": "governance_program",
                    "persistence_mode": "durable",
                    "retention_mode": "manual_archive",
                },
                {
                    "ref": ".omo/debt/dashboard/",
                    "status": "active",
                    "plane": "state_plane",
                    "asset_type": "governance_review_surface",
                    "persistence_mode": "durable",
                    "retention_mode": "until_replaced",
                },
                {
                    "ref": ".omo/debt/review-queue/",
                    "status": "active",
                    "plane": "state_plane",
                    "asset_type": "governance_review_surface",
                    "persistence_mode": "durable",
                    "retention_mode": "until_replaced",
                },
                {
                    "ref": ".omo/debt/reviews/",
                    "status": "active",
                    "plane": "state_plane",
                    "asset_type": "governance_review_surface",
                    "persistence_mode": "durable",
                    "retention_mode": "until_replaced",
                },
                {
                    "ref": ".omo/debt/action-packet/",
                    "status": "active",
                    "plane": "state_plane",
                    "asset_type": "governance_routing_surface",
                    "persistence_mode": "durable",
                    "retention_mode": "until_replaced",
                },
                {
                    "ref": ".omo/debt/owner-routing/",
                    "status": "active",
                    "plane": "state_plane",
                    "asset_type": "governance_routing_surface",
                    "persistence_mode": "durable",
                    "retention_mode": "until_replaced",
                },
                {
                    "ref": ".omo/debt/dispatch/",
                    "status": "active",
                    "plane": "state_plane",
                    "asset_type": "governance_dispatch_surface",
                    "persistence_mode": "durable",
                    "retention_mode": "manual_archive",
                },
                {
                    "ref": ".omo/debt/campaign/",
                    "status": "active",
                    "plane": "state_plane",
                    "asset_type": "governance_campaign_surface",
                    "persistence_mode": "durable",
                    "retention_mode": "manual_archive",
                },
                {
                    "ref": ".omo/debt/reporting/",
                    "status": "active",
                    "plane": "state_plane",
                    "asset_type": "governance_reporting_surface",
                    "persistence_mode": "durable",
                    "retention_mode": "manual_archive",
                },
                {
                    "ref": ".omo/workers/",
                    "status": "active",
                    "plane": "state_plane",
                    "asset_type": "execution_runtime",
                    "persistence_mode": "operational",
                    "retention_mode": "rolling_window",
                },
                {
                    "ref": ".omo/standards/",
                    "status": "active",
                    "plane": "state_plane",
                    "asset_type": "rule_docs",
                    "persistence_mode": "durable",
                    "retention_mode": "until_replaced",
                },
                {
                    "ref": ".omo/capabilities/",
                    "status": "active",
                    "plane": "state_plane",
                    "asset_type": "capability_market",
                    "persistence_mode": "durable",
                    "retention_mode": "until_replaced",
                },
                {
                    "ref": ".omo/evidence/",
                    "status": "active",
                    "plane": "state_plane",
                    "asset_type": "compatibility_alias",
                    "persistence_mode": "compatibility_alias",
                    "retention_mode": "alias_only",
                    "alias_target": ".omo/_delivery/evidence-legacy/",
                },
                {
                    "ref": ".omo/goals/",
                    "status": "active",
                    "plane": "state_plane",
                    "asset_type": "goal_state",
                    "persistence_mode": "authoritative",
                    "retention_mode": "until_replaced",
                },
            ]
        },
    )
    _write_yaml(
        omo / "_truth" / "registry" / "task-policies.yaml",
        {
            "policies": [
                {
                    "name": "active-execution-links",
                    "summary": "active/ 中的 in_progress/review 任务必须具备 dispatch/run/review 等链路字段",
                    "target_roots": ["active"],
                    "file_glob": "*.yaml",
                    "prohibited_roots": [],
                    "required_fields": {},
                    "required_status": None,
                    "allowed_statuses": [],
                    "validator_id": "active_execution_links",
                },
                {
                    "name": "active-review-ref",
                    "summary": "active/ 下 review 态任务必须带 review_ref 且指向真实审查工件",
                    "target_roots": ["active"],
                    "file_glob": "*.yaml",
                    "prohibited_roots": [],
                    "required_fields": {},
                    "required_status": None,
                    "allowed_statuses": [],
                    "validator_id": "active_review_ref",
                },
                {
                    "name": "done-directory-status",
                    "summary": "done/ 目录中的任务必须显式保持 status=done",
                    "target_roots": ["done"],
                    "file_glob": "*.yaml",
                    "prohibited_roots": [],
                    "required_fields": {},
                    "required_status": "done",
                    "allowed_statuses": [],
                    "validator_id": None,
                },
                {
                    "name": "modern-done-completion-marker",
                    "summary": "新式 done packet 必须带 completed_at 或 completed 完成标记",
                    "target_roots": ["done"],
                    "file_glob": "*.yaml",
                    "prohibited_roots": [],
                    "required_fields": {},
                    "required_status": None,
                    "allowed_statuses": [],
                    "validator_id": "modern_done_completion_marker",
                },
                {
                    "name": "modern-done-evidence-paths",
                    "summary": "新式 done packet 一旦声明 evidence_paths，其目标文件必须物理存在",
                    "target_roots": ["done"],
                    "file_glob": "*.yaml",
                    "prohibited_roots": [],
                    "required_fields": {},
                    "required_status": None,
                    "allowed_statuses": [],
                    "validator_id": "modern_done_evidence_paths",
                },
                {
                    "name": "remediation-review-note",
                    "summary": "remediation/ 下 review 态任务必须带 review_note 且指向真实审查笔记",
                    "target_roots": ["remediation"],
                    "file_glob": "*.yaml",
                    "prohibited_roots": [],
                    "required_fields": {},
                    "required_status": None,
                    "allowed_statuses": [],
                    "validator_id": "remediation_review_note",
                },
                {
                    "name": "self-evolution-approval",
                    "summary": "self-evolution 任务只能留在 planned/，且审批字段必须保持人工待批基线",
                    "target_roots": ["planned"],
                    "file_glob": "OPC-P6-SELF-EVOLUTION-*.yaml",
                    "prohibited_roots": ["active"],
                    "required_fields": {
                        "approval_required": True,
                        "human_approval_required": True,
                        "approval_state": "awaiting_human",
                    },
                    "required_status": None,
                    "allowed_statuses": ["candidate"],
                    "validator_id": None,
                },
                {
                    "name": "human-approval-ref",
                    "summary": "human_approval_required 的 planned/review 任务必须绑定 task-specific promotion approval yaml",
                    "target_roots": ["planned", "remediation"],
                    "file_glob": "*.yaml",
                    "prohibited_roots": [],
                    "required_fields": {},
                    "required_status": None,
                    "allowed_statuses": [],
                    "validator_id": "human_approval_ref",
                },
            ]
        },
    )
    _write_yaml(
        omo / "_truth" / "registry" / "mutation-surfaces.yaml",
        {
            "surfaces": [
                {
                    "name": "omo-governance-ingress-goal",
                    "entrypoint": "omo governance ingress-goal",
                    "runtime_ref": "projects/omo/src/omo/omo_governance.py:main (command=ingress-goal)",
                    "mutation_target": ".omo/goals/current.yaml",
                    "broker_ref": "projects/omo/src/omo/omo_ingress.py:create_goal",
                    "delivery_artifact_root": "runtime/omo/_delivery/ingress/goals/",
                    "mode": "brokered",
                    "category": "governance_ingress",
                },
                {
                    "name": "omo-governance-ingress-task",
                    "entrypoint": "omo governance ingress-task",
                    "runtime_ref": "projects/omo/src/omo/omo_governance.py:main (command=ingress-task)",
                    "mutation_target": ".omo/tasks/planned/",
                    "broker_ref": "projects/omo/src/omo/omo_ingress.py:create_planned_task",
                    "delivery_artifact_root": "runtime/omo/_delivery/ingress/tasks/",
                    "mode": "brokered",
                    "category": "governance_ingress",
                },
                {
                    "name": "omo-governance-ingress-debt",
                    "entrypoint": "omo governance ingress-debt",
                    "runtime_ref": "projects/omo/src/omo/omo_governance.py:main (command=ingress-debt)",
                    "mutation_target": ".omo/debt/items/ + .omo/debt/registry.yaml",
                    "broker_ref": "projects/omo/src/omo/omo_ingress.py:upsert_debt_item",
                    "delivery_artifact_root": "runtime/omo/_delivery/ingress/debts/",
                    "mode": "brokered",
                    "category": "governance_ingress",
                },
                {
                    "name": "omo-goal-create",
                    "entrypoint": "omo goal create",
                    "runtime_ref": "projects/omo/src/omo/omo_goal.py:cmd_goal_create",
                    "mutation_target": ".omo/goals/current.yaml",
                    "broker_ref": "projects/omo/src/omo/omo_ingress.py:create_goal",
                    "delivery_artifact_root": "runtime/omo/_delivery/ingress/goals/",
                    "mode": "brokered",
                    "category": "human_cli",
                },
                {
                    "name": "omo-goal-progress",
                    "entrypoint": "omo goal progress",
                    "runtime_ref": "projects/omo/src/omo/omo_goal.py:cmd_goal_progress",
                    "mutation_target": ".omo/goals/current.yaml",
                    "broker_ref": "projects/omo/src/omo/omo_ingress.py:update_goal_progress",
                    "delivery_artifact_root": "runtime/omo/_delivery/ingress/goals/",
                    "mode": "brokered",
                    "category": "human_cli",
                },
                {
                    "name": "omo-goal-reconcile",
                    "entrypoint": "omo goal reconcile",
                    "runtime_ref": "projects/omo/src/omo/omo_goal.py:cmd_goal_reconcile",
                    "mutation_target": ".omo/goals/current.yaml",
                    "broker_ref": "projects/omo/src/omo/omo_ingress.py:reconcile_goals",
                    "delivery_artifact_root": "runtime/omo/_delivery/ingress/goals/",
                    "mode": "brokered",
                    "category": "human_cli",
                },
                {
                    "name": "omo-task-create",
                    "entrypoint": "omo task create",
                    "runtime_ref": "projects/omo/src/omo/omo_task.py:cmd_task_create",
                    "mutation_target": ".omo/tasks/planned/",
                    "broker_ref": "projects/omo/src/omo/omo_ingress.py:create_planned_task",
                    "delivery_artifact_root": "runtime/omo/_delivery/ingress/tasks/",
                    "mode": "brokered",
                    "category": "human_cli",
                },
                {
                    "name": "omo-task-done",
                    "entrypoint": "omo task done",
                    "runtime_ref": "projects/omo/src/omo/omo_task.py:cmd_task_done",
                    "mutation_target": ".omo/tasks/active/|planned/ -> .omo/tasks/done/",
                    "broker_ref": "projects/omo/src/omo/omo_ingress.py:complete_task",
                    "delivery_artifact_root": "runtime/omo/_delivery/ingress/tasks/",
                    "mode": "brokered",
                    "category": "human_cli",
                },
                {
                    "name": "omo-task-refresh-evidence",
                    "entrypoint": "omo task refresh-evidence",
                    "runtime_ref": "projects/omo/src/omo/omo_task.py:cmd_task_refresh_evidence",
                    "mutation_target": ".omo/tasks/done/*.yaml (evidence_paths)",
                    "broker_ref": "projects/omo/src/omo/omo_ingress.py:update_done_task_evidence_paths",
                    "delivery_artifact_root": "runtime/omo/_delivery/ingress/tasks/",
                    "mode": "brokered",
                    "category": "human_cli",
                },
                {
                    "name": "omo-task-repair-approval",
                    "entrypoint": "omo task repair-approval",
                    "runtime_ref": "projects/omo/src/omo/omo_task.py:cmd_task_repair_approval",
                    "mutation_target": ".omo/tasks/{planned,active,done,remediation}/*.yaml (approval_ref) + .omo/workers/runs/*-promotion-approval-*.yaml",
                    "broker_ref": "projects/omo/src/omo/omo_ingress.py:repair_task_promotion_approval",
                    "delivery_artifact_root": "runtime/omo/_delivery/ingress/tasks/",
                    "mode": "brokered",
                    "category": "human_cli",
                },
                {
                    "name": "omo-worker-task-normalize-planned",
                    "entrypoint": "uv run python -m omo.cli worker task normalize-planned",
                    "workdir": "projects/omo",
                    "runtime_ref": "projects/omo/src/omo/omo_worker_cmd_task.py:execute_task_command (task_command=normalize-planned)",
                    "mutation_target": ".omo/tasks/planned/ + .omo/tasks/archived/legacy-normalized/",
                    "broker_ref": "projects/omo/src/omo/omo_ingress.py:normalize_legacy_planned_task",
                    "delivery_artifact_root": "runtime/omo/_delivery/ingress/tasks/",
                    "mode": "brokered",
                    "category": "governance_ingress",
                },
                {
                    "name": "omo-worker-task-route-self-evolution-remediation",
                    "entrypoint": "uv run python -m omo.cli worker task route-self-evolution-remediation",
                    "workdir": "projects/omo",
                    "runtime_ref": "projects/omo/src/omo/omo_worker_cmd_task.py:execute_task_command (task_command=route-self-evolution-remediation)",
                    "mutation_target": ".omo/tasks/planned/ -> .omo/tasks/remediation/ + .omo/tasks/remediation-notes/",
                    "broker_ref": "projects/omo/src/omo/omo_ingress.py:route_self_evolution_to_remediation",
                    "delivery_artifact_root": "runtime/omo/_delivery/ingress/tasks/",
                    "mode": "brokered",
                    "category": "governance_ingress",
                },
                {
                    "name": "opc-p6-self-evolve-task-emit",
                    "entrypoint": "python3 scripts/opc_p6_self_evolve.py",
                    "runtime_ref": "projects/omo/src/omo/omo_self_evolve.py:write_planned_self_evolution_tasks",
                    "mutation_target": ".omo/tasks/planned/",
                    "broker_ref": "projects/omo/src/omo/omo_ingress.py:create_planned_task",
                    "delivery_artifact_root": "runtime/omo/_delivery/ingress/tasks/",
                    "mode": "brokered",
                    "category": "governance_ingress",
                },
                {
                    "name": "omo-knowledge-add",
                    "entrypoint": "omo knowledge add",
                    "runtime_ref": "projects/omo/src/omo/omo_knowledge.py:cmd_knowledge_add",
                    "mutation_target": ".omo/_knowledge/",
                    "broker_ref": "projects/omo/src/omo/omo_ingress.py:create_knowledge_doc",
                    "delivery_artifact_root": "runtime/omo/_delivery/ingress/knowledge/",
                    "mode": "brokered",
                    "category": "human_cli",
                },
                {
                    "name": "omo-standard-add",
                    "entrypoint": "omo standard add",
                    "runtime_ref": "projects/omo/src/omo/omo_standard.py:cmd_standard_add",
                    "mutation_target": ".omo/standards/",
                    "broker_ref": "projects/omo/src/omo/omo_ingress.py:create_standard_doc",
                    "delivery_artifact_root": "runtime/omo/_delivery/ingress/standards/",
                    "mode": "brokered",
                    "category": "human_cli",
                },
                {
                    "name": "omo-capability-registry-scan",
                    "entrypoint": "omo-capability capability scan --write",
                    "runtime_ref": "projects/omo/src/omo/omo_capability.py:scan_command",
                    "mutation_target": ".omo/capabilities/INDEX.md + .omo/capabilities/projects-capabilities.yaml + .omo/capabilities/sharedwork-sample.yaml + .omo/capabilities/system-packages.yaml + .omo/capabilities/agent-clis.yaml",
                    "broker_ref": "projects/omo/src/omo/omo_ingress.py:write_capability_registry_bundle",
                    "delivery_artifact_root": "runtime/omo/_delivery/ingress/capabilities/",
                    "mode": "brokered",
                    "category": "human_cli",
                },
                {
                    "name": "omo-capability-registry-register",
                    "entrypoint": "omo-capability capability register <file>",
                    "runtime_ref": "projects/omo/src/omo/omo_capability.py:register_command",
                    "mutation_target": ".omo/capabilities/manual-capabilities.yaml",
                    "broker_ref": "projects/omo/src/omo/omo_ingress.py:write_manual_capabilities",
                    "delivery_artifact_root": "runtime/omo/_delivery/ingress/capabilities/",
                    "mode": "brokered",
                    "category": "human_cli",
                },
                {
                    "name": "omo-task-center-skill-manifest",
                    "entrypoint": "projects/omo/src/omo/omo_skill.py:register_skill_manifest",
                    "runtime_ref": "projects/omo/src/omo/omo_skill.py:register_skill_manifest",
                    "mutation_target": ".omo/_truth/task-center/skills/*.yaml",
                    "broker_ref": "projects/omo/src/omo/omo_ingress.py:create_skill_manifest",
                    "delivery_artifact_root": "runtime/omo/_delivery/ingress/task-center/skills/",
                    "mode": "brokered",
                    "category": "governance_ingress",
                },
                {
                    "name": "omo-task-center-discovery-registry",
                    "entrypoint": "projects/omo/src/omo/omo_discovery.py:discover_task_blueprints",
                    "runtime_ref": "projects/omo/src/omo/omo_discovery.py:discover_task_blueprints",
                    "mutation_target": ".omo/_truth/task-center/discovery-registry.yaml",
                    "broker_ref": "projects/omo/src/omo/omo_ingress.py:write_discovery_registry",
                    "delivery_artifact_root": "runtime/omo/_delivery/ingress/task-center/discovery/",
                    "mode": "brokered",
                    "category": "governance_ingress",
                },
                {
                    "name": "omo-self-healing-debt",
                    "entrypoint": "projects/omo/src/omo/omo_self_healing.py:SelfHealingEngine._create_debt",
                    "runtime_ref": "projects/omo/src/omo/omo_self_healing.py:SelfHealingEngine._create_debt",
                    "mutation_target": ".omo/debt/items/*.yaml + .omo/_truth/registry/debt.yaml",
                    "broker_ref": "projects/omo/src/omo/omo_ingress.py:upsert_debt_item",
                    "delivery_artifact_root": "runtime/omo/_delivery/ingress/debts/",
                    "mode": "brokered",
                    "category": "governance_ingress",
                },
                {
                    "name": "omo-bridge-bmad-openspec",
                    "entrypoint": "omo bridge --format bmad|openspec",
                    "runtime_ref": "projects/omo/src/omo/omo_bridge.py:_import_bmad",
                    "mutation_target": ".omo/tasks/planned/",
                    "broker_ref": "projects/omo/src/omo/omo_ingress.py:create_planned_task",
                    "delivery_artifact_root": "runtime/omo/_delivery/ingress/tasks/",
                    "mode": "brokered",
                    "category": "bridge_import",
                },
                {
                    "name": "omo-bridge-fast-track",
                    "entrypoint": "omo bridge --format fast_track",
                    "runtime_ref": "projects/omo/src/omo/omo_bridge.py:_import_fast_track",
                    "mutation_target": ".omo/tasks/planned/",
                    "broker_ref": "projects/omo/src/omo/omo_ingress.py:create_planned_task",
                    "delivery_artifact_root": "runtime/omo/_delivery/ingress/tasks/",
                    "mode": "brokered",
                    "category": "bridge_import",
                },
                {
                    "name": "omo-bridge-pitch",
                    "entrypoint": "omo bridge --format pitch",
                    "runtime_ref": "projects/omo/src/omo/omo_bridge.py:_import_pitch",
                    "mutation_target": ".omo/goals/current.yaml + .omo/tasks/planned/",
                    "broker_ref": "projects/omo/src/omo/omo_goal.py:cmd_goal_create + projects/omo/src/omo/omo_ingress.py:create_planned_task",
                    "delivery_artifact_root": "runtime/omo/_delivery/ingress/goals/ + runtime/omo/_delivery/ingress/tasks/",
                    "mode": "brokered",
                    "category": "bridge_import",
                },
                {
                    "name": "ecos-mof-state-bridge-m1-to-omo",
                    "entrypoint": "python3 projects/ecos/src/ecos/ssot/tools/mof-state-bridge.py --m1-to-omo",
                    "runtime_ref": "projects/ecos/src/ecos/ssot/tools/mof-state-bridge.py:main (flag=--m1-to-omo)",
                    "mutation_target": ".omo/tasks/planned/",
                    "broker_ref": "projects/omo/src/omo/omo_ingress.py:create_planned_task",
                    "delivery_artifact_root": "runtime/omo/_delivery/ingress/tasks/",
                    "mode": "brokered",
                    "category": "bridge_import",
                },
                {
                    "name": "c2g-storage-save-bet",
                    "entrypoint": "projects/c2g/src/c2g/adapters.py:EcosStorageProvider.save_bet",
                    "runtime_ref": "projects/c2g/src/c2g/adapters.py:EcosStorageProvider.save_bet",
                    "mutation_target": ".omo/goals/current.yaml",
                    "broker_ref": "projects/omo/src/omo/omo_ingress.py:create_goal",
                    "delivery_artifact_root": "runtime/omo/_delivery/ingress/goals/",
                    "mode": "brokered",
                    "category": "c2g_adapter",
                },
                {
                    "name": "c2g-storage-save-task",
                    "entrypoint": "projects/c2g/src/c2g/adapters.py:EcosStorageProvider.save_task",
                    "runtime_ref": "projects/c2g/src/c2g/adapters.py:EcosStorageProvider.save_task",
                    "mutation_target": ".omo/tasks/planned/",
                    "broker_ref": "projects/omo/src/omo/omo_ingress.py:create_planned_task",
                    "delivery_artifact_root": "runtime/omo/_delivery/ingress/tasks/",
                    "mode": "brokered",
                    "category": "c2g_adapter",
                },
                {
                    "name": "omo-state-refresh",
                    "entrypoint": "omo state refresh",
                    "runtime_ref": "projects/omo/src/omo/omo_state.py:cmd_state_refresh",
                    "mutation_target": ".omo/state/runtime/system_health.yaml + .omo/state/system_health.yaml",
                    "broker_ref": None,
                    "delivery_artifact_root": None,
                    "mode": "direct-runtime-cache",
                    "category": "runtime_cache",
                },
                {
                    "name": "omo-state-sync-tasks",
                    "entrypoint": "omo state sync-tasks",
                    "runtime_ref": "projects/omo/src/omo/omo_state.py:cmd_state_sync_tasks",
                    "mutation_target": ".omo/state/system.yaml (task counters + next_* projection)",
                    "broker_ref": "projects/omo/src/omo/omo_ingress.py:write_system_projection_fields",
                    "delivery_artifact_root": "runtime/omo/_delivery/ingress/state/",
                    "mode": "brokered",
                    "category": "governance_ingress",
                },
                {
                    "name": "omo-state-sync-projection",
                    "entrypoint": "omo state sync",
                    "runtime_ref": "projects/omo/src/omo/omo_state.py:cmd_state_sync",
                    "mutation_target": ".omo/state/health.yaml + .omo/state/system.yaml + BRIEF.md + .omo/_control/governance-data.json",
                    "broker_ref": "projects/omo/src/omo/omo_ingress_state.py:sync_state_projection",
                    "delivery_artifact_root": "runtime/omo/_delivery/ingress/state/",
                    "mode": "brokered",
                    "category": "governance_ingress",
                },
                {
                    "name": "omo-audit-sync-system-projection",
                    "entrypoint": "python -m omo.omo_audit_sync --apply",
                    "runtime_ref": "projects/omo/src/omo/omo_audit_sync.py:apply_diff",
                    "mutation_target": ".omo/state/system.yaml (whitelisted audit projection fields)",
                    "broker_ref": "projects/omo/src/omo/omo_ingress.py:write_system_projection_fields",
                    "delivery_artifact_root": "runtime/omo/_delivery/ingress/state/",
                    "mode": "brokered",
                    "category": "runtime_cache",
                },
            ]
        },
    )
    _write_yaml(
        omo / "_truth" / "registry" / "internal-write-profiles.yaml",
        {
            "profiles": [
                {
                    "name": "worker-dispatch",
                    "runtime_ref": "projects/omo/src/omo/omo_worker_dispatch.py:dispatch_task",
                    "category": "worker_internal",
                    "subtype": "dispatch_runtime",
                    "writes": [
                        ".omo/workers/runs/*-dispatch.yaml",
                        ".omo/workers/runs/*-envelope.yaml",
                        ".omo/workers/runs/*-prompt.md",
                        ".omo/workers/runs/*-checkpoint.md",
                        ".omo/workers/runs/*-reclaim.md",
                        ".omo/workers/runs/*-review.md",
                        ".omo/workers/runs/*-stdout.log",
                        ".omo/tasks/active/*.yaml",
                    ],
                    "promotion_surface": False,
                    "note": "内部调度运行态；不是人类/bridge 入口",
                },
                {
                    "name": "worker-task-lifecycle",
                    "runtime_ref": "projects/omo/src/omo/omo_worker_dispatch.py:yield_task + _fast_track_compaction",
                    "category": "worker_internal",
                    "subtype": "task_lifecycle_runtime",
                    "writes": [
                        ".omo/workers/runs/*-dispatch.yaml",
                        ".omo/tasks/planned/*.yaml",
                        ".omo/tasks/archived/*.yaml",
                        ".omo/_knowledge/audits/*.md",
                        "runtime/omo/_delivery/ingress/tasks/*-yield-*.yaml",
                        "runtime/omo/_delivery/ingress/tasks/*-archive-*.yaml",
                        "runtime/omo/_delivery/ingress/audits/*.yaml",
                    ],
                    "promotion_surface": False,
                    "note": "内部任务回退与 Fast-Track 归档链路；通过 broker 持久化",
                },
                {
                    "name": "worker-self-evolution-remediation",
                    "runtime_ref": "projects/omo/src/omo/omo_worker_promotion.py:_route_self_evolution_packet_to_remediation",
                    "category": "worker_internal",
                    "subtype": "remediation_runtime",
                    "writes": [
                        ".omo/tasks/planned/*.yaml",
                        ".omo/tasks/remediation/*.yaml",
                        ".omo/tasks/remediation-notes/*.md",
                        "runtime/omo/_delivery/ingress/tasks/*-route-self-evolution-*.yaml",
                    ],
                    "promotion_surface": False,
                    "note": "self-evolution 专用 review lane；已批但不可入 active 的包转入 remediation",
                },
                {
                    "name": "worker-promotion",
                    "runtime_ref": "projects/omo/src/omo/omo_worker_promotion.py:_apply_task_promotion",
                    "category": "worker_internal",
                    "subtype": "promotion_runtime",
                    "writes": [
                        ".omo/workers/runs/*-promotion-*.yaml",
                        "runtime/omo/_delivery/ingress/tasks/*-promote-*.yaml",
                        "runtime/omo/_delivery/ingress/tasks/*-revert-*.yaml",
                        ".omo/state/system.yaml (via sync_omo_state.py)",
                    ],
                    "promotion_surface": True,
                    "note": "内部晋升与回滚链路；task 生命周期迁移已通过 ingress broker 持久化",
                },
                {
                    "name": "worker-status",
                    "runtime_ref": "projects/omo/src/omo/omo_worker_status.py:update_dispatch_checkpoint",
                    "category": "worker_internal",
                    "subtype": "checkpoint_runtime",
                    "writes": [
                        ".omo/workers/runs/*-checkpoint.md",
                        ".omo/workers/runs/*-dispatch.yaml",
                    ],
                    "promotion_surface": False,
                    "note": "内部 checkpoint/lease 续写",
                },
                {
                    "name": "worker-approval-runtime",
                    "runtime_ref": "projects/omo/src/omo/omo_worker_promotion.py:_request_task_promotion_approval_record + projects/omo/src/omo/omo_admission.py:request_conditional_approval",
                    "category": "worker_internal",
                    "subtype": "approval_runtime",
                    "writes": [
                        ".omo/workers/runs/*-promotion-approval-*.yaml",
                        ".omo/workers/runs/*-approval.yaml",
                        ".omo/_truth/task-center/proposals/*.yaml",
                        "runtime/omo/_delivery/ingress/tasks/*-promotion-approval-*.yaml",
                        "runtime/omo/_delivery/ingress/tasks/*-contract-request-*.yaml",
                    ],
                    "promotion_surface": True,
                    "note": "内部审批请求与 contract-request 链路；planned/active task 补丁已通过 ingress broker 落盘",
                },
                {
                    "name": "worker-rollout-runtime",
                    "runtime_ref": "projects/omo/src/omo/omo_rollout.py:accept_rollout_envelope",
                    "category": "worker_internal",
                    "subtype": "rollout_runtime",
                    "writes": [
                        ".omo/workers/runs/*-acceptance.yaml",
                        ".omo/workers/runs/*-envelope.yaml",
                    ],
                    "promotion_surface": False,
                    "note": "内部 rollout acceptance 续写",
                },
                {
                    "name": "worker-experience-runtime",
                    "runtime_ref": "projects/omo/src/omo/omo_experience.py",
                    "category": "worker_internal",
                    "subtype": "experience_runtime",
                    "writes": [
                        ".omo/tasks/blocked/*.yaml",
                        ".omo/_delivery/task-center/consensus/*.yaml",
                        ".omo/_truth/task-center/usage-accounting.yaml",
                        ".omo/_delivery/task-center/freshness/current.yaml",
                        ".omo/_delivery/task-center/control/current.yaml",
                        ".omo/summaries/*.md",
                        "runtime/omo/_delivery/ingress/tasks/*-blocked-*.yaml",
                        "runtime/omo/_delivery/ingress/tasks/*-consensus-*.yaml",
                        "runtime/omo/_delivery/ingress/task-center/*.yaml",
                    ],
                    "promotion_surface": False,
                    "note": "复杂请求桥接与 task-center truth/control 产物已通过 ingress broker 落盘；summary markdown 保留为运行时写出",
                },
                {
                    "name": "worker-overlay-runtime",
                    "runtime_ref": "projects/omo/src/omo/omo_worker_promotion.py:_write_task_governance_overlay_* + _write_task_promotion_*",
                    "category": "worker_internal",
                    "subtype": "analytics_runtime",
                    "writes": [
                        ".omo/_truth/governance-overlay/roadmap.yaml",
                        ".omo/_control/governance-overlay/current.yaml",
                        "runtime/omo/_delivery/ingress/governance-overlay/*.yaml",
                        ".omo/workers/promotion/current.yaml",
                        ".omo/workers/promotion/current.md",
                        ".omo/workers/promotion/readiness.yaml",
                        ".omo/workers/promotion/readiness.md",
                        ".omo/workers/promotion/approvals/**/current.yaml",
                        ".omo/workers/promotion/approvals/**/current.md",
                        ".omo/workers/governance-overlay/**/current.yaml",
                        ".omo/workers/governance-overlay/**/current.md",
                    ],
                    "promotion_surface": False,
                    "note": "governance overlay roadmap/control 已通过 ingress broker 持久化；shell current 与 approval analytics 仍为运行时快照",
                },
                {
                    "name": "debt-review-runtime",
                    "runtime_ref": "projects/omo/src/omo/omo_debt.py:refresh_outputs + write_dashboard + write_review_queue + write_review_pack + projects/omo/src/omo/omo_debt_io.py:write_dashboard + write_review_queue",
                    "category": "kernel_internal",
                    "subtype": "governance_review_runtime",
                    "writes": [
                        ".omo/debt/dashboard/current.yaml",
                        ".omo/debt/review-queue/current.yaml",
                        ".omo/debt/reviews/current.md",
                    ],
                    "promotion_surface": False,
                    "note": "debt review 面板与审查包由 OMO 内核直接生成；属于治理巡检输出",
                },
                {
                    "name": "debt-routing-runtime",
                    "runtime_ref": "projects/omo/src/omo/omo_debt.py:refresh_outputs + write_action_packet + write_owner_routing + projects/omo/src/omo/omo_debt_io.py:write_action_packet + write_owner_routing",
                    "category": "kernel_internal",
                    "subtype": "governance_routing_runtime",
                    "writes": [
                        ".omo/debt/action-packet/current.yaml",
                        ".omo/debt/action-packet/current.md",
                        ".omo/debt/owner-routing/current.yaml",
                        ".omo/debt/owner-routing/current.md",
                    ],
                    "promotion_surface": False,
                    "note": "debt action packet 与 owner routing 由 OMO 内核直接生成；属于治理分发前置产物",
                },
                {
                    "name": "debt-dispatch-runtime",
                    "runtime_ref": "projects/omo/src/omo/omo_debt.py:dispatch_outputs + write_dispatch_packet + projects/omo/src/omo/omo_debt_io.py:write_dispatch_packet",
                    "category": "kernel_internal",
                    "subtype": "governance_dispatch_runtime",
                    "writes": [
                        ".omo/debt/dispatch/current.yaml",
                        ".omo/debt/dispatch/current.md",
                        ".omo/debt/dispatch/runs/*.yaml",
                        ".omo/debt/dispatch/runs/*.md",
                    ],
                    "promotion_surface": False,
                    "note": "debt dispatch current/runs 产物由 OMO 内核直接生成；属于治理派发执行面",
                },
                {
                    "name": "debt-campaign-runtime",
                    "runtime_ref": "projects/omo/src/omo/omo_debt.py:write_campaign_packet + build_selected_campaign_packet + projects/omo/src/omo/omo_debt_io.py:write_campaign_packet",
                    "category": "kernel_internal",
                    "subtype": "governance_campaign_runtime",
                    "writes": [
                        ".omo/debt/campaign/current.yaml",
                        ".omo/debt/campaign/current.md",
                        ".omo/debt/campaign/runs/**/current.yaml",
                        ".omo/debt/campaign/runs/**/current.md",
                    ],
                    "promotion_surface": False,
                    "note": "debt campaign current/runs 产物由 OMO 内核直接生成；属于治理专项推进面",
                },
                {
                    "name": "debt-reporting-runtime",
                    "runtime_ref": "projects/omo/src/omo/omo_debt.py:write_reporting_* + load_reporting_history_packet + _reporting_history_inputs + projects/omo/src/omo/omo_debt_io.py:write_reporting_*",
                    "category": "kernel_internal",
                    "subtype": "governance_reporting_runtime",
                    "writes": [
                        ".omo/debt/reporting/current.yaml",
                        ".omo/debt/reporting/current.md",
                        ".omo/debt/reporting/runs/**/current.yaml",
                        ".omo/debt/reporting/runs/**/current.md",
                        ".omo/debt/reporting/history/current.yaml",
                        ".omo/debt/reporting/history/current.md",
                        ".omo/debt/reporting/diff/current.yaml",
                        ".omo/debt/reporting/diff/current.md",
                        ".omo/debt/reporting/trend/current.yaml",
                        ".omo/debt/reporting/trend/current.md",
                    ],
                    "promotion_surface": False,
                    "note": "debt reporting/history/diff/trend 产物由 OMO 内核直接生成；属于治理报表分析面",
                },
            ]
        },
    )

    c2g_builder = root / "projects" / "c2g" / "src" / "c2g" / "task_builder.py"
    c2g_facade = root / "projects" / "c2g" / "src" / "c2g" / "omo_client.py"
    _write(
        c2g_facade,
        """
def validate_planned_task_data(task_data):
    return []
""".strip()
        + "\n",
    )
    _write(
        c2g_builder,
        """
def build_ecos_task(*args, **kwargs):
    return {
        "governance_refs": [
            ".omo/standards/omo-governance-surfaces.md",
            ".omo/_truth/registry/omo-governance-surfaces.yaml",
        ],
        "metadata": {"ingress_plane": "projects/c2g"},
    }
""".strip()
        + "\n",
    )
    _write(
        root / ".pre-commit-config.yaml",
        """
- repo: local
  hooks:
    - id: omo-direct-io-gate
      entry: uv run --directory projects/omo python -m omo.cli lint direct-omo-io
    - id: omo-task-policy-gate
      entry: uv run --directory projects/omo python -m omo.cli lint task-policy --all --workspace-root .
    - id: omo-mutation-surface-gate
      entry: uv run --directory projects/omo python -m omo.cli lint mutation-surfaces --workspace-root .
    - id: omo-internal-write-profile-gate
      entry: uv run --directory projects/omo python -m omo.cli lint internal-write-profiles --workspace-root .
    - id: omo-state-plane-asset-gate
      entry: uv run --directory projects/omo python -m omo.cli lint state-plane-assets --workspace-root .
    - id: omo-c2g-omo-boundary-gate
      entry: uv run --directory projects/omo python -m omo.cli lint c2g-omo-boundary --workspace-root .
    - id: omo-ingress-artifact-gate
      entry: uv run --directory projects/omo python -m omo.cli lint ingress-artifacts --workspace-root .
    - id: omo-mutation-ledger-gate
      entry: uv run --directory projects/omo python -m omo.cli lint mutation-ledger --workspace-root .
""".strip()
        + "\n",
    )
    ingress_dir = omo.parent / "runtime" / "omo" / "_delivery" / "ingress"
    ingress_dir.mkdir(parents=True, exist_ok=True)
    _write_yaml(
        ingress_dir / "registry.yaml",
        {
            "goals": {
                "by_id": {
                    "BET-1": {
                        "source_ref": "c2g:bet:BET-1",
                        "artifact_ref": "runtime/omo/_delivery/ingress/goals/BET-1.yaml",
                        "fingerprint": {"id": "BET-1"},
                        "created_at": "2026-06-18T00:00:00Z",
                    }
                },
                "by_source_ref": {"c2g:bet:BET-1": "BET-1"},
            },
            "tasks": {
                "by_id": {
                    "TASK-1": {
                        "source_ref": "c2g:task:TASK-1",
                        "artifact_ref": "runtime/omo/_delivery/ingress/tasks/TASK-1.yaml",
                        "fingerprint": {"id": "TASK-1"},
                        "created_at": "2026-06-18T00:01:00Z",
                    }
                },
                "by_source_ref": {"c2g:task:TASK-1": "TASK-1"},
            },
            "debts": {
                "by_id": {
                    "DEBT-1": {
                        "source_ref": "omo:debt:DEBT-1",
                        "artifact_ref": "runtime/omo/_delivery/ingress/debts/DEBT-1.yaml",
                        "fingerprint": {"id": "DEBT-1"},
                        "created_at": "2026-06-18T00:02:00Z",
                    }
                },
                "by_source_ref": {"omo:debt:DEBT-1": "DEBT-1"},
            },
            "capabilities": {
                "by_id": {
                    "bundle": {
                        "source_ref": "omo-capability:scan",
                        "artifact_ref": "runtime/omo/_delivery/ingress/capabilities/bundle-2026-06-18T00-03-00Z.yaml",
                        "fingerprint": {"kind": "bundle"},
                        "created_at": "2026-06-18T00:03:00Z",
                    },
                    "manual-capabilities": {
                        "source_ref": "omo-capability:register:manual.yaml",
                        "artifact_ref": "runtime/omo/_delivery/ingress/capabilities/manual-capabilities-2026-06-18T00-04-00Z.yaml",
                        "fingerprint": {"kind": "manual-capabilities"},
                        "created_at": "2026-06-18T00:04:00Z",
                    },
                },
                "by_source_ref": {
                    "omo-capability:scan": "bundle",
                    "omo-capability:register:manual.yaml": "manual-capabilities",
                },
            },
        },
    )
    _write_yaml(
        omo.parent
        / "runtime"
        / "omo"
        / "_delivery"
        / "ingress"
        / "goals"
        / "BET-1.yaml",
        {
            "kind": "goal_created",
            "goal_id": "BET-1",
            "title": "bet",
            "ingress_plane": "projects/c2g",
            "source_ref": "c2g:bet:BET-1",
            "created_at": "2026-06-18T00:00:00Z",
            "goal_ref": ".omo/goals/current.yaml",
        },
    )
    _write_yaml(
        omo.parent
        / "runtime"
        / "omo"
        / "_delivery"
        / "ingress"
        / "tasks"
        / "TASK-1.yaml",
        {
            "kind": "planned_task_created",
            "task_id": "TASK-1",
            "title": "task",
            "ingress_plane": "projects/c2g",
            "source_ref": "c2g:task:TASK-1",
            "created_at": "2026-06-18T00:01:00Z",
            "task_ref": ".omo/tasks/planned/TASK-1.yaml",
        },
    )
    _write_yaml(
        omo / "tasks" / "planned" / "TASK-1.yaml",
        {
            "id": "TASK-1",
            "title": "task",
            "status": "candidate",
            "task_type": "feature",
            "risk_level": "L0",
            "depends_on": [],
            "source_docs": ["spec.md"],
            "deliverables": ["代码"],
            "imported_via": "projects/c2g",
            "context_uri": "bos://memory/tasks/TASK-1",
            "assigned_to": None,
            "dispatch_id": None,
            "run_ref": None,
            "approval_ref": None,
            "review_ref": None,
            "knowledge_refs": [],
            "handoff_refs": [],
            "governance_refs": [".omo/standards/omo-governance-surfaces.md"],
            "entry_gate": [],
            "evidence_required": [],
            "test_plan": ["pytest"],
            "allowed_operation_level": "L0",
            "human_approval_required": False,
            "metadata": {},
        },
    )
    _write_yaml(
        omo.parent
        / "runtime"
        / "omo"
        / "_delivery"
        / "ingress"
        / "debts"
        / "DEBT-1.yaml",
        {
            "kind": "debt_upserted",
            "debt_id": "DEBT-1",
            "title": "debt",
            "ingress_plane": "projects/omo",
            "source_ref": "omo:debt:DEBT-1",
            "created_at": "2026-06-18T00:02:00Z",
            "last_seen_at": "2026-06-18T00:02:00Z",
            "occurrence_count": 1,
            "debt_ref": ".omo/debt/items/DEBT-1.yaml",
            "lifecycle_state": "identified",
        },
    )
    _write_yaml(
        omo.parent
        / "runtime"
        / "omo"
        / "_delivery"
        / "ingress"
        / "capabilities"
        / "bundle-2026-06-18T00-03-00Z.yaml",
        {
            "kind": "capability_registry_bundle_written",
            "capability_registry_id": "bundle",
            "registry_refs": [
                ".omo/capabilities/INDEX.md",
                ".omo/capabilities/projects-capabilities.yaml",
                ".omo/capabilities/sharedwork-sample.yaml",
                ".omo/capabilities/system-packages.yaml",
                ".omo/capabilities/agent-clis.yaml",
            ],
            "ingress_plane": "projects/omo",
            "actor": "omo-capability capability scan",
            "source_ref": "omo-capability:scan",
            "created_at": "2026-06-18T00:03:00Z",
            "written_at": "2026-06-18T00:03:00Z",
        },
    )
    _write_yaml(
        omo.parent
        / "runtime"
        / "omo"
        / "_delivery"
        / "ingress"
        / "capabilities"
        / "manual-capabilities-2026-06-18T00-04-00Z.yaml",
        {
            "kind": "manual_capabilities_written",
            "capability_registry_id": "manual-capabilities",
            "registry_ref": ".omo/capabilities/manual-capabilities.yaml",
            "ingress_plane": "projects/omo",
            "actor": "omo-capability capability register",
            "source_ref": "omo-capability:register:manual.yaml",
            "created_at": "2026-06-18T00:04:00Z",
            "written_at": "2026-06-18T00:04:00Z",
        },
    )
    _write(omo / "capabilities" / "INDEX.md", "# Capability registry\n")
    _write_yaml(
        omo / "capabilities" / "projects-capabilities.yaml",
        {"capabilities": [{"id": "demo.cap"}]},
    )
    _write_yaml(
        omo / "capabilities" / "sharedwork-sample.yaml",
        {"capabilities": [{"id": "shared.demo"}]},
    )
    _write_yaml(
        omo / "capabilities" / "system-packages.yaml",
        {"packages": [{"id": "demo"}]},
    )
    _write_yaml(
        omo / "capabilities" / "agent-clis.yaml",
        {"clis": [{"name": "omo"}]},
    )
    _write_yaml(
        omo / "capabilities" / "manual-capabilities.yaml",
        {"capabilities": [{"id": "manual.demo"}]},
    )
    _write_yaml(
        omo / "debt" / "items" / "DEBT-1.yaml",
        {"id": "DEBT-1", "title": "debt", "lifecycle_state": "identified"},
    )


def test_build_governance_surfaces_report_ok(tmp_path: Path) -> None:
    _seed_workspace(tmp_path)

    report = build_governance_surfaces_report(tmp_path)

    assert report["status"] == "ok"
    assert report["unregistered_top_levels"] == []
    assert report["missing_registered_roots"] == []
    assert report["c2g_missing_governance_refs"] == []
    assert report["direct_io_gate_present"] is True
    assert report["task_policy_gate_present"] is True
    assert report["mutation_surface_gate_present"] is True
    assert report["internal_write_profile_gate_present"] is True
    assert report["state_plane_asset_gate_present"] is True
    assert report["c2g_omo_boundary_gate_present"] is True
    assert report["ingress_artifact_gate_present"] is True
    assert report["goals_runtime_entry"]["exists"] is True
    assert report["goals_runtime_entry"]["is_symlink"] is True
    assert report["goals_runtime_entry"]["resolves_to_truth"] is True
    assert report["task_policy_registry"]["exists"] is True
    assert report["state_plane_asset_registry"]["exists"] is True
    assert report["mutation_surface_registry"]["exists"] is True
    assert report["internal_write_profile_registry"]["exists"] is True
    assert report["state_plane_asset_registry"]["top_level_asset_count"] == 21
    assert report["state_plane_asset_registry"]["persistence_mode_counts"] == {
        "append_only": 1,
        "archival": 1,
        "authoritative": 2,
        "compatibility_alias": 1,
        "durable": 12,
        "operational": 4,
    }
    assert report["state_plane_asset_registry"]["retention_mode_counts"] == {
        "alias_only": 1,
        "manual_archive": 7,
        "manual_cleanup": 1,
        "rolling_window": 2,
        "until_replaced": 10,
    }
    assert report["c2g_omo_boundary"]["facade_exists"] is True
    assert report["c2g_omo_boundary"]["violations"] == []
    assert report["ingress_artifacts"]["goal_artifacts"] == 1
    assert report["ingress_artifacts"]["task_artifacts"] == 1
    assert report["ingress_artifacts"]["debt_artifacts"] == 1
    assert report["ingress_artifacts"]["capability_artifacts"] == 2
    assert report["ingress_registry"]["capability_ids"] == [
        "bundle",
        "manual-capabilities",
    ]
    assert report["ingress_registry"]["capability_source_refs"] == [
        "omo-capability:register:manual.yaml",
        "omo-capability:scan",
    ]
    assert report["task_policy_registry"]["runtime_policy_names"] == [
        "active-execution-links",
        "active-review-ref",
        "done-directory-status",
        "human-approval-ref",
        "modern-done-completion-marker",
        "modern-done-evidence-paths",
        "remediation-review-note",
        "self-evolution-approval",
    ]
    assert report["mutation_surface_registry"]["runtime_surface_names"] == [
        "c2g-storage-save-bet",
        "c2g-storage-save-task",
        "ecos-mof-state-bridge-m1-to-omo",
        "omo-audit-sync-system-projection",
        "omo-bridge-bmad-openspec",
        "omo-bridge-fast-track",
        "omo-bridge-pitch",
        "omo-capability-registry-register",
        "omo-capability-registry-scan",
        "omo-goal-create",
        "omo-goal-progress",
        "omo-goal-reconcile",
        "omo-governance-ingress-debt",
        "omo-governance-ingress-goal",
        "omo-governance-ingress-task",
        "omo-knowledge-add",
        "omo-self-healing-debt",
        "omo-standard-add",
        "omo-state-refresh",
        "omo-state-sync-projection",
        "omo-state-sync-tasks",
        "omo-task-center-discovery-registry",
        "omo-task-center-skill-manifest",
        "omo-task-create",
        "omo-task-done",
        "omo-task-refresh-evidence",
        "omo-task-repair-approval",
        "omo-worker-task-normalize-planned",
        "omo-worker-task-route-self-evolution-remediation",
        "opc-p6-self-evolve-task-emit",
    ]
    assert report["mutation_surface_registry"]["runtime_category_counts"] == {
        "bridge_import": 4,
        "c2g_adapter": 2,
        "governance_ingress": 11,
            "human_cli": 11,
        "runtime_cache": 2,
    }
    assert report["internal_write_profile_registry"]["runtime_profile_names"] == [
        "debt-campaign-runtime",
        "debt-dispatch-runtime",
        "debt-reporting-runtime",
        "debt-review-runtime",
        "debt-routing-runtime",
        "worker-approval-runtime",
        "worker-dispatch",
        "worker-experience-runtime",
        "worker-overlay-runtime",
        "worker-promotion",
        "worker-rollout-runtime",
        "worker-self-evolution-remediation",
        "worker-status",
        "worker-task-lifecycle",
    ]
    assert report["internal_write_profile_registry"]["runtime_subtype_counts"] == {
        "analytics_runtime": 1,
        "approval_runtime": 1,
        "checkpoint_runtime": 1,
        "dispatch_runtime": 1,
        "experience_runtime": 1,
        "governance_campaign_runtime": 1,
        "governance_dispatch_runtime": 1,
        "governance_reporting_runtime": 1,
        "governance_review_runtime": 1,
        "governance_routing_runtime": 1,
        "remediation_runtime": 1,
        "promotion_runtime": 1,
        "rollout_runtime": 1,
        "task_lifecycle_runtime": 1,
    }
    assert [item["name"] for item in report["worker_internal_write_profiles"]] == [
        "worker-dispatch",
        "worker-task-lifecycle",
        "worker-self-evolution-remediation",
        "worker-promotion",
        "worker-status",
        "worker-approval-runtime",
        "worker-rollout-runtime",
        "worker-experience-runtime",
        "worker-overlay-runtime",
        "debt-review-runtime",
        "debt-routing-runtime",
        "debt-dispatch-runtime",
        "debt-campaign-runtime",
        "debt-reporting-runtime",
    ]
    assert report["worker_internal_write_profiles"][1]["promotion_surface"] is False
    assert [item["subtype"] for item in report["worker_internal_write_profiles"]] == [
        "dispatch_runtime",
        "task_lifecycle_runtime",
        "remediation_runtime",
        "promotion_runtime",
        "checkpoint_runtime",
        "approval_runtime",
        "rollout_runtime",
        "experience_runtime",
        "analytics_runtime",
        "governance_review_runtime",
        "governance_routing_runtime",
        "governance_dispatch_runtime",
        "governance_campaign_runtime",
        "governance_reporting_runtime",
    ]
    assert report["ingress_registry"]["exists"] is True
    assert report["ingress_registry"]["debt_ids"] == ["DEBT-1"]


def test_build_governance_surfaces_report_accepts_multi_document_registry(
    tmp_path: Path,
) -> None:
    _seed_workspace(tmp_path)
    _write(
        tmp_path / ".omo" / "_truth" / "registry" / "omo-governance-surfaces.yaml",
        "---\nstatus: active\nowner: governance-team\n---\n---\nassets:\n"
        "  - ref: .omo/_truth/\n"
        "    status: active\n"
        "    plane: state_plane\n"
        "    asset_type: authority\n"
        "    persistence_mode: authoritative\n"
        "    retention_mode: until_replaced\n",
    )

    report = build_governance_surfaces_report(tmp_path)

    assert report["state_plane_asset_registry"]["exists"] is True
    assert report["state_plane_asset_registry"]["asset_count"] == 1


def test_build_governance_surfaces_report_flags_unregistered_top_level(
    tmp_path: Path,
) -> None:
    _seed_workspace(tmp_path)
    (tmp_path / ".omo" / "mystery").mkdir()

    report = build_governance_surfaces_report(tmp_path)

    assert report["status"] == "error"
    assert "mystery" in report["unregistered_top_levels"]


def test_omo_governance_surfaces_cli_json(
    tmp_path: Path, capsys, monkeypatch: object
) -> None:
    _seed_workspace(tmp_path)
    monkeypatch.chdir(tmp_path)  # type: ignore[reportAttributeAccessIssue]

    rc = omo_governance_main(["surfaces", "--workspace-root", ".", "--json"])

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "ok"
    assert ".omo/standards/omo-governance-surfaces.md" in payload["c2g_governance_refs"]


def test_omo_governance_surfaces_cli_auto_detects_workspace_root_from_subrepo(
    tmp_path: Path, capsys, monkeypatch: object
) -> None:
    _seed_workspace(tmp_path)
    subrepo = tmp_path / "projects" / "omo"
    subrepo.mkdir(parents=True, exist_ok=True)
    monkeypatch.chdir(subrepo)  # type: ignore[reportAttributeAccessIssue]

    rc = omo_governance_main(["surfaces", "--workspace-root", ".", "--json"])

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "ok"
    assert payload["workspace_root"] == str(tmp_path)


def test_build_governance_surfaces_report_accepts_evidence_alias(
    tmp_path: Path,
) -> None:
    _seed_workspace(tmp_path)

    report = build_governance_surfaces_report(tmp_path)

    assert report["status"] == "ok"
    assert report["warnings"] == []


def test_build_governance_surfaces_report_requires_direct_io_gate(
    tmp_path: Path,
) -> None:
    _seed_workspace(tmp_path)
    (tmp_path / ".pre-commit-config.yaml").unlink()

    report = build_governance_surfaces_report(tmp_path)

    assert report["status"] == "error"
    assert any(
        "pre-commit direct io gate missing" in issue for issue in report["issues"]
    )


def test_build_governance_surfaces_report_requires_mutation_surface_gate(
    tmp_path: Path,
) -> None:
    _seed_workspace(tmp_path)
    _write(
        tmp_path / ".pre-commit-config.yaml",
        """
- repo: local
  hooks:
    - id: omo-direct-io-gate
      entry: uv run --directory projects/omo python -m omo.cli lint direct-omo-io
    - id: omo-task-policy-gate
      entry: uv run --directory projects/omo python -m omo.cli lint task-policy --all --workspace-root .
""".strip()
        + "\n",
    )

    report = build_governance_surfaces_report(tmp_path)

    assert report["status"] == "error"
    assert any(
        "pre-commit mutation surface gate missing" in issue
        for issue in report["issues"]
    )


def test_build_governance_surfaces_report_requires_internal_write_profile_gate(
    tmp_path: Path,
) -> None:
    _seed_workspace(tmp_path)
    _write(
        tmp_path / ".pre-commit-config.yaml",
        """
- repo: local
  hooks:
    - id: omo-direct-io-gate
      entry: uv run --directory projects/omo python -m omo.cli lint direct-omo-io
    - id: omo-task-policy-gate
      entry: uv run --directory projects/omo python -m omo.cli lint task-policy --all --workspace-root .
    - id: omo-mutation-surface-gate
      entry: uv run --directory projects/omo python -m omo.cli lint mutation-surfaces --workspace-root .
""".strip()
        + "\n",
    )

    report = build_governance_surfaces_report(tmp_path)

    assert report["status"] == "error"
    assert any(
        "pre-commit internal write profile gate missing" in issue
        for issue in report["issues"]
    )


def test_build_governance_surfaces_report_requires_state_plane_asset_gate(
    tmp_path: Path,
) -> None:
    _seed_workspace(tmp_path)
    _write(
        tmp_path / ".pre-commit-config.yaml",
        """
- repo: local
  hooks:
    - id: omo-direct-io-gate
      entry: uv run --directory projects/omo python -m omo.cli lint direct-omo-io
    - id: omo-task-policy-gate
      entry: uv run --directory projects/omo python -m omo.cli lint task-policy --all --workspace-root .
    - id: omo-mutation-surface-gate
      entry: uv run --directory projects/omo python -m omo.cli lint mutation-surfaces --workspace-root .
    - id: omo-internal-write-profile-gate
      entry: uv run --directory projects/omo python -m omo.cli lint internal-write-profiles --workspace-root .
""".strip()
        + "\n",
    )

    report = build_governance_surfaces_report(tmp_path)

    assert report["status"] == "error"
    assert any(
        "pre-commit state plane asset gate missing" in issue
        for issue in report["issues"]
    )


def test_build_governance_surfaces_report_requires_c2g_omo_boundary_gate(
    tmp_path: Path,
) -> None:
    _seed_workspace(tmp_path)
    _write(
        tmp_path / ".pre-commit-config.yaml",
        """
- repo: local
  hooks:
    - id: omo-direct-io-gate
      entry: uv run --directory projects/omo python -m omo.cli lint direct-omo-io
    - id: omo-task-policy-gate
      entry: uv run --directory projects/omo python -m omo.cli lint task-policy --all --workspace-root .
    - id: omo-mutation-surface-gate
      entry: uv run --directory projects/omo python -m omo.cli lint mutation-surfaces --workspace-root .
    - id: omo-internal-write-profile-gate
      entry: uv run --directory projects/omo python -m omo.cli lint internal-write-profiles --workspace-root .
    - id: omo-state-plane-asset-gate
      entry: uv run --directory projects/omo python -m omo.cli lint state-plane-assets --workspace-root .
""".strip()
        + "\n",
    )

    report = build_governance_surfaces_report(tmp_path)

    assert report["status"] == "error"
    assert any(
        "pre-commit c2g/omo boundary gate missing" in issue
        for issue in report["issues"]
    )


def test_build_governance_surfaces_report_requires_ingress_artifact_gate(
    tmp_path: Path,
) -> None:
    _seed_workspace(tmp_path)
    _write(
        tmp_path / ".pre-commit-config.yaml",
        """
- repo: local
  hooks:
    - id: omo-direct-io-gate
      entry: uv run --directory projects/omo python -m omo.cli lint direct-omo-io
    - id: omo-task-policy-gate
      entry: uv run --directory projects/omo python -m omo.cli lint task-policy --all --workspace-root .
    - id: omo-mutation-surface-gate
      entry: uv run --directory projects/omo python -m omo.cli lint mutation-surfaces --workspace-root .
    - id: omo-internal-write-profile-gate
      entry: uv run --directory projects/omo python -m omo.cli lint internal-write-profiles --workspace-root .
    - id: omo-state-plane-asset-gate
      entry: uv run --directory projects/omo python -m omo.cli lint state-plane-assets --workspace-root .
    - id: omo-c2g-omo-boundary-gate
      entry: uv run --directory projects/omo python -m omo.cli lint c2g-omo-boundary --workspace-root .
""".strip()
        + "\n",
    )

    report = build_governance_surfaces_report(tmp_path)

    assert report["status"] == "error"
    assert any(
        "pre-commit ingress artifact gate missing" in issue
        for issue in report["issues"]
    )


def test_build_governance_surfaces_report_requires_mutation_ledger_gate(
    tmp_path: Path,
) -> None:
    _seed_workspace(tmp_path)
    _write(
        tmp_path / ".pre-commit-config.yaml",
        """
- repo: local
  hooks:
    - id: omo-direct-io-gate
      entry: uv run --directory projects/omo python -m omo.cli lint direct-omo-io
    - id: omo-task-policy-gate
      entry: uv run --directory projects/omo python -m omo.cli lint task-policy --all --workspace-root .
    - id: omo-mutation-surface-gate
      entry: uv run --directory projects/omo python -m omo.cli lint mutation-surfaces --workspace-root .
    - id: omo-internal-write-profile-gate
      entry: uv run --directory projects/omo python -m omo.cli lint internal-write-profiles --workspace-root .
    - id: omo-state-plane-asset-gate
      entry: uv run --directory projects/omo python -m omo.cli lint state-plane-assets --workspace-root .
    - id: omo-c2g-omo-boundary-gate
      entry: uv run --directory projects/omo python -m omo.cli lint c2g-omo-boundary --workspace-root .
    - id: omo-ingress-artifact-gate
      entry: uv run --directory projects/omo python -m omo.cli lint ingress-artifacts --workspace-root .
""".strip()
        + "\n",
    )

    report = build_governance_surfaces_report(tmp_path)

    assert report["status"] == "error"
    assert any(
        "pre-commit mutation ledger gate missing" in issue for issue in report["issues"]
    )


def test_build_governance_surfaces_report_flags_ingress_artifact_created_at_drift(
    tmp_path: Path,
) -> None:
    _seed_workspace(tmp_path)
    _write_yaml(
        tmp_path
        / "runtime"
        / "omo"
        / "_delivery"
        / "ingress"
        / "tasks"
        / "TASK-1.yaml",
        {
            "kind": "planned_task_created",
            "task_id": "TASK-1",
            "title": "task",
            "ingress_plane": "projects/c2g",
            "source_ref": "c2g:task:TASK-1",
            "task_ref": ".omo/tasks/planned/TASK-1.yaml",
        },
    )

    report = build_governance_surfaces_report(tmp_path)

    assert report["status"] == "error"
    assert any(
        "ingress artifacts: runtime/omo/_delivery/ingress/tasks/TASK-1.yaml missing created_at"
        in issue
        for issue in report["issues"]
    )


def test_build_governance_surfaces_report_requires_ingress_registry(
    tmp_path: Path,
) -> None:
    _seed_workspace(tmp_path)
    (tmp_path / "runtime" / "omo" / "_delivery" / "ingress" / "registry.yaml").unlink()

    report = build_governance_surfaces_report(tmp_path)

    assert report["status"] == "error"
    assert any(
        "ingress registry: required file missing: runtime/omo/_delivery/ingress/registry.yaml"
        in issue
        for issue in report["issues"]
    )
    assert any(
        "ingress artifacts: required registry missing: runtime/omo/_delivery/ingress/registry.yaml"
        in issue
        for issue in report["issues"]
    )


def test_build_governance_surfaces_report_flags_c2g_direct_omo_imports(
    tmp_path: Path,
) -> None:
    _seed_workspace(tmp_path)
    _write(
        tmp_path / "projects" / "c2g" / "src" / "c2g" / "adapters.py",
        """
from omo.omo_ingress import create_planned_task
""".strip()
        + "\n",
    )

    report = build_governance_surfaces_report(tmp_path)

    assert report["status"] == "error"
    assert (
        "projects/c2g/src/c2g/adapters.py" in report["c2g_omo_boundary"]["violations"]
    )
    assert any(
        "c2g direct omo import forbidden outside facade" in issue
        for issue in report["issues"]
    )


def test_build_governance_surfaces_report_requires_goals_runtime_symlink(
    tmp_path: Path,
) -> None:
    _seed_workspace(tmp_path)
    goals_link = tmp_path / ".omo" / "goals"
    goals_link.unlink()
    goals_link.mkdir()
    _write_yaml(goals_link / "current.yaml", {"goals": []})

    report = build_governance_surfaces_report(tmp_path)

    assert report["status"] == "error"
    assert report["goals_runtime_entry"]["is_symlink"] is False
    assert any(
        "goals runtime entry must be a symlink" in issue for issue in report["issues"]
    )


def test_build_governance_surfaces_report_flags_task_policy_registry_drift(
    tmp_path: Path,
) -> None:
    _seed_workspace(tmp_path)
    _write_yaml(
        tmp_path / ".omo" / "_truth" / "registry" / "task-policies.yaml",
        {
            "policies": [
                {
                    "name": "self-evolution-approval",
                    "summary": "drifted",
                    "target_roots": ["planned"],
                    "file_glob": "OPC-P6-SELF-EVOLUTION-*.yaml",
                    "prohibited_roots": ["active"],
                    "required_fields": {
                        "approval_required": True,
                        "human_approval_required": True,
                        "approval_state": "awaiting_human",
                    },
                    "required_status": None,
                    "allowed_statuses": ["planned"],
                    "validator_id": None,
                }
            ]
        },
    )

    report = build_governance_surfaces_report(tmp_path)

    assert report["status"] == "error"
    assert any(
        "task policy registry drift for self-evolution-approval" in issue
        for issue in report["issues"]
    )
    assert any(
        "task policy registry missing runtime policy: human-approval-ref" in issue
        for issue in report["issues"]
    )


def test_build_governance_surfaces_report_flags_mutation_surface_registry_drift(
    tmp_path: Path,
) -> None:
    _seed_workspace(tmp_path)
    _write_yaml(
        tmp_path / ".omo" / "_truth" / "registry" / "mutation-surfaces.yaml",
        {
            "surfaces": [
                {
                    "name": "omo-goal-create",
                    "entrypoint": "omo goal create",
                    "runtime_ref": "projects/omo/src/omo/omo_goal.py:cmd_goal_create",
                    "mutation_target": ".omo/goals/current.yaml",
                    "broker_ref": "DRIFTED",
                    "delivery_artifact_root": "runtime/omo/_delivery/ingress/goals/",
                    "mode": "brokered",
                }
            ]
        },
    )

    report = build_governance_surfaces_report(tmp_path)

    assert report["status"] == "error"
    assert any(
        "mutation surface registry drift for omo-goal-create" in issue
        for issue in report["issues"]
    )
    assert any(
        "mutation surface registry missing runtime surface: omo-task-create" in issue
        for issue in report["issues"]
    )


def test_build_governance_surfaces_report_flags_ingress_registry_reverse_mapping_mismatch(
    tmp_path: Path,
) -> None:
    _seed_workspace(tmp_path)
    ingress_dir = tmp_path / "runtime" / "omo" / "_delivery" / "ingress"
    ingress_dir.mkdir(parents=True, exist_ok=True)
    _write_yaml(
        tmp_path / ".omo" / "tasks" / "planned" / "IMPORTED-1.yaml",
        {
            "id": "IMPORTED-1",
            "title": "task",
            "status": "candidate",
            "task_type": "feature",
            "risk_level": "L0",
            "depends_on": [],
            "source_docs": ["spec.md"],
            "deliverables": ["代码"],
            "imported_via": "projects/c2g",
            "context_uri": "bos://memory/spec#1",
            "assigned_to": None,
            "dispatch_id": None,
            "run_ref": None,
            "approval_ref": None,
            "review_ref": None,
            "knowledge_refs": [],
            "handoff_refs": [],
            "governance_refs": [".omo/standards/omo-governance-surfaces.md"],
            "entry_gate": [],
            "evidence_required": ["pytest"],
            "test_plan": ["uv run pytest"],
            "allowed_operation_level": "L0",
            "human_approval_required": False,
            "metadata": {},
        },
    )
    _write_yaml(
        ingress_dir / "registry.yaml",
        {
            "goals": {"by_id": {}, "by_source_ref": {}},
            "tasks": {
                "by_id": {
                    "IMPORTED-1": {
                        "source_ref": "c2g:bridge-import:IMPORTED-1",
                        "artifact_ref": "runtime/omo/_delivery/ingress/tasks/IMPORTED-1.yaml",
                        "fingerprint": {"id": "IMPORTED-1"},
                        "created_at": "2026-06-18T00:00:00Z",
                    }
                },
                "by_source_ref": {"c2g:bridge-import:IMPORTED-1": "IMPORTED-OTHER"},
            },
            "debts": {"by_id": {}, "by_source_ref": {}},
        },
    )

    report = build_governance_surfaces_report(tmp_path)

    assert report["status"] == "error"
    assert any("reverse mapping mismatch" in issue for issue in report["issues"])


def test_build_governance_surfaces_report_tracks_debt_ingress(tmp_path: Path) -> None:
    _seed_workspace(tmp_path)
    ingress_dir = tmp_path / "runtime" / "omo" / "_delivery" / "ingress"
    ingress_dir.mkdir(parents=True, exist_ok=True)
    _write_yaml(
        tmp_path / ".omo" / "debt" / "items" / "DEBT-1.yaml",
        {
            "id": "DEBT-1",
            "title": "debt",
            "lifecycle_state": "identified",
        },
    )
    _write_yaml(
        ingress_dir / "registry.yaml",
        {
            "goals": {"by_id": {}, "by_source_ref": {}},
            "tasks": {"by_id": {}, "by_source_ref": {}},
            "debts": {
                "by_id": {
                    "DEBT-1": {
                        "source_ref": "aetherforge:budget:DEBT-1",
                        "artifact_ref": "runtime/omo/_delivery/ingress/debts/DEBT-1.yaml",
                        "fingerprint": {"id": "DEBT-1"},
                        "created_at": "2026-06-18T00:00:00Z",
                    }
                },
                "by_source_ref": {"aetherforge:budget:DEBT-1": "DEBT-1"},
            },
            "capabilities": {"by_id": {}, "by_source_ref": {}},
        },
    )
    _write_yaml(
        ingress_dir / "debts" / "DEBT-1.yaml",
        {
            "kind": "debt_upserted",
            "debt_id": "DEBT-1",
            "title": "debt",
            "ingress_plane": "projects/omo",
            "source_ref": "aetherforge:budget:DEBT-1",
            "created_at": "2026-06-18T00:00:00Z",
            "last_seen_at": "2026-06-18T00:00:00Z",
            "occurrence_count": 1,
            "debt_ref": ".omo/debt/items/DEBT-1.yaml",
            "lifecycle_state": "identified",
        },
    )

    report = build_governance_surfaces_report(tmp_path)

    assert report["status"] == "ok"
    assert report["ingress_registry"]["debt_ids"] == ["DEBT-1"]
    assert report["ingress_registry"]["debt_source_refs"] == [
        "aetherforge:budget:DEBT-1"
    ]


def test_build_governance_surfaces_report_accepts_archived_ingress_task_carrier(
    tmp_path: Path,
) -> None:
    _seed_workspace(tmp_path)
    ingress_dir = tmp_path / "runtime" / "omo" / "_delivery" / "ingress"
    ingress_dir.mkdir(parents=True, exist_ok=True)
    _write_yaml(
        tmp_path / ".omo" / "tasks" / "archive" / "IMPORTED-1.yaml",
        {
            "id": "IMPORTED-1",
            "status": "archived",
        },
    )
    _write_yaml(
        ingress_dir / "registry.yaml",
        {
            "goals": {"by_id": {}, "by_source_ref": {}},
            "tasks": {
                "by_id": {
                    "IMPORTED-1": {
                        "source_ref": "c2g:bridge-import:IMPORTED-1",
                        "artifact_ref": "runtime/omo/_delivery/ingress/tasks/IMPORTED-1.yaml",
                        "fingerprint": {"id": "IMPORTED-1"},
                        "created_at": "2026-06-18T00:00:00Z",
                    }
                },
                "by_source_ref": {"c2g:bridge-import:IMPORTED-1": "IMPORTED-1"},
            },
            "debts": {"by_id": {}, "by_source_ref": {}},
            "capabilities": {"by_id": {}, "by_source_ref": {}},
        },
    )
    _write_yaml(
        ingress_dir / "tasks" / "IMPORTED-1.yaml",
        {
            "kind": "planned_task_created",
            "task_id": "IMPORTED-1",
            "title": "task",
            "ingress_plane": "projects/c2g",
            "source_ref": "c2g:bridge-import:IMPORTED-1",
            "created_at": "2026-06-18T00:00:00Z",
            "task_ref": ".omo/tasks/archive/IMPORTED-1.yaml",
        },
    )

    report = build_governance_surfaces_report(tmp_path)

    assert report["status"] == "ok"
    assert report["issues"] == []
