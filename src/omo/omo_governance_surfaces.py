#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import json
import sys
from pathlib import Path

from .omo_task_policy import task_policy_registry_snapshot
from .omo_shared import load_yaml_required


ALLOWED_PERSISTENCE_MODES = {
    "authoritative",
    "durable",
    "operational",
    "append_only",
    "archival",
    "compatibility_alias",
}

ALLOWED_RETENTION_MODES = {
    "until_replaced",
    "manual_cleanup",
    "rolling_window",
    "append_forever",
    "manual_archive",
    "alias_only",
}

EXPECTED_ASSET_LIFECYCLE_BY_TYPE: dict[str, tuple[str, str]] = {
    "authority": ("authoritative", "until_replaced"),
    "control_state": ("operational", "rolling_window"),
    "knowledge_state": ("durable", "manual_cleanup"),
    "delivery_state": ("append_only", "manual_archive"),
    "archived_state": ("archival", "manual_archive"),
    "workflow_state": ("operational", "manual_archive"),
    "runtime_ssot": ("operational", "until_replaced"),
    "governance_program": ("durable", "manual_archive"),
    "governance_review_surface": ("durable", "until_replaced"),
    "governance_routing_surface": ("durable", "until_replaced"),
    "governance_dispatch_surface": ("durable", "manual_archive"),
    "governance_campaign_surface": ("durable", "manual_archive"),
    "governance_reporting_surface": ("durable", "manual_archive"),
    "execution_runtime": ("operational", "rolling_window"),
    "rule_docs": ("durable", "until_replaced"),
    "control_contract": ("durable", "until_replaced"),
    "runtime_logs": ("append_only", "rolling_window"),
    "goal_state": ("authoritative", "until_replaced"),
    "strategic_input": ("durable", "manual_archive"),
    "governance_test_surface": ("durable", "manual_cleanup"),
    "capability_market": ("durable", "until_replaced"),
    "change_history": ("append_only", "manual_archive"),
    "root_registry": ("authoritative", "until_replaced"),
    "root_index": ("durable", "until_replaced"),
    "compatibility_alias": ("compatibility_alias", "alias_only"),
}

INGRESS_ARTIFACT_RULES: dict[str, dict[str, object]] = {
    "goals": {
        "kind": "goal_created",
        "id_field": "goal_id",
        "target_field": "goal_ref",
        "target_ref": ".omo/goals/current.yaml",
    },
    "tasks": {
        "kind": "planned_task_created",
        "id_field": "task_id",
        "target_field": "task_ref",
        "target_prefix": ".omo/tasks/",
    },
    "debts": {
        "kind": "debt_upserted",
        "id_field": "debt_id",
        "target_field": "debt_ref",
        "target_prefix": ".omo/debt/items/",
    },
    "capabilities": {
        "kind_by_id": {
            "bundle": "capability_registry_bundle_written",
            "manual-capabilities": "manual_capabilities_written",
        },
        "id_field": "capability_registry_id",
        "target_field_by_id": {
            "bundle": "registry_refs",
            "manual-capabilities": "registry_ref",
        },
        "target_expected_by_id": {
            "bundle": [
                ".omo/capabilities/INDEX.md",
                ".omo/capabilities/projects-capabilities.yaml",
                ".omo/capabilities/sharedwork-sample.yaml",
                ".omo/capabilities/system-packages.yaml",
                ".omo/capabilities/agent-clis.yaml",
            ],
            "manual-capabilities": ".omo/capabilities/manual-capabilities.yaml",
        },
    },
}


def _load_yaml(path: Path) -> dict:
    return load_yaml_required(path)


def _asset_ref_to_top_level(ref: str) -> str:
    normalized = ref.strip().strip("/")
    if normalized.startswith(".omo/"):
        normalized = normalized[len(".omo/") :]
    if normalized == ".omo":
        return ""
    return normalized.split("/", 1)[0] if normalized else ""


def _top_level_entries(omo_dir: Path) -> list[str]:
    ignored = {".DS_Store", "__pycache__", ".omo"}
    return sorted(
        entry.name for entry in omo_dir.iterdir() if entry.name not in ignored
    )


def _check_goals_runtime_entry(omo_dir: Path) -> tuple[dict[str, object], list[str]]:
    goals_path = omo_dir / "goals"
    truth_goals_path = omo_dir / "_truth" / "goals"
    summary: dict[str, object] = {
        "path": str(goals_path),
        "truth_path": str(truth_goals_path),
        "exists": goals_path.exists(),
        "is_symlink": goals_path.is_symlink(),
        "resolves_to_truth": False,
        "current_exists": (goals_path / "current.yaml").exists()
        if goals_path.exists()
        else False,
    }
    issues: list[str] = []
    if not goals_path.exists():
        issues.append("goals runtime entry missing: .omo/goals")
        return summary, issues
    if not goals_path.is_symlink():
        issues.append(
            "goals runtime entry must be a symlink: .omo/goals -> .omo/_truth/goals"
        )
        return summary, issues
    try:
        summary["resolves_to_truth"] = (
            goals_path.resolve() == truth_goals_path.resolve()
        )
    except FileNotFoundError:
        summary["resolves_to_truth"] = False
    if not summary["resolves_to_truth"]:
        issues.append("goals runtime entry resolves to unexpected target")
    if not summary["current_exists"]:
        issues.append("goals runtime entry missing current.yaml")
    return summary, issues


def _read_c2g_governance_refs(workspace_root: Path) -> tuple[list[str], list[str]]:
    issues: list[str] = []
    refs: list[str] = []
    c2g_src = workspace_root / "projects" / "c2g" / "src"
    if not c2g_src.exists():
        issues.append("projects/c2g/src missing")
        return refs, issues
    sys.path.insert(0, str(c2g_src))
    try:
        from c2g.task_builder import build_ecos_task  # type: ignore

        task = build_ecos_task(
            "SURFACE-CHECK",
            "surface check",
            source_docs=["governance"],
            evidence_required=["evidence"],
            test_plan=["verify"],
        )
        refs = list(task.get("governance_refs", []))
        if not refs:
            issues.append("c2g task builder returned empty governance_refs")
        metadata = task.get("metadata", {})
        if metadata.get("ingress_plane") != "projects/c2g":
            issues.append("c2g task builder ingress_plane metadata mismatch")
    except Exception as exc:  # pragma: no cover - defensive
        issues.append(f"failed to load c2g governance refs: {exc}")
    finally:
        if sys.path and sys.path[0] == str(c2g_src):
            sys.path.pop(0)
    return refs, issues


def _check_c2g_omo_boundary(
    workspace_root: Path,
) -> tuple[dict[str, object], list[str]]:
    c2g_src = workspace_root / "projects" / "c2g" / "src" / "c2g"
    facade_path = c2g_src / "omo_client.py"
    summary: dict[str, object] = {
        "exists": c2g_src.exists(),
        "path": str(c2g_src),
        "facade_path": str(facade_path),
        "facade_exists": facade_path.exists(),
        "violations": [],
    }
    if not c2g_src.exists():
        return summary, ["projects/c2g/src/c2g missing"]
    if not facade_path.exists():
        return summary, ["c2g omo facade missing: projects/c2g/src/c2g/omo_client.py"]

    violations: list[str] = []
    violating_files: list[str] = []
    for py_file in sorted(c2g_src.rglob("*.py")):
        if py_file.name == "omo_client.py":
            continue
        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        except SyntaxError as exc:
            violations.append(
                f"failed to parse {py_file.relative_to(workspace_root)}: {exc}"
            )
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "omo" or alias.name.startswith("omo."):
                        violating_files.append(str(py_file.relative_to(workspace_root)))
                        violations.append(
                            f"c2g direct omo import forbidden outside facade: "
                            f"{py_file.relative_to(workspace_root)} imports {alias.name}"
                        )
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if module == "omo" or module.startswith("omo."):
                    violating_files.append(str(py_file.relative_to(workspace_root)))
                    violations.append(
                        f"c2g direct omo import forbidden outside facade: "
                        f"{py_file.relative_to(workspace_root)} imports from {module}"
                    )

    summary["violations"] = sorted(set(violating_files))
    return summary, violations


