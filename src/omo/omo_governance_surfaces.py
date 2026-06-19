#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml


def _load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


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


def _check_ingress_registry(workspace_root: Path) -> tuple[dict[str, object], list[str]]:
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
        }, []

    registry = _load_yaml(registry_path)
    issues: list[str] = []
    goals = registry.get("goals")
    tasks = registry.get("tasks")
    debts = registry.get("debts")
    if not isinstance(goals, dict):
        issues.append("ingress registry: goals block missing or not a mapping")
        goals = {}
    if not isinstance(tasks, dict):
        issues.append("ingress registry: tasks block missing or not a mapping")
        tasks = {}
    if not isinstance(debts, dict):
        issues.append("ingress registry: debts block missing or not a mapping")
        debts = {}

    goals_by_id = goals.get("by_id")
    goals_by_source_ref = goals.get("by_source_ref")
    tasks_by_id = tasks.get("by_id")
    tasks_by_source_ref = tasks.get("by_source_ref")
    debts_by_id = debts.get("by_id")
    debts_by_source_ref = debts.get("by_source_ref")
    for label, bucket in [
        ("goals.by_id", goals_by_id),
        ("goals.by_source_ref", goals_by_source_ref),
        ("tasks.by_id", tasks_by_id),
        ("tasks.by_source_ref", tasks_by_source_ref),
        ("debts.by_id", debts_by_id),
        ("debts.by_source_ref", debts_by_source_ref),
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

    for item_id, meta in goals_by_id.items():
        if not isinstance(meta, dict):
            issues.append(f"ingress registry: goals.by_id.{item_id} not a mapping")
            continue
        if meta.get("artifact_ref") != f".omo/_delivery/ingress/goals/{item_id}.yaml":
            issues.append(f"ingress registry: goals.by_id.{item_id} artifact_ref mismatch")
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
            issues.append(f"ingress registry: tasks.by_id.{item_id} artifact_ref mismatch")
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
            issues.append(f"ingress registry: debts.by_id.{item_id} artifact_ref mismatch")
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

    return {
        "exists": True,
        "path": str(registry_path),
        "goal_ids": sorted(goals_by_id.keys()),
        "goal_source_refs": sorted(goals_by_source_ref.keys()),
        "task_ids": sorted(tasks_by_id.keys()),
        "task_source_refs": sorted(tasks_by_source_ref.keys()),
        "debt_ids": sorted(debts_by_id.keys()),
        "debt_source_refs": sorted(debts_by_source_ref.keys()),
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
            for top in (_asset_ref_to_top_level(item.get("ref", "")) for item in registry.get("assets", []))
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
        if item.get("status") == "constrained" and (workspace_root / item.get("ref", "")).exists()
    )

    c2g_refs, c2g_issues = _read_c2g_governance_refs(workspace_root)
    expected_refs = [
        ".omo/standards/omo-governance-surfaces.md",
        ".omo/_truth/registry/omo-governance-surfaces.yaml",
    ]
    missing_c2g_refs = [ref for ref in expected_refs if ref not in c2g_refs]
    direct_io_gate_present = _has_direct_io_gate(workspace_root)
    ingress_registry, ingress_registry_issues = _check_ingress_registry(workspace_root)

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
    issues.extend(c2g_issues)
    issues.extend(ingress_registry_issues)

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
        "ingress_registry": ingress_registry,
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
