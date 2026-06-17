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
        "issues": issues,
        "warnings": warnings,
        "status": status,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="omo governance surfaces")
    parser.add_argument("--workspace-root", default=".", help="Workspace root")
    parser.add_argument("--json", action="store_true", help="Print JSON report")
    args = parser.parse_args(argv)

    workspace_root = Path(args.workspace_root).resolve()
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