def _has_direct_io_gate(workspace_root: Path) -> bool:
    precommit = workspace_root / ".pre-commit-config.yaml"
    if not precommit.exists():
        return False
    text = precommit.read_text(encoding="utf-8")
    return "omo-direct-io-gate" in text and "lint direct-omo-io" in text


def _has_task_policy_gate(workspace_root: Path) -> bool:
    precommit = workspace_root / ".pre-commit-config.yaml"
    if not precommit.exists():
        return False
    text = precommit.read_text(encoding="utf-8")
    return "omo-task-policy-gate" in text and "lint task-policy" in text


def _has_mutation_surface_gate(workspace_root: Path) -> bool:
    precommit = workspace_root / ".pre-commit-config.yaml"
    if not precommit.exists():
        return False
    text = precommit.read_text(encoding="utf-8")
    return "omo-mutation-surface-gate" in text and "lint mutation-surfaces" in text


def _has_internal_write_profile_gate(workspace_root: Path) -> bool:
    precommit = workspace_root / ".pre-commit-config.yaml"
    if not precommit.exists():
        return False
    text = precommit.read_text(encoding="utf-8")
    return (
        "omo-internal-write-profile-gate" in text
        and "lint internal-write-profiles" in text
    )


def _has_state_plane_asset_gate(workspace_root: Path) -> bool:
    precommit = workspace_root / ".pre-commit-config.yaml"
    if not precommit.exists():
        return False
    text = precommit.read_text(encoding="utf-8")
    return "omo-state-plane-asset-gate" in text and "lint state-plane-assets" in text


def _has_c2g_omo_boundary_gate(workspace_root: Path) -> bool:
    precommit = workspace_root / ".pre-commit-config.yaml"
    if not precommit.exists():
        return False
    text = precommit.read_text(encoding="utf-8")
    return "omo-c2g-omo-boundary-gate" in text and "lint c2g-omo-boundary" in text


def _has_ingress_artifact_gate(workspace_root: Path) -> bool:
    precommit = workspace_root / ".pre-commit-config.yaml"
    if not precommit.exists():
        return False
    text = precommit.read_text(encoding="utf-8")
    return "omo-ingress-artifact-gate" in text and "lint ingress-artifacts" in text


def _has_mutation_ledger_gate(workspace_root: Path) -> bool:
    precommit = workspace_root / ".pre-commit-config.yaml"
    if not precommit.exists():
        return False
    text = precommit.read_text(encoding="utf-8")
    return "omo-mutation-ledger-gate" in text and "lint mutation-ledger" in text


def _check_task_policy_registry(
    workspace_root: Path,
) -> tuple[dict[str, object], list[str]]:
    registry_path = (
        workspace_root / ".omo" / "_truth" / "registry" / "task-policies.yaml"
    )
    if not registry_path.exists():
        return {
            "exists": False,
            "path": str(registry_path),
            "registered_policy_names": [],
            "runtime_policy_names": [
                item["name"] for item in task_policy_registry_snapshot()
            ],
        }, ["task policy registry missing"]

    registry = _load_yaml(registry_path)
    policies = registry.get("policies")
    if not isinstance(policies, list):
        return {
            "exists": True,
            "path": str(registry_path),
            "registered_policy_names": [],
            "runtime_policy_names": [
                item["name"] for item in task_policy_registry_snapshot()
            ],
        }, ["task policy registry: policies block missing or not a list"]

    registered_items = [item for item in policies if isinstance(item, dict)]
    runtime_items = task_policy_registry_snapshot()
    registered_by_name = {
        str(item.get("name")): {
            "summary": item.get("summary"),
            "target_roots": list(item.get("target_roots", [])),
            "file_glob": item.get("file_glob"),
            "prohibited_roots": list(item.get("prohibited_roots", [])),
            "required_fields": item.get("required_fields", {}),
            "required_status": item.get("required_status"),
            "allowed_statuses": list(item.get("allowed_statuses", [])),
            "validator_id": item.get("validator_id"),
        }
        for item in registered_items
        if item.get("name")
    }
    runtime_by_name = {
        item["name"]: {
            "summary": item.get("summary"),
            "target_roots": list(item.get("target_roots", [])),
            "file_glob": item.get("file_glob"),
            "prohibited_roots": list(item.get("prohibited_roots", [])),
            "required_fields": item.get("required_fields", {}),
            "required_status": item.get("required_status"),
            "allowed_statuses": list(item.get("allowed_statuses", [])),
            "validator_id": item.get("validator_id"),
        }
        for item in runtime_items
    }

    issues: list[str] = []
    registered_names = sorted(registered_by_name)
    runtime_names = sorted(runtime_by_name)
    missing_in_registry = sorted(
        name for name in runtime_names if name not in registered_by_name
    )
    stale_in_registry = sorted(
        name for name in registered_names if name not in runtime_by_name
    )
    issues.extend(
        f"task policy registry missing runtime policy: {name}"
        for name in missing_in_registry
    )
    issues.extend(
        f"task policy registry contains stale policy: {name}"
        for name in stale_in_registry
    )

    for name in sorted(set(registered_by_name).intersection(runtime_by_name)):
        if registered_by_name[name] != runtime_by_name[name]:
            issues.append(f"task policy registry drift for {name}")

    return {
        "exists": True,
        "path": str(registry_path),
        "registered_policy_names": registered_names,
        "runtime_policy_names": runtime_names,
        "registered_policies": [
            registered_by_name[name] | {"name": name} for name in registered_names
        ],
        "runtime_policies": runtime_items,
    }, issues


def _check_state_plane_asset_registry(
    workspace_root: Path,
) -> tuple[dict[str, object], list[str]]:
    registry_path = (
        workspace_root / ".omo" / "_truth" / "registry" / "omo-governance-surfaces.yaml"
    )
    if not registry_path.exists():
        return {
            "exists": False,
            "path": str(registry_path),
            "asset_count": 0,
            "top_level_asset_count": 0,
            "persistence_mode_counts": {},
            "retention_mode_counts": {},
        }, ["governance surfaces registry missing"]

    registry = _load_yaml(registry_path)
    assets = [item for item in registry.get("assets", []) if isinstance(item, dict)]
    top_level_assets = [
        item
        for item in assets
        if item.get("plane") == "state_plane"
        and str(item.get("ref", "")).startswith(".omo/")
    ]

    persistence_mode_counts: dict[str, int] = {}
    retention_mode_counts: dict[str, int] = {}
    issues: list[str] = []

    for item in top_level_assets:
        ref = str(item.get("ref", ""))
        asset_type = str(item.get("asset_type", ""))
        persistence_mode = item.get("persistence_mode")
        retention_mode = item.get("retention_mode")

        if not asset_type:
            issues.append(f"state plane asset missing asset_type: {ref}")
            continue

        if not isinstance(persistence_mode, str) or not persistence_mode:
            issues.append(f"state plane asset missing persistence_mode: {ref}")
        elif persistence_mode not in ALLOWED_PERSISTENCE_MODES:
            issues.append(
                f"state plane asset invalid persistence_mode {persistence_mode!r}: {ref}"
            )
        else:
            persistence_mode_counts[persistence_mode] = (
                persistence_mode_counts.get(persistence_mode, 0) + 1
            )

        if not isinstance(retention_mode, str) or not retention_mode:
            issues.append(f"state plane asset missing retention_mode: {ref}")
        elif retention_mode not in ALLOWED_RETENTION_MODES:
            issues.append(
                f"state plane asset invalid retention_mode {retention_mode!r}: {ref}"
            )
        else:
            retention_mode_counts[retention_mode] = (
                retention_mode_counts.get(retention_mode, 0) + 1
            )

        expected = EXPECTED_ASSET_LIFECYCLE_BY_TYPE.get(asset_type)
        if (
            expected
            and isinstance(persistence_mode, str)
            and isinstance(retention_mode, str)
        ):
            if (persistence_mode, retention_mode) != expected:
                issues.append(
                    "state plane asset lifecycle drift "
                    f"for {ref}: expected {expected[0]}/{expected[1]}, "
                    f"got {persistence_mode}/{retention_mode}"
                )

        if asset_type == "compatibility_alias" and not item.get("alias_target"):
            issues.append(f"compatibility alias missing alias_target: {ref}")

    return {
        "exists": True,
        "path": str(registry_path),
        "asset_count": len(assets),
        "top_level_asset_count": len(top_level_assets),
        "persistence_mode_counts": dict(sorted(persistence_mode_counts.items())),
        "retention_mode_counts": dict(sorted(retention_mode_counts.items())),
    }, issues


