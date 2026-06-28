#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .omo_shared import load_yaml_required


# P104 R1 (P106 修复): snapshots 子模块 re-export
from .omo_governance_surfaces_snapshots import (  # noqa: E402, F401
    _mutation_surface_category_counts,
    _mutation_surface_registry_snapshot,
    _worker_internal_write_profiles_snapshot,
    _worker_profile_subtype_counts,
)

# P105 R1: ingress-check 子模块 re-export
from .omo_governance_surfaces_ingress import (  # noqa: E402, F401
    _check_ingress_registry,
    _resolve_ingress_task_carrier,
)

# P106 R1: task-policy + ingress-artifacts 子模块 re-export
from .omo_governance_surfaces_task_policy import (  # noqa: E402, F401
    _check_task_policy_registry,
)

from .omo_governance_surfaces_ingress_artifacts import (  # noqa: E402, F401
    _check_ingress_artifacts,
)

# P110 R1: build_governance_surfaces_report 子模块 (extracted 254L from omo_governance_surfaces.py)
# Re-export 保持向后兼容 (cli.py / external callers)
from .omo_governance_surfaces_report import (  # noqa: E402, F401
    build_governance_surfaces_report,
)

# P107 R1: state-plane + mutation-surface 子模块 re-export
from .omo_governance_surfaces_state_plane import (  # noqa: E402, F401
    _check_state_plane_asset_registry,
)

from .omo_governance_surfaces_mutation_surface import (  # noqa: E402, F401
    _check_mutation_surface_registry,
)

# P108 R1: c2g-boundary + internal-write-profiles 子模块 re-export
from .omo_governance_surfaces_c2g_boundary import (  # noqa: E402, F401
    _check_c2g_omo_boundary,
)

from .omo_governance_surfaces_internal_write_profiles import (  # noqa: E402, F401
    _check_internal_write_profile_registry,
)

# P110-G R1: gates 子模块 re-export (F7114ABA 治本 — 破 child→parent circular)
from .omo_governance_surfaces_gates import (  # noqa: E402, F401
    _asset_ref_to_top_level,
    _candidate_roots,
    _check_goals_runtime_entry,
    _has_c2g_omo_boundary_gate,
    _has_direct_io_gate,
    _has_ingress_artifact_gate,
    _has_internal_write_profile_gate,
    _has_mutation_ledger_gate,
    _has_mutation_surface_gate,
    _has_state_plane_asset_gate,
    _has_task_policy_gate,
    _read_c2g_governance_refs,
    _top_level_entries,
    resolve_governance_workspace_root,
)


def _load_yaml(path: Path) -> dict:
    return load_yaml_required(path)


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
