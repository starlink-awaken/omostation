"""P107 refactor: omo_governance_surfaces mutation-surface 子模块 (从 omo_governance_surfaces.py 提取).

业务:
  - _check_mutation_surface_registry (L420-532, 112L):
    校验 .omo/_truth/registry/mutation-surfaces.yaml 结构 (Round 30 P0)
    - surfaces 块结构
    - registered vs runtime surface names 一致性
    - category_counts 校验 (via _mutation_surface_category_counts helper)

模块依赖:
  - Path (stdlib)
  - yaml (via inline _load_yaml helper, P105 D2 范式)
  - omo.omo_shared.load_yaml_required (SSOT)
  - omo.omo_governance_surfaces_snapshots (sibling module, 跨子模块 import:
    _mutation_surface_registry_snapshot + _mutation_surface_category_counts)

向后兼容 (P100-P106 模式):
  omo_governance_surfaces.py 通过 `from .omo_governance_surfaces_mutation_surface import (...)` re-export,
  保持 `_check_mutation_surface_registry()` 调用点 (P102 cmd_lint_mutation_surfaces wrapper) 不破.

P107 关键差异: mutation_surface 子模块**需要 import snapshots 子模块** (cross-sibling import),
因为 _check_mutation_surface_registry 内部直接调用 _mutation_surface_registry_snapshot().
无 circular 风险 (snapshots 是 pure data, 不依赖 mutation_surface).
"""

from __future__ import annotations

from pathlib import Path

from omo.omo_shared import load_yaml_required


def _load_yaml(path):
    """Inline helper (P107): avoid circular import with omo_governance_surfaces."""
    return load_yaml_required(path)


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


# P105 R1: ingress-check 子模块 (extracted 265L from omo_governance_surfaces.py)
# Re-export 保持向后兼容 (P102 cmd_lint_ingress_registry wrapper 调用点)
from .omo_governance_surfaces_ingress import (  # noqa: E402, F401
    _check_ingress_registry,
    _resolve_ingress_task_carrier,
)

# P104 R1 (补): snapshots 子模块 re-export (P104 Python 脚本漏写 re-export,
# P106 R3 lint 验证发现 _mutation_surface_registry_snapshot NameError)
# 保持 P104 拆解后内部 call sites (L360, L426, L627) 不破.
from .omo_governance_surfaces_snapshots import (  # noqa: E402, F401
    _mutation_surface_category_counts,
    _mutation_surface_registry_snapshot,
    _worker_internal_write_profiles_snapshot,
    _worker_profile_subtype_counts,
)

# P106 R1: task-policy + ingress-artifacts 子模块 (extracted 132+180=312L)
# Re-export 保持向后兼容 (P102 cmd_lint_mutation_surfaces 等 wrapper 调用点)
from .omo_governance_surfaces_task_policy import (  # noqa: E402, F401
    _check_task_policy_registry,
)

from .omo_governance_surfaces_ingress_artifacts import (  # noqa: E402, F401
    _check_ingress_artifacts,
)