def _check_ingress_artifacts(
    workspace_root: Path,
) -> tuple[dict[str, object], list[str]]:
    omo_dir = workspace_root / ".omo"
    registry_path = omo_dir / "_delivery" / "ingress" / "registry.yaml"
    if not registry_path.exists():
        return {
            "exists": False,
            "path": str(registry_path),
            "goal_artifacts": 0,
            "task_artifacts": 0,
            "debt_artifacts": 0,
            "capability_artifacts": 0,
        }, [
            "ingress artifacts: required registry missing: .omo/_delivery/ingress/registry.yaml"
        ]

    registry = _load_yaml(registry_path)
    issues: list[str] = []
    summary = {
        "exists": True,
        "path": str(registry_path),
        "goal_artifacts": 0,
        "task_artifacts": 0,
        "debt_artifacts": 0,
        "capability_artifacts": 0,
    }

    for bucket_name, summary_key in (
        ("goals", "goal_artifacts"),
        ("tasks", "task_artifacts"),
        ("debts", "debt_artifacts"),
        ("capabilities", "capability_artifacts"),
    ):
        bucket = registry.get(bucket_name, {})
        by_id = bucket.get("by_id", {}) if isinstance(bucket, dict) else {}
        if not isinstance(by_id, dict):
            issues.append(
                f"ingress artifacts: {bucket_name}.by_id missing or not a mapping"
            )
            continue
        summary[summary_key] = len(by_id)
        rules = INGRESS_ARTIFACT_RULES[bucket_name]
        for item_id, meta in by_id.items():
            if not isinstance(meta, dict):
                issues.append(
                    f"ingress artifacts: {bucket_name}.by_id.{item_id} not a mapping"
                )
                continue
            artifact_ref = meta.get("artifact_ref")
            if not isinstance(artifact_ref, str) or not artifact_ref:
                issues.append(
                    f"ingress artifacts: {bucket_name}.by_id.{item_id} missing artifact_ref"
                )
                continue
            artifact_path = workspace_root / artifact_ref
            if not artifact_path.exists():
                issues.append(
                    f"ingress artifacts: artifact file missing for {bucket_name}.{item_id}: {artifact_ref}"
                )
                continue
            payload = _load_yaml(artifact_path)
            expected_kind = (
                (rules.get("kind_by_id") or {}).get(item_id)
                if isinstance(rules.get("kind_by_id"), dict)
                else rules.get("kind")
            ) or rules.get("kind")
            if payload.get("kind") != expected_kind:
                issues.append(
                    f"ingress artifacts: {artifact_ref} kind mismatch "
                    f"(expected {expected_kind}, got {payload.get('kind')!r})"
                )
            if payload.get(rules["id_field"]) != item_id:
                issues.append(
                    f"ingress artifacts: {artifact_ref} {rules['id_field']} mismatch for {item_id}"
                )
            if not payload.get("created_at"):
                issues.append(f"ingress artifacts: {artifact_ref} missing created_at")
            if payload.get("source_ref", "") != meta.get("source_ref", ""):
                issues.append(
                    f"ingress artifacts: {artifact_ref} source_ref mismatch for {item_id}"
                )
            if not payload.get("ingress_plane"):
                issues.append(
                    f"ingress artifacts: {artifact_ref} missing ingress_plane"
                )
            target_field = (
                (rules.get("target_field_by_id") or {}).get(item_id)
                if isinstance(rules.get("target_field_by_id"), dict)
                else rules.get("target_field")
            )
            if not isinstance(target_field, str) or not target_field:
                issues.append(
                    f"ingress artifacts: {bucket_name}.{item_id} missing target_field rule"
                )
                continue
            target_value = payload.get(target_field)
            expected_target = (
                (rules.get("target_expected_by_id") or {}).get(item_id)
                if isinstance(rules.get("target_expected_by_id"), dict)
                else rules.get("target_ref")
            )
            if isinstance(expected_target, list):
                if not isinstance(target_value, list) or not target_value:
                    issues.append(
                        f"ingress artifacts: {artifact_ref} missing {target_field}"
                    )
                else:
                    missing_refs = [
                        ref for ref in expected_target if ref not in target_value
                    ]
                    if missing_refs:
                        issues.append(
                            f"ingress artifacts: {artifact_ref} {target_field} missing refs {missing_refs}"
                        )
            elif not isinstance(target_value, str) or not target_value:
                issues.append(
                    f"ingress artifacts: {artifact_ref} missing {target_field}"
                )
            elif "target_ref" in rules and target_value != rules["target_ref"]:
                issues.append(
                    f"ingress artifacts: {artifact_ref} {target_field} mismatch "
                    f"(expected {rules['target_ref']}, got {target_value!r})"
                )
            elif expected_target and target_value != expected_target:
                issues.append(
                    f"ingress artifacts: {artifact_ref} {target_field} mismatch "
                    f"(expected {expected_target}, got {target_value!r})"
                )
            elif "target_prefix" in rules and not target_value.startswith(
                str(rules["target_prefix"])
            ):
                issues.append(
                    f"ingress artifacts: {artifact_ref} {target_field} must start with {rules['target_prefix']}"
                )

    return summary, issues


