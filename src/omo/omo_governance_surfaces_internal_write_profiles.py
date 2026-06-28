"""P108 refactor: omo_governance_surfaces internal-write-profiles 子模块 (从 omo_governance_surfaces.py 提取).

业务:
  - _check_internal_write_profile_registry (L222-325, 103L):
    校验 worker internal write profile registry 与运行时清单是否一致 (Round 36 P0)
    - registered vs runtime profile names 一致性
    - subtype_counts 校验 (via _worker_profile_subtype_counts helper)

模块依赖:
  - Path (stdlib)
  - yaml (via inline _load_yaml helper, P105 D2 范式)
  - omo.omo_shared.load_yaml_required (SSOT)
  - omo.omo_governance_surfaces_snapshots (sibling module, 跨子模块 import:
    _worker_internal_write_profiles_snapshot + _worker_profile_subtype_counts)

P107 范式复用: child → sibling (同 parent) 直接 import, 无 circular 风险.

向后兼容 (P100-P107 模式):
  omo_governance_surfaces.py 通过 `from .omo_governance_surfaces_internal_write_profiles import (...)` re-export,
  保持 `_check_internal_write_profile_registry()` 调用点 (P102 cmd_lint_internal_write_profiles wrapper) 不破.
"""

from __future__ import annotations

from pathlib import Path

from omo.omo_shared import load_yaml_required


def _load_yaml(path):
    """Inline helper (P108): avoid circular import with omo_governance_surfaces."""
    return load_yaml_required(path)


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


# P107 R1: state-plane + mutation-surface 子模块 (extracted 128+154=282L)
# Re-export 保持向后兼容 (P102 cmd_lint_state_plane_assets / cmd_lint_mutation_surfaces wrapper)
# P104 R1 (P106 修复): snapshots 子模块 re-export
# 保持 P104 拆解后内部 call sites (L360, L426, L627) 不破.
from .omo_governance_surfaces_snapshots import (  # noqa: E402, F401
    _mutation_surface_category_counts,
    _mutation_surface_registry_snapshot,
    _worker_internal_write_profiles_snapshot,
    _worker_profile_subtype_counts,
)

# P105 R1: ingress-check 子模块 re-export
# Re-export 保持向后兼容 (P102 cmd_lint_ingress_registry wrapper 调用点)
from .omo_governance_surfaces_ingress import (  # noqa: E402, F401
    _check_ingress_registry,
    _resolve_ingress_task_carrier,
)

# P106 R1: task-policy + ingress-artifacts 子模块 re-export
# Re-export 保持向后兼容 (P102 cmd_lint_mutation_surfaces 等 wrapper 调用点)
from .omo_governance_surfaces_task_policy import (  # noqa: E402, F401
    _check_task_policy_registry,
)

from .omo_governance_surfaces_ingress_artifacts import (  # noqa: E402, F401
    _check_ingress_artifacts,
)

# P107 R1: state-plane + mutation-surface 子模块 re-export
# Re-export 保持向后兼容 (P102 cmd_lint_state_plane_assets / cmd_lint_mutation_surfaces wrapper)
from .omo_governance_surfaces_state_plane import (  # noqa: E402, F401
    _check_state_plane_asset_registry,
)

from .omo_governance_surfaces_mutation_surface import (  # noqa: E402, F401
    _check_mutation_surface_registry,
)
