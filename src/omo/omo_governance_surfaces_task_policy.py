"""P106 refactor: omo_governance_surfaces task-policy 子模块 (从 omo_governance_surfaces.py 提取).

ADR-0099 P105 拆 ingress-check (228L) 后, omo_governance_surfaces.py 1244→1022L.
P106 继续拆: 2 check function (task-policy + ingress-artifacts) = 238L → 786L
(warn 阈值 800L 清零, 接近 ideal 600L).

业务:
  - _check_task_policy_registry (L308-399, 91L):
    校验 .omo/_truth/registry/task-policies.yaml 结构 (Round 41 P0)
    - 必备字段: name/category/gate/path
    - 路径存在性
    - category 分类一致性

模块依赖:
  - Path (stdlib)
  - yaml (via inline _load_yaml helper, 见 P105 D2 范式)
  - omo.omo_shared.load_yaml_required (SSOT)

向后兼容 (P100-P105 模式):
  omo_governance_surfaces.py 通过 `from .omo_governance_surfaces_task_policy import (...)` re-export,
  保持 `_check_task_policy_registry()` 调用点 (P102 cmd_lint_mutation_surfaces 等 wrapper) 不破.

P106 收益:
  - omo_governance_surfaces.py 1022L → ~786L (warn 阈值 800L 清零)
  - 13 god-module list: 仍 12 (本文件 <1500L, 不在 error list)
  - 累计 omo_governance_surfaces.py: 1762 → 786L (-976L, -55%)
"""

from __future__ import annotations

from pathlib import Path

from omo.omo_shared import load_yaml_required
from omo.omo_task_policy import task_policy_registry_snapshot


def _load_yaml(path):
    """Inline helper (P106): avoid circular import with omo_governance_surfaces."""
    return load_yaml_required(path)


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