def _mutation_surface_registry_snapshot() -> list[dict[str, object]]:
    return [
        {
            "name": "omo-governance-ingress-goal",
            "entrypoint": "omo governance ingress-goal",
            "runtime_ref": "projects/omo/src/omo/omo_governance.py:main (command=ingress-goal)",
            "mutation_target": ".omo/goals/current.yaml",
            "broker_ref": "projects/omo/src/omo/omo_ingress.py:create_goal",
            "delivery_artifact_root": ".omo/_delivery/ingress/goals/",
            "mode": "brokered",
            "category": "governance_ingress",
        },
        {
            "name": "omo-governance-ingress-task",
            "entrypoint": "omo governance ingress-task",
            "runtime_ref": "projects/omo/src/omo/omo_governance.py:main (command=ingress-task)",
            "mutation_target": ".omo/tasks/planned/",
            "broker_ref": "projects/omo/src/omo/omo_ingress.py:create_planned_task",
            "delivery_artifact_root": ".omo/_delivery/ingress/tasks/",
            "mode": "brokered",
            "category": "governance_ingress",
        },
        {
            "name": "omo-governance-ingress-debt",
            "entrypoint": "omo governance ingress-debt",
            "runtime_ref": "projects/omo/src/omo/omo_governance.py:main (command=ingress-debt)",
            "mutation_target": ".omo/debt/items/ + .omo/debt/registry.yaml",
            "broker_ref": "projects/omo/src/omo/omo_ingress.py:upsert_debt_item",
            "delivery_artifact_root": ".omo/_delivery/ingress/debts/",
            "mode": "brokered",
            "category": "governance_ingress",
        },
        {
            "name": "omo-goal-create",
            "entrypoint": "omo goal create",
            "runtime_ref": "projects/omo/src/omo/omo_goal.py:cmd_goal_create",
            "mutation_target": ".omo/goals/current.yaml",
            "broker_ref": "projects/omo/src/omo/omo_ingress.py:create_goal",
            "delivery_artifact_root": ".omo/_delivery/ingress/goals/",
            "mode": "brokered",
            "category": "human_cli",
        },
        {
            "name": "omo-goal-progress",
            "entrypoint": "omo goal progress",
            "runtime_ref": "projects/omo/src/omo/omo_goal.py:cmd_goal_progress",
            "mutation_target": ".omo/goals/current.yaml",
            "broker_ref": "projects/omo/src/omo/omo_ingress.py:update_goal_progress",
            "delivery_artifact_root": ".omo/_delivery/ingress/goals/",
            "mode": "brokered",
            "category": "human_cli",
        },
        {
            "name": "omo-task-create",
            "entrypoint": "omo task create",
            "runtime_ref": "projects/omo/src/omo/omo_task.py:cmd_task_create",
            "mutation_target": ".omo/tasks/planned/",
            "broker_ref": "projects/omo/src/omo/omo_ingress.py:create_planned_task",
            "delivery_artifact_root": ".omo/_delivery/ingress/tasks/",
            "mode": "brokered",
            "category": "human_cli",
        },
        {
            "name": "omo-task-done",
            "entrypoint": "omo task done",
            "runtime_ref": "projects/omo/src/omo/omo_task.py:cmd_task_done",
            "mutation_target": ".omo/tasks/active/|planned/ -> .omo/tasks/done/",
            "broker_ref": "projects/omo/src/omo/omo_ingress.py:complete_task",
            "delivery_artifact_root": ".omo/_delivery/ingress/tasks/",
            "mode": "brokered",
            "category": "human_cli",
        },
        {
            "name": "omo-task-refresh-evidence",
            "entrypoint": "omo task refresh-evidence",
            "runtime_ref": "projects/omo/src/omo/omo_task.py:cmd_task_refresh_evidence",
            "mutation_target": ".omo/tasks/done/*.yaml (evidence_paths)",
            "broker_ref": "projects/omo/src/omo/omo_ingress.py:update_done_task_evidence_paths",
            "delivery_artifact_root": ".omo/_delivery/ingress/tasks/",
            "mode": "brokered",
            "category": "human_cli",
        },
        {
            "name": "omo-task-repair-approval",
            "entrypoint": "omo task repair-approval",
            "runtime_ref": "projects/omo/src/omo/omo_task.py:cmd_task_repair_approval",
            "mutation_target": ".omo/tasks/{planned,active,done,remediation}/*.yaml (approval_ref) + .omo/workers/runs/*-promotion-approval-*.yaml",
            "broker_ref": "projects/omo/src/omo/omo_ingress.py:repair_task_promotion_approval",
            "delivery_artifact_root": ".omo/_delivery/ingress/tasks/",
            "mode": "brokered",
            "category": "human_cli",
        },
        {
            "name": "omo-worker-task-normalize-planned",
            "entrypoint": "python3 scripts/omo_worker.py task normalize-planned",
            "runtime_ref": "projects/omo/src/omo/omo_worker_cmd_task.py:execute_task_command (task_command=normalize-planned)",
            "mutation_target": ".omo/tasks/planned/ + .omo/tasks/archived/legacy-normalized/",
            "broker_ref": "projects/omo/src/omo/omo_ingress.py:normalize_legacy_planned_task",
            "delivery_artifact_root": ".omo/_delivery/ingress/tasks/",
            "mode": "brokered",
            "category": "governance_ingress",
        },
        {
            "name": "omo-worker-task-route-self-evolution-remediation",
            "entrypoint": "python3 scripts/omo/omo_worker.py task route-self-evolution-remediation",
            "runtime_ref": "projects/omo/src/omo/omo_worker_cmd_task.py:execute_task_command (task_command=route-self-evolution-remediation)",
            "mutation_target": ".omo/tasks/planned/ -> .omo/tasks/remediation/ + .omo/tasks/remediation-notes/",
            "broker_ref": "projects/omo/src/omo/omo_ingress.py:route_self_evolution_to_remediation",
            "delivery_artifact_root": ".omo/_delivery/ingress/tasks/",
            "mode": "brokered",
            "category": "governance_ingress",
        },
        {
            "name": "opc-p6-self-evolve-task-emit",
            "entrypoint": "python3 scripts/opc_p6_self_evolve.py",
            "runtime_ref": "projects/omo/src/omo/omo_self_evolve.py:write_planned_self_evolution_tasks",
            "mutation_target": ".omo/tasks/planned/",
            "broker_ref": "projects/omo/src/omo/omo_ingress.py:create_planned_task",
            "delivery_artifact_root": ".omo/_delivery/ingress/tasks/",
            "mode": "brokered",
            "category": "governance_ingress",
        },
        {
            "name": "omo-knowledge-add",
            "entrypoint": "omo knowledge add",
            "runtime_ref": "projects/omo/src/omo/omo_knowledge.py:cmd_knowledge_add",
            "mutation_target": ".omo/_knowledge/",
            "broker_ref": "projects/omo/src/omo/omo_ingress.py:create_knowledge_doc",
            "delivery_artifact_root": ".omo/_delivery/ingress/knowledge/",
            "mode": "brokered",
            "category": "human_cli",
        },
        {
            "name": "omo-standard-add",
            "entrypoint": "omo standard add",
            "runtime_ref": "projects/omo/src/omo/omo_standard.py:cmd_standard_add",
            "mutation_target": ".omo/standards/",
            "broker_ref": "projects/omo/src/omo/omo_ingress.py:create_standard_doc",
            "delivery_artifact_root": ".omo/_delivery/ingress/standards/",
            "mode": "brokered",
            "category": "human_cli",
        },
        {
            "name": "omo-capability-registry-scan",
            "entrypoint": "omo-capability capability scan --write",
            "runtime_ref": "projects/omo/src/omo/omo_capability.py:scan_command",
            "mutation_target": ".omo/capabilities/INDEX.md + .omo/capabilities/projects-capabilities.yaml + .omo/capabilities/sharedwork-sample.yaml + .omo/capabilities/system-packages.yaml + .omo/capabilities/agent-clis.yaml",
            "broker_ref": "projects/omo/src/omo/omo_ingress.py:write_capability_registry_bundle",
            "delivery_artifact_root": ".omo/_delivery/ingress/capabilities/",
            "mode": "brokered",
            "category": "human_cli",
        },
        {
            "name": "omo-capability-registry-register",
            "entrypoint": "omo-capability capability register <file>",
            "runtime_ref": "projects/omo/src/omo/omo_capability.py:register_command",
            "mutation_target": ".omo/capabilities/manual-capabilities.yaml",
            "broker_ref": "projects/omo/src/omo/omo_ingress.py:write_manual_capabilities",
            "delivery_artifact_root": ".omo/_delivery/ingress/capabilities/",
            "mode": "brokered",
            "category": "human_cli",
        },
        {
            "name": "omo-task-center-skill-manifest",
            "entrypoint": "projects/omo/src/omo/omo_skill.py:register_skill_manifest",
            "runtime_ref": "projects/omo/src/omo/omo_skill.py:register_skill_manifest",
            "mutation_target": ".omo/_truth/task-center/skills/*.yaml",
            "broker_ref": "projects/omo/src/omo/omo_ingress.py:create_skill_manifest",
            "delivery_artifact_root": ".omo/_delivery/ingress/task-center/skills/",
            "mode": "brokered",
            "category": "governance_ingress",
        },
        {
            "name": "omo-task-center-discovery-registry",
            "entrypoint": "projects/omo/src/omo/omo_discovery.py:discover_task_blueprints",
            "runtime_ref": "projects/omo/src/omo/omo_discovery.py:discover_task_blueprints",
            "mutation_target": ".omo/_truth/task-center/discovery-registry.yaml",
            "broker_ref": "projects/omo/src/omo/omo_ingress.py:write_discovery_registry",
            "delivery_artifact_root": ".omo/_delivery/ingress/task-center/discovery/",
            "mode": "brokered",
            "category": "governance_ingress",
        },
        {
            "name": "omo-self-healing-debt",
            "entrypoint": "projects/omo/src/omo/omo_self_healing.py:SelfHealingEngine._create_debt",
            "runtime_ref": "projects/omo/src/omo/omo_self_healing.py:SelfHealingEngine._create_debt",
            "mutation_target": ".omo/debt/items/*.yaml + .omo/_truth/registry/debt.yaml",
            "broker_ref": "projects/omo/src/omo/omo_ingress.py:upsert_debt_item",
            "delivery_artifact_root": ".omo/_delivery/ingress/debts/",
            "mode": "brokered",
            "category": "governance_ingress",
        },
        {
            "name": "omo-bridge-bmad-openspec",
            "entrypoint": "omo bridge --format bmad|openspec",
            "runtime_ref": "projects/omo/src/omo/omo_bridge.py:_import_bmad",
            "mutation_target": ".omo/tasks/planned/",
            "broker_ref": "projects/omo/src/omo/omo_ingress.py:create_planned_task",
            "delivery_artifact_root": ".omo/_delivery/ingress/tasks/",
            "mode": "brokered",
            "category": "bridge_import",
        },
        {
            "name": "omo-bridge-fast-track",
            "entrypoint": "omo bridge --format fast_track",
            "runtime_ref": "projects/omo/src/omo/omo_bridge.py:_import_fast_track",
            "mutation_target": ".omo/tasks/planned/",
            "broker_ref": "projects/omo/src/omo/omo_ingress.py:create_planned_task",
            "delivery_artifact_root": ".omo/_delivery/ingress/tasks/",
            "mode": "brokered",
            "category": "bridge_import",
        },
        {
            "name": "omo-bridge-pitch",
            "entrypoint": "omo bridge --format pitch",
            "runtime_ref": "projects/omo/src/omo/omo_bridge.py:_import_pitch",
            "mutation_target": ".omo/goals/current.yaml + .omo/tasks/planned/",
            "broker_ref": "projects/omo/src/omo/omo_goal.py:cmd_goal_create + projects/omo/src/omo/omo_ingress.py:create_planned_task",
            "delivery_artifact_root": ".omo/_delivery/ingress/goals/ + .omo/_delivery/ingress/tasks/",
            "mode": "brokered",
            "category": "bridge_import",
        },
        {
            "name": "ecos-mof-state-bridge-m1-to-omo",
            "entrypoint": "python3 projects/ecos/src/ecos/ssot/tools/mof-state-bridge.py --m1-to-omo",
            "runtime_ref": "projects/ecos/src/ecos/ssot/tools/mof-state-bridge.py:main (flag=--m1-to-omo)",
            "mutation_target": ".omo/tasks/planned/",
            "broker_ref": "projects/omo/src/omo/omo_ingress.py:create_planned_task",
            "delivery_artifact_root": ".omo/_delivery/ingress/tasks/",
            "mode": "brokered",
            "category": "bridge_import",
        },
        {
            "name": "c2g-storage-save-bet",
            "entrypoint": "projects/c2g/src/c2g/adapters.py:EcosStorageProvider.save_bet",
            "runtime_ref": "projects/c2g/src/c2g/adapters.py:EcosStorageProvider.save_bet",
            "mutation_target": ".omo/goals/current.yaml",
            "broker_ref": "projects/omo/src/omo/omo_ingress.py:create_goal",
            "delivery_artifact_root": ".omo/_delivery/ingress/goals/",
            "mode": "brokered",
            "category": "c2g_adapter",
        },
        {
            "name": "c2g-storage-save-task",
            "entrypoint": "projects/c2g/src/c2g/adapters.py:EcosStorageProvider.save_task",
            "runtime_ref": "projects/c2g/src/c2g/adapters.py:EcosStorageProvider.save_task",
            "mutation_target": ".omo/tasks/planned/",
            "broker_ref": "projects/omo/src/omo/omo_ingress.py:create_planned_task",
            "delivery_artifact_root": ".omo/_delivery/ingress/tasks/",
            "mode": "brokered",
            "category": "c2g_adapter",
        },
        {
            "name": "omo-state-refresh",
            "entrypoint": "omo state refresh",
            "runtime_ref": "projects/omo/src/omo/omo_state.py:cmd_state_refresh",
            "mutation_target": ".omo/state/system_health.yaml",
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
            "delivery_artifact_root": ".omo/_delivery/ingress/state/",
            "mode": "brokered",
            "category": "governance_ingress",
        },
        {
            "name": "omo-audit-sync-system-projection",
            "entrypoint": "python -m omo.omo_audit_sync --apply",
            "runtime_ref": "projects/omo/src/omo/omo_audit_sync.py:apply_diff",
            "mutation_target": ".omo/state/system.yaml (whitelisted audit projection fields)",
            "broker_ref": "projects/omo/src/omo/omo_ingress.py:write_system_projection_fields",
            "delivery_artifact_root": ".omo/_delivery/ingress/state/",
            "mode": "brokered",
            "category": "runtime_cache",
        },
    ]


