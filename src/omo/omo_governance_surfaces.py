#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import json
import sys
from pathlib import Path
from typing import Any

# P105 R1: ingress-check 子模块 re-export.  These names remain a public
# facade for CLI lint commands and downstream governance callers.
from .omo_governance_surfaces_ingress import (
    _check_ingress_registry,  # noqa: F401
    _resolve_ingress_task_carrier,  # noqa: F401
)

# P106 R1: task-policy + ingress-artifacts 子模块 re-export
from .omo_governance_surfaces_ingress_artifacts import (
    _check_ingress_artifacts,  # noqa: F401
)


# P110 R1: build_governance_surfaces_report 子模块 (extracted 254L from omo_governance_surfaces.py)
# Re-export 保持向后兼容 (cli.py / external callers)
from .omo_governance_surfaces_report import (
    build_governance_surfaces_report,
)

# P104 R1 (P106 修复): snapshots 子模块 re-export
from .omo_governance_surfaces_snapshots import (
    _mutation_surface_category_counts,
    _mutation_surface_registry_snapshot,
    _worker_internal_write_profiles_snapshot,
    _worker_profile_subtype_counts,
)
from .omo_shared import load_yaml_required
from .omo_task_policy import task_policy_registry_snapshot

# P107 R1: state-plane + mutation-surface 子模块 re-export


# P108 R1: c2g-boundary + internal-write-profiles 子模块 re-export


# P110-G R1: gates 子模块 re-export (F7114ABA 治本 — 破 child→parent circular)


def _load_yaml(path: Path) -> dict:  # type: ignore[no-redef]
    return load_yaml_required(path)


def _load_yaml(path):  # type: ignore[no-redef]
    """Inline helper (P108): avoid circular import with omo_governance_surfaces."""
    return load_yaml_required(path)


def _check_c2g_omo_boundary(
    workspace_root: Path,
) -> tuple[dict[str, Any], list[str]]:
    c2g_src = workspace_root / "projects" / "c2g" / "src" / "c2g"
    facade_path = c2g_src / "omo_client.py"
    summary: dict[str, Any] = {
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


def _load_yaml(path):  # type: ignore[no-redef]
    """Inline helper (P106): avoid circular import with omo_governance_surfaces."""
    return load_yaml_required(path)


def _check_task_policy_registry(
    workspace_root: Path,
) -> tuple[dict[str, Any], list[str]]:
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


def _load_yaml(path):  # type: ignore[no-redef]
    """Inline helper (P108): avoid circular import with omo_governance_surfaces."""
    return load_yaml_required(path)


def _check_internal_write_profile_registry(
    workspace_root: Path,
) -> tuple[dict[str, Any], list[str]]:
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

# P105 R1: ingress-check 子模块 re-export
# Re-export 保持向后兼容 (P102 cmd_lint_ingress_registry wrapper 调用点)

# P106 R1: task-policy + ingress-artifacts 子模块 re-export
# Re-export 保持向后兼容 (P102 cmd_lint_mutation_surfaces 等 wrapper 调用点)


# P107 R1: state-plane + mutation-surface 子模块 re-export
# Re-export 保持向后兼容 (P102 cmd_lint_state_plane_assets / cmd_lint_mutation_surfaces wrapper)


def _load_yaml(path):  # type: ignore[no-redef]
    """Inline helper (P107): avoid circular import with omo_governance_surfaces."""
    return load_yaml_required(path)


def _check_mutation_surface_registry(
    workspace_root: Path,
) -> tuple[dict[str, Any], list[str]]:
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

# P104 R1 (补): snapshots 子模块 re-export (P104 Python 脚本漏写 re-export,
# P106 R3 lint 验证发现 _mutation_surface_registry_snapshot NameError)
# 保持 P104 拆解后内部 call sites (L360, L426, L627) 不破.

# P106 R1: task-policy + ingress-artifacts 子模块 (extracted 132+180=312L)
# Re-export 保持向后兼容 (P102 cmd_lint_mutation_surfaces 等 wrapper 调用点)


def _load_yaml(path):
    """Inline helper (P107): avoid circular import with omo_governance_surfaces."""
    return load_yaml_required(path)


ALLOWED_PERSISTENCE_MODES = {
    "authoritative",
    "durable",
    "operational",
    "append_only",
    "archival",
    "compatibility_alias",
    "derived",  # .omo/_generated/ — CI/generated artifacts (gitignored)
    "ephemeral",  # .omo/autopilot/ — autopilot runtime state (session scoped)
}

ALLOWED_RETENTION_MODES = {
    "until_replaced",
    "manual_cleanup",
    "rolling_window",
    "append_forever",
    "manual_archive",
    "alias_only",
    "session_only",  # .omo/autopilot/ — session scoped retention
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


def _check_state_plane_asset_registry(
    workspace_root: Path,
) -> tuple[dict[str, Any], list[str]]:
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
        ) and (persistence_mode, retention_mode) != expected:
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


def _asset_ref_to_top_level(ref: str) -> str:
    normalized = ref.strip().strip("/")
    normalized = normalized.removeprefix(".omo/")
    if normalized == ".omo":
        return ""
    return normalized.split("/", 1)[0] if normalized else ""


def _top_level_entries(omo_dir: Path) -> list[str]:
    ignored = {".DS_Store", "__pycache__", ".omo", "_derived"}
    return sorted(
        entry.name for entry in omo_dir.iterdir() if entry.name not in ignored
    )


def _check_goals_runtime_entry(omo_dir: Path) -> tuple[dict[str, Any], list[str]]:
    goals_path = omo_dir / "goals"
    truth_goals_path = omo_dir / "_truth" / "goals"
    summary: dict[str, Any] = {
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
