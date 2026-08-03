"""P105 refactor: omo_governance_surfaces ingress-check 子模块 (从 omo_governance_surfaces.py 提取).

ADR-0098 P104 拆 snapshots 后, omo_governance_surfaces.py 1762→1244L, 仍 >800L warn.
P105 继续拆 _check_ingress_registry (204L, 最大) + 内部依赖 _resolve_ingress_task_carrier (23L),
共 228L (实际 229 含空白).

业务:
  - _resolve_ingress_task_carrier (L785-808, 23L): 解析 task carrier yaml 路径
  - _check_ingress_registry       (L809-1013, 204L): 校验 ingress registry.yaml
    - registry 结构 (goal/task/debt/capability ids)
    - 反向映射 (artifact_ref ↔ registry entry)
    - 落盘一致性 (registry → 真实 artifact 文件)
    - task_carrier 路径回落

模块依赖:
  - Path (stdlib)
  - yaml (stdlib, via parent module's _load_yaml re-export)
  - omo.omo_governance_surfaces._load_yaml (同模块内 helper, 3L)

向后兼容 (P88/P100-P104 模式):
  omo_governance_surfaces.py 通过 `from .omo_governance_surfaces_ingress import (...)` re-export,
  保持 `_check_ingress_registry()` 调用点 (P102 cmd_lint_ingress_registry wrapper) 不破.

P105 收益:
  - omo_governance_surfaces.py 1244L → 1016L, 接近 1000L 阈值
  - 13 god-module list: 仍 12 (本文件未出 error list, 但持续减重)
  - P106+ 推进: _check_ingress_artifacts / _check_task_policy_registry / _check_state_plane_asset_registry
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from omo.omo_ingress_paths import _registry_path
from omo.omo_shared import load_yaml_required


def _load_yaml(path):
    """Inline helper (P105): avoid circular import with omo_governance_surfaces."""
    return load_yaml_required(path)


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
) -> tuple[dict[str, Any], list[str]]:
    omo_dir = workspace_root / ".omo"
    registry_path = _registry_path(omo_dir)
    if not registry_path.exists():
        # Runtime cache absent on fresh clones is ok; missing registry under an
        # initialized ingress directory is a real issue.
        if not registry_path.parent.exists():
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
            }, []
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
            f"ingress registry: required file missing: {registry_path.relative_to(workspace_root)}"
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
        capabilities_by_source_ref
        if isinstance(capabilities_by_source_ref, dict)
        else {}
    )

    for item_id, meta in goals_by_id.items():
        if not isinstance(meta, dict):
            issues.append(f"ingress registry: goals.by_id.{item_id} not a mapping")
            continue
        if (
            meta.get("artifact_ref")
            != f"runtime/omo/_delivery/ingress/goals/{item_id}.yaml"
        ):
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
        if (
            meta.get("artifact_ref")
            != f"runtime/omo/_delivery/ingress/tasks/{item_id}.yaml"
        ):
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
        if (
            meta.get("artifact_ref")
            != f"runtime/omo/_delivery/ingress/debts/{item_id}.yaml"
        ):
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
            issues.append(
                f"ingress registry: capabilities.by_id.{item_id} not a mapping"
            )
            continue
        artifact_ref = meta.get("artifact_ref")
        if not isinstance(artifact_ref, str) or not artifact_ref.startswith(
            "runtime/omo/_delivery/ingress/capabilities/"
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