def _mutation_surface_category_counts(items: list[dict[str, object]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        category = str(item.get("category", "unclassified"))
        counts[category] = counts.get(category, 0) + 1
    return dict(sorted(counts.items()))


def _worker_internal_write_profiles_snapshot() -> list[dict[str, object]]:
    return [
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
                ".omo/_delivery/ingress/tasks/*-yield-*.yaml",
                ".omo/_delivery/ingress/tasks/*-archive-*.yaml",
                ".omo/_delivery/ingress/audits/*.yaml",
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
                ".omo/_delivery/ingress/tasks/*-route-self-evolution-*.yaml",
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
                ".omo/_delivery/ingress/tasks/*-promote-*.yaml",
                ".omo/_delivery/ingress/tasks/*-revert-*.yaml",
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
                ".omo/_delivery/ingress/tasks/*-promotion-approval-*.yaml",
                ".omo/_delivery/ingress/tasks/*-contract-request-*.yaml",
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
                ".omo/_delivery/ingress/tasks/*-blocked-*.yaml",
                ".omo/_delivery/ingress/tasks/*-consensus-*.yaml",
                ".omo/_delivery/ingress/task-center/*.yaml",
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
                ".omo/_delivery/ingress/governance-overlay/*.yaml",
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


def _worker_profile_subtype_counts(
    items: list[dict[str, object]],
) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        subtype = str(item.get("subtype", "unknown"))
        counts[subtype] = counts.get(subtype, 0) + 1
    return dict(sorted(counts.items()))


def _check_internal_write_profile_registry(
    workspace_root: Path,
) -> tuple[dict[str, object], list[str]]:
    registry_path = (
        workspace_root / ".omo" / "_truth" / "registry" / "internal-write-profiles.yaml"
    )
    runtime_items = _worker_internal_write_profiles_snapshot()
    if not registry_path.exists():
        return {
            "exists": False,
            "path": str(registry_path),
            "registered_profile_names": [],
            "runtime_profile_names": [item["name"] for item in runtime_items],
            "runtime_profiles": runtime_items,
        }, ["internal write profile registry missing"]

    registry = _load_yaml(registry_path)
    profiles = registry.get("profiles")
    if not isinstance(profiles, list):
        return {
            "exists": True,
            "path": str(registry_path),
            "registered_profile_names": [],
            "runtime_profile_names": [item["name"] for item in runtime_items],
            "runtime_profiles": runtime_items,
        }, ["internal write profile registry: profiles block missing or not a list"]

    registered_items = [
        item for item in profiles if isinstance(item, dict) and item.get("name")
    ]
    keys = ("runtime_ref", "category", "subtype", "writes", "promotion_surface", "note")
    registered_by_name = {
        str(item["name"]): {k: item.get(k) for k in keys} for item in registered_items
    }
    runtime_by_name = {
        str(item["name"]): {k: item.get(k) for k in keys} for item in runtime_items
    }
    registered_names = sorted(registered_by_name)
    runtime_names = sorted(runtime_by_name)
    issues: list[str] = []
    for name in sorted(set(runtime_names) - set(registered_names)):
        issues.append(
            f"internal write profile registry missing runtime profile: {name}"
        )
    for name in sorted(set(registered_names) - set(runtime_names)):
        issues.append(f"internal write profile registry contains stale profile: {name}")
    for name in sorted(set(registered_names).intersection(runtime_names)):
        if registered_by_name[name] != runtime_by_name[name]:
            issues.append(f"internal write profile registry drift for {name}")
    registered_profiles = [
        registered_by_name[name] | {"name": name} for name in registered_names
    ]
    return {
        "exists": True,
        "path": str(registry_path),
        "registered_profile_names": registered_names,
        "runtime_profile_names": runtime_names,
        "registered_subtype_counts": _worker_profile_subtype_counts(
            registered_profiles
        ),
        "runtime_subtype_counts": _worker_profile_subtype_counts(runtime_items),
        "registered_profiles": registered_profiles,
        "runtime_profiles": runtime_items,
    }, issues


def _check_mutation_surface_registry(
    workspace_root: Path,
) -> tuple[dict[str, object], list[str]]:
    registry_path = (
        workspace_root / ".omo" / "_truth" / "registry" / "mutation-surfaces.yaml"
    )
    runtime_items = _mutation_surface_registry_snapshot()
    if not registry_path.exists():
        return {
            "exists": False,
            "path": str(registry_path),
            "registered_surface_names": [],
            "runtime_surface_names": [item["name"] for item in runtime_items],
            "runtime_surfaces": runtime_items,
        }, ["mutation surface registry missing"]

    registry = _load_yaml(registry_path)
    surfaces = registry.get("surfaces")
    if not isinstance(surfaces, list):
        return {
            "exists": True,
            "path": str(registry_path),
            "registered_surface_names": [],
            "runtime_surface_names": [item["name"] for item in runtime_items],
            "runtime_surfaces": runtime_items,
        }, ["mutation surface registry: surfaces block missing or not a list"]

    registered_items = [
        item for item in surfaces if isinstance(item, dict) and item.get("name")
    ]
    registered_by_name = {
        str(item["name"]): {
            k: item.get(k)
            for k in (
                "entrypoint",
                "runtime_ref",
                "mutation_target",
                "broker_ref",
                "delivery_artifact_root",
                "mode",
                "category",
            )
        }
        for item in registered_items
    }
    runtime_by_name = {
        str(item["name"]): {
            k: item.get(k)
            for k in (
                "entrypoint",
                "runtime_ref",
                "mutation_target",
                "broker_ref",
                "delivery_artifact_root",
                "mode",
                "category",
            )
        }
        for item in runtime_items
    }
    registered_names = sorted(registered_by_name)
    runtime_names = sorted(runtime_by_name)
    issues: list[str] = []
    for name in sorted(set(runtime_names) - set(registered_names)):
        issues.append(f"mutation surface registry missing runtime surface: {name}")
    for name in sorted(set(registered_names) - set(runtime_names)):
        issues.append(f"mutation surface registry contains stale surface: {name}")
    for name in sorted(set(registered_names).intersection(runtime_names)):
        if registered_by_name[name] != runtime_by_name[name]:
            issues.append(f"mutation surface registry drift for {name}")
    return {
        "exists": True,
        "path": str(registry_path),
        "registered_surface_names": registered_names,
        "runtime_surface_names": runtime_names,
        "registered_category_counts": _mutation_surface_category_counts(
            [registered_by_name[name] | {"name": name} for name in registered_names]
        ),
        "runtime_category_counts": _mutation_surface_category_counts(runtime_items),
        "registered_surfaces": [
            registered_by_name[name] | {"name": name} for name in registered_names
        ],
        "runtime_surfaces": runtime_items,
    }, issues


def _resolve_ingress_task_carrier(omo_dir: Path, item_id: str) -> Path | None:
    direct_candidates = [
        omo_dir / "tasks" / "planned" / f"{item_id}.yaml",
        omo_dir / "tasks" / "done" / f"{item_id}.yaml",
        omo_dir / "tasks" / "archived" / f"{item_id}.yaml",
        omo_dir / "tasks" / "archive" / f"{item_id}.yaml",
        omo_dir / "tasks" / "completed" / f"{item_id}.yaml",
        omo_dir / "tasks" / "blocked" / f"{item_id}.yaml",
        omo_dir / "tasks" / "active" / f"{item_id}.yaml",
        omo_dir / "tasks" / "registry" / "done" / f"{item_id}.yaml",
    ]
    for path in direct_candidates:
        if path.exists():
            return path

    task_root = omo_dir / "tasks"
    if not task_root.exists():
        return None
    for path in task_root.rglob(f"{item_id}.yaml"):
        if path.is_file():
            return path
    return None


def _check_ingress_registry(
    workspace_root: Path,
) -> tuple[dict[str, object], list[str]]:
    omo_dir = workspace_root / ".omo"
    registry_path = omo_dir / "_delivery" / "ingress" / "registry.yaml"
    if not registry_path.exists():
        return {
            "exists": False,
            "path": str(registry_path),
            "goal_ids": [],
            "goal_source_refs": [],
            "task_ids": [],
            "task_source_refs": [],
            "debt_ids": [],
            "debt_source_refs": [],
            "capability_ids": [],
            "capability_source_refs": [],
        }, [
            "ingress registry: required file missing: .omo/_delivery/ingress/registry.yaml"
        ]

    registry = _load_yaml(registry_path)
    issues: list[str] = []
    goals = registry.get("goals")
    tasks = registry.get("tasks")
    debts = registry.get("debts")
    capabilities = registry.get("capabilities")
    if not isinstance(goals, dict):
        issues.append("ingress registry: goals block missing or not a mapping")
        goals = {}
    if not isinstance(tasks, dict):
        issues.append("ingress registry: tasks block missing or not a mapping")
        tasks = {}
    if not isinstance(debts, dict):
        issues.append("ingress registry: debts block missing or not a mapping")
        debts = {}
    if not isinstance(capabilities, dict):
        issues.append("ingress registry: capabilities block missing or not a mapping")
        capabilities = {}

    goals_by_id = goals.get("by_id")
    goals_by_source_ref = goals.get("by_source_ref")
    tasks_by_id = tasks.get("by_id")
    tasks_by_source_ref = tasks.get("by_source_ref")
    debts_by_id = debts.get("by_id")
    debts_by_source_ref = debts.get("by_source_ref")
    capabilities_by_id = capabilities.get("by_id")
    capabilities_by_source_ref = capabilities.get("by_source_ref")
    for label, bucket in [
        ("goals.by_id", goals_by_id),
        ("goals.by_source_ref", goals_by_source_ref),
        ("tasks.by_id", tasks_by_id),
        ("tasks.by_source_ref", tasks_by_source_ref),
        ("debts.by_id", debts_by_id),
        ("debts.by_source_ref", debts_by_source_ref),
        ("capabilities.by_id", capabilities_by_id),
        ("capabilities.by_source_ref", capabilities_by_source_ref),
    ]:
        if not isinstance(bucket, dict):
            issues.append(f"ingress registry: {label} missing or not a mapping")

    goals_by_id = goals_by_id if isinstance(goals_by_id, dict) else {}
    goals_by_source_ref = (
        goals_by_source_ref if isinstance(goals_by_source_ref, dict) else {}
    )
    tasks_by_id = tasks_by_id if isinstance(tasks_by_id, dict) else {}
    tasks_by_source_ref = (
        tasks_by_source_ref if isinstance(tasks_by_source_ref, dict) else {}
    )
    debts_by_id = debts_by_id if isinstance(debts_by_id, dict) else {}
    debts_by_source_ref = (
        debts_by_source_ref if isinstance(debts_by_source_ref, dict) else {}
    )
    capabilities_by_id = (
        capabilities_by_id if isinstance(capabilities_by_id, dict) else {}
    )
    capabilities_by_source_ref = (
        capabilities_by_source_ref if isinstance(capabilities_by_source_ref, dict) else {}
    )

    for item_id, meta in goals_by_id.items():
        if not isinstance(meta, dict):
            issues.append(f"ingress registry: goals.by_id.{item_id} not a mapping")
            continue
        if meta.get("artifact_ref") != f".omo/_delivery/ingress/goals/{item_id}.yaml":
            issues.append(
                f"ingress registry: goals.by_id.{item_id} artifact_ref mismatch"
            )
        if not (omo_dir / "goals" / "current.yaml").exists():
            issues.append("ingress registry: goals/current.yaml missing")
        source_ref = meta.get("source_ref", "")
        if source_ref and goals_by_source_ref.get(source_ref) != item_id:
            issues.append(
                f"ingress registry: goals source_ref reverse mapping mismatch for {item_id}"
            )

    for source_ref, item_id in goals_by_source_ref.items():
        if item_id not in goals_by_id:
            issues.append(
                f"ingress registry: goals.by_source_ref points to missing id {item_id}"
            )

    for item_id, meta in tasks_by_id.items():
        if not isinstance(meta, dict):
            issues.append(f"ingress registry: tasks.by_id.{item_id} not a mapping")
            continue
        if meta.get("artifact_ref") != f".omo/_delivery/ingress/tasks/{item_id}.yaml":
            issues.append(
                f"ingress registry: tasks.by_id.{item_id} artifact_ref mismatch"
            )
        task_carrier = _resolve_ingress_task_carrier(omo_dir, item_id)
        if task_carrier is None:
            issues.append(f"ingress registry: task carrier missing for {item_id}")
        source_ref = meta.get("source_ref", "")
        if source_ref and tasks_by_source_ref.get(source_ref) != item_id:
            issues.append(
                f"ingress registry: tasks source_ref reverse mapping mismatch for {item_id}"
            )

    for source_ref, item_id in tasks_by_source_ref.items():
        if item_id not in tasks_by_id:
            issues.append(
                f"ingress registry: tasks.by_source_ref points to missing id {item_id}"
            )

    for item_id, meta in debts_by_id.items():
        if not isinstance(meta, dict):
            issues.append(f"ingress registry: debts.by_id.{item_id} not a mapping")
            continue
        if meta.get("artifact_ref") != f".omo/_delivery/ingress/debts/{item_id}.yaml":
            issues.append(
                f"ingress registry: debts.by_id.{item_id} artifact_ref mismatch"
            )
        if not (omo_dir / "debt" / "items" / f"{item_id}.yaml").exists():
            issues.append(f"ingress registry: debt item missing for {item_id}")
        source_ref = meta.get("source_ref", "")
        if source_ref and debts_by_source_ref.get(source_ref) != item_id:
            issues.append(
                f"ingress registry: debts source_ref reverse mapping mismatch for {item_id}"
            )

    for source_ref, item_id in debts_by_source_ref.items():
        if item_id not in debts_by_id:
            issues.append(
                f"ingress registry: debts.by_source_ref points to missing id {item_id}"
            )

    capability_expected_targets = {
        "bundle": [
            omo_dir / "capabilities" / "INDEX.md",
            omo_dir / "capabilities" / "projects-capabilities.yaml",
            omo_dir / "capabilities" / "sharedwork-sample.yaml",
            omo_dir / "capabilities" / "system-packages.yaml",
            omo_dir / "capabilities" / "agent-clis.yaml",
        ],
        "manual-capabilities": [
            omo_dir / "capabilities" / "manual-capabilities.yaml",
        ],
    }
    for item_id, meta in capabilities_by_id.items():
        if not isinstance(meta, dict):
            issues.append(f"ingress registry: capabilities.by_id.{item_id} not a mapping")
            continue
        artifact_ref = meta.get("artifact_ref")
        if not isinstance(artifact_ref, str) or not artifact_ref.startswith(
            ".omo/_delivery/ingress/capabilities/"
        ):
            issues.append(
                f"ingress registry: capabilities.by_id.{item_id} artifact_ref mismatch"
            )
        for expected_path in capability_expected_targets.get(item_id, []):
            if not expected_path.exists():
                issues.append(
                    f"ingress registry: capability target missing for {item_id}: {expected_path.relative_to(omo_dir.parent)}"
                )
        source_ref = meta.get("source_ref", "")
        if source_ref and capabilities_by_source_ref.get(source_ref) != item_id:
            issues.append(
                f"ingress registry: capabilities source_ref reverse mapping mismatch for {item_id}"
            )

    for source_ref, item_id in capabilities_by_source_ref.items():
        if item_id not in capabilities_by_id:
            issues.append(
                f"ingress registry: capabilities.by_source_ref points to missing id {item_id}"
            )

    return {
        "exists": True,
        "path": str(registry_path),
        "goal_ids": sorted(goals_by_id.keys()),
        "goal_source_refs": sorted(goals_by_source_ref.keys()),
        "task_ids": sorted(tasks_by_id.keys()),
        "task_source_refs": sorted(tasks_by_source_ref.keys()),
        "debt_ids": sorted(debts_by_id.keys()),
        "debt_source_refs": sorted(debts_by_source_ref.keys()),
        "capability_ids": sorted(capabilities_by_id.keys()),
        "capability_source_refs": sorted(capabilities_by_source_ref.keys()),
    }, issues


def _candidate_roots(start: Path) -> list[Path]:
    current = start.resolve()
    if current.is_file():
        current = current.parent
    return [current, *current.parents]


def resolve_governance_workspace_root(start: Path | None = None) -> Path:
    starts: list[Path] = []
    if start is not None:
        starts.append(start)
    starts.append(Path.cwd())
    starts.append(Path(__file__).resolve())

    seen: set[Path] = set()
    for origin in starts:
        for candidate in _candidate_roots(origin):
            if candidate in seen:
                continue
            seen.add(candidate)
            if (candidate / ".omo").exists() and (
                (candidate / "projects" / "c2g").exists()
                or (candidate / "projects" / "omo").exists()
            ):
                return candidate
    for origin in starts:
        for candidate in _candidate_roots(origin):
            if (candidate / ".omo").exists():
                return candidate
    raise FileNotFoundError("unable to locate workspace root containing .omo/")


def build_governance_surfaces_report(workspace_root: Path) -> dict[str, object]:
    omo_dir = workspace_root / ".omo"
    registry_path = omo_dir / "_truth" / "registry" / "omo-governance-surfaces.yaml"
    standard_path = omo_dir / "standards" / "omo-governance-surfaces.md"

    if not omo_dir.is_dir():
        raise FileNotFoundError(f".omo not found: {omo_dir}")
    if not registry_path.exists():
        raise FileNotFoundError(f"registry missing: {registry_path}")

    registry = _load_yaml(registry_path)
    registered_top_levels = sorted(
        {
            top
            for top in (
                _asset_ref_to_top_level(item.get("ref", ""))
                for item in registry.get("assets", [])
            )
            if top
        }
    )
    observed_top_levels = _top_level_entries(omo_dir)

    missing_registered_roots = sorted(
        top for top in registered_top_levels if not (omo_dir / top).exists()
    )
    unregistered_top_levels = sorted(
        top for top in observed_top_levels if top not in registered_top_levels
    )
    constrained_present = sorted(
        item.get("ref", "")
        for item in registry.get("assets", [])
        if item.get("status") == "constrained"
        and (workspace_root / item.get("ref", "")).exists()
    )

    c2g_refs, c2g_issues = _read_c2g_governance_refs(workspace_root)
    expected_refs = [
        ".omo/standards/omo-governance-surfaces.md",
        ".omo/_truth/registry/omo-governance-surfaces.yaml",
    ]
    missing_c2g_refs = [ref for ref in expected_refs if ref not in c2g_refs]
    direct_io_gate_present = _has_direct_io_gate(workspace_root)
    task_policy_gate_present = _has_task_policy_gate(workspace_root)
    mutation_surface_gate_present = _has_mutation_surface_gate(workspace_root)
    internal_write_profile_gate_present = _has_internal_write_profile_gate(
        workspace_root
    )
    state_plane_asset_gate_present = _has_state_plane_asset_gate(workspace_root)
    c2g_omo_boundary_gate_present = _has_c2g_omo_boundary_gate(workspace_root)
    ingress_artifact_gate_present = _has_ingress_artifact_gate(workspace_root)
    mutation_ledger_gate_present = _has_mutation_ledger_gate(workspace_root)
    goals_runtime_entry, goals_runtime_entry_issues = _check_goals_runtime_entry(
        omo_dir
    )
    ingress_registry, ingress_registry_issues = _check_ingress_registry(workspace_root)
    ingress_artifacts, ingress_artifact_issues = _check_ingress_artifacts(
        workspace_root
    )
    task_policy_registry, task_policy_registry_issues = _check_task_policy_registry(
        workspace_root
    )
    c2g_omo_boundary, c2g_omo_boundary_issues = _check_c2g_omo_boundary(workspace_root)
    state_plane_asset_registry, state_plane_asset_registry_issues = (
        _check_state_plane_asset_registry(workspace_root)
    )
    mutation_surface_registry, mutation_surface_registry_issues = (
        _check_mutation_surface_registry(workspace_root)
    )
    internal_write_profile_registry, internal_write_profile_registry_issues = (
        _check_internal_write_profile_registry(workspace_root)
    )
    worker_internal_write_profiles = _worker_internal_write_profiles_snapshot()

    issues: list[str] = []
    if not standard_path.exists():
        issues.append("governance surfaces standard missing")
    issues.extend(
        f"unregistered top-level asset: {top}" for top in unregistered_top_levels
    )
    issues.extend(
        f"registered top-level asset missing on disk: {top}"
        for top in missing_registered_roots
    )
    issues.extend(
        f"c2g governance ref missing from task builder: {ref}"
        for ref in missing_c2g_refs
    )
    if not direct_io_gate_present:
        issues.append("pre-commit direct io gate missing: omo-direct-io-gate")
    if not task_policy_gate_present:
        issues.append("pre-commit task policy gate missing: omo-task-policy-gate")
    if not mutation_surface_gate_present:
        issues.append(
            "pre-commit mutation surface gate missing: omo-mutation-surface-gate"
        )
    if not internal_write_profile_gate_present:
        issues.append(
            "pre-commit internal write profile gate missing: "
            "omo-internal-write-profile-gate"
        )
    if not state_plane_asset_gate_present:
        issues.append(
            "pre-commit state plane asset gate missing: omo-state-plane-asset-gate"
        )
    if not c2g_omo_boundary_gate_present:
        issues.append(
            "pre-commit c2g/omo boundary gate missing: omo-c2g-omo-boundary-gate"
        )
    if not ingress_artifact_gate_present:
        issues.append(
            "pre-commit ingress artifact gate missing: omo-ingress-artifact-gate"
        )
    if not mutation_ledger_gate_present:
        issues.append(
            "pre-commit mutation ledger gate missing: omo-mutation-ledger-gate"
        )
    issues.extend(goals_runtime_entry_issues)
    issues.extend(c2g_issues)
    issues.extend(c2g_omo_boundary_issues)
    issues.extend(ingress_registry_issues)
    issues.extend(ingress_artifact_issues)
    issues.extend(task_policy_registry_issues)
    issues.extend(state_plane_asset_registry_issues)
    issues.extend(mutation_surface_registry_issues)
    issues.extend(internal_write_profile_registry_issues)

    warnings = [
        f"constrained legacy asset present: {ref}" for ref in constrained_present
    ]

    status = "ok"
    if issues:
        status = "error"
    elif warnings:
        status = "warn"

    return {
        "workspace_root": str(workspace_root),
        "omo_dir": str(omo_dir),
        "registry_path": str(registry_path),
        "standard_path": str(standard_path),
        "registered_top_levels": registered_top_levels,
        "observed_top_levels": observed_top_levels,
        "missing_registered_roots": missing_registered_roots,
        "unregistered_top_levels": unregistered_top_levels,
        "constrained_present": constrained_present,
        "nested_omo_present": (omo_dir / ".omo").exists(),
        "c2g_governance_refs": c2g_refs,
        "c2g_missing_governance_refs": missing_c2g_refs,
        "direct_io_gate_present": direct_io_gate_present,
        "task_policy_gate_present": task_policy_gate_present,
        "mutation_surface_gate_present": mutation_surface_gate_present,
        "internal_write_profile_gate_present": internal_write_profile_gate_present,
        "state_plane_asset_gate_present": state_plane_asset_gate_present,
        "c2g_omo_boundary_gate_present": c2g_omo_boundary_gate_present,
        "ingress_artifact_gate_present": ingress_artifact_gate_present,
        "mutation_ledger_gate_present": mutation_ledger_gate_present,
        "goals_runtime_entry": goals_runtime_entry,
        "c2g_omo_boundary": c2g_omo_boundary,
        "ingress_registry": ingress_registry,
        "ingress_artifacts": ingress_artifacts,
        "task_policy_registry": task_policy_registry,
        "state_plane_asset_registry": state_plane_asset_registry,
        "mutation_surface_registry": mutation_surface_registry,
        "internal_write_profile_registry": internal_write_profile_registry,
        "worker_internal_write_profiles": worker_internal_write_profiles,
        "issues": issues,
        "warnings": warnings,
        "status": status,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="omo governance surfaces")
    parser.add_argument("--workspace-root", default=".", help="Workspace root")
    parser.add_argument("--json", action="store_true", help="Print JSON report")
    args = parser.parse_args(argv)

    workspace_root = resolve_governance_workspace_root(Path(args.workspace_root))
    report = build_governance_surfaces_report(workspace_root)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"status: {report['status']}")
        print(f"registered_top_levels: {', '.join(report['registered_top_levels'])}")
        print(f"observed_top_levels: {', '.join(report['observed_top_levels'])}")
        if report["warnings"]:
            print("warnings:")
            for warning in report["warnings"]:
                print(f"  - {warning}")
        if report["issues"]:
            print("issues:")
            for issue in report["issues"]:
                print(f"  - {issue}")
    return 0 if report["status"] in {"ok", "warn"} else 1


__all__ = ["build_governance_surfaces_report", "main"]
