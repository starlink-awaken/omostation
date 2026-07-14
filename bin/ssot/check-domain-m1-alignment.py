#!/usr/bin/env python3
"""
check-domain-m1-alignment.py — Detect drift between project-registry.yaml and eCOS M1 nodes

Validates that every project in `docs/project-registry.yaml` has a matching
M1 node (across all 37 types) in `ecos/src/ecos/ssot/mof/m1/`,
and reports any layer/metadata drift.

Usage:
    python3 bin/ssot/check-domain-m1-alignment.py [--json] [--strict] [--types]

Exit codes:
    0 - aligned (or warnings only)
    1 - misalignment detected (--strict only)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

WORKSPACE = Path(__file__).resolve().parents[2]
PROJ_REG = WORKSPACE / "docs" / "project-registry.yaml"
M1_ROOT = WORKSPACE / "projects" / "ecos" / "src" / "ecos" / "ssot" / "mof" / "m1"


def load_yaml(path: Path) -> dict:
    if not HAS_YAML:
        print("❌ PyYAML required. Install: pip install pyyaml", file=sys.stderr)
        sys.exit(2)
    return yaml.safe_load(path.read_text())


def get_projects() -> list[tuple[str, dict]]:
    data = load_yaml(PROJ_REG)
    projects = data.get("projects", {})
    return list(projects.items())


def get_m1_types() -> dict[str, int]:
    """Map M1 type -> count of files in that type's directory."""
    types = {}
    if not M1_ROOT.exists():
        return types
    for d in M1_ROOT.iterdir():
        if d.is_dir():
            types[d.name] = len(list(d.glob("*.yaml")))
    return types


def find_m1(project_id: str) -> list[Path]:
    """Find matching M1 nodes for a project (any type that references it)."""
    found = []
    if not M1_ROOT.exists():
        return found
    for type_dir in M1_ROOT.iterdir():
        if not type_dir.is_dir():
            continue
        # Look for files that reference the project
        for yaml_file in type_dir.glob("*.yaml"):
            if project_id.upper() in yaml_file.stem.upper():
                found.append(yaml_file)
    return found


def check_alignment() -> dict:
    projects = get_projects()
    m1_types = get_m1_types()
    aligned = []
    missing_m1 = []
    layer_drift = []

    for pid, entry in projects:
        if not isinstance(entry, dict):
            continue
        proj_layer = entry.get("layer", "")
        m1_files = find_m1(pid)
        if not m1_files:
            missing_m1.append(pid)
            continue
        # Aggregate layers from all M1 nodes
        layers = set()
        for f in m1_files:
            m1 = load_yaml(f)
            if "layer" in m1:
                layers.add(str(m1["layer"]))
        aligned.append({
            "id": pid,
            "registry_layer": proj_layer,
            "m1_layers": sorted(layers),
            "m1_paths": [str(f.relative_to(WORKSPACE)) for f in m1_files],
        })
        # Check layer drift
        if proj_layer and layers and proj_layer not in layers:
            layer_drift.append({
                "id": pid,
                "registry": proj_layer,
                "m1": sorted(layers),
            })

    return {
        "m1_type_counts": m1_types,
        "m1_total": sum(m1_types.values()),
        "total_projects": len(projects),
        "with_m1": len(aligned),
        "missing_m1": missing_m1,
        "layer_drift": layer_drift,
        "aligned": aligned,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--json", action="store_true", help="JSON output")
    ap.add_argument("--strict", action="store_true", help="Exit 1 on any drift")
    ap.add_argument("--types", action="store_true", help="Show M1 type breakdown only")
    args = ap.parse_args()

    if args.types:
        types = get_m1_types()
        print("📊 eCOS M1 node types (37 types):")
        for t, c in sorted(types.items(), key=lambda x: -x[1]):
            print(f"   {t:25s} {c:4d}")
        print(f"   {'TOTAL':25s} {sum(types.values()):4d}")
        return 0

    result = check_alignment()
    has_drift = bool(result["missing_m1"] or result["layer_drift"])

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print("📊 project-registry.yaml ↔ eCOS M1 nodes alignment (all 37 types)")
        print()
        print("M1 type breakdown:")
        for t, c in sorted(result["m1_type_counts"].items(), key=lambda x: -x[1])[:10]:
            print(f"   {t:25s} {c:4d}")
        print(f"   ... and {len(result['m1_type_counts']) - 10} more types")
        print(f"   {'TOTAL M1 NODES':25s} {result['m1_total']:4d}")
        print()
        print(f"   Total projects:        {result['total_projects']}")
        print(f"   With M1 nodes:         {result['with_m1']}")
        print(f"   Missing M1 (any type): {len(result['missing_m1'])}")
        if result["missing_m1"]:
            for pid in result["missing_m1"][:10]:
                print(f"     - {pid}")
        if len(result["missing_m1"]) > 10:
            print(f"     ... and {len(result['missing_m1']) - 10} more")
        print(f"   Layer drift:           {len(result['layer_drift'])}")
        if result["layer_drift"]:
            for d in result["layer_drift"]:
                print(f"     - {d['id']}: registry={d['registry']} ↔ m1={d['m1']}")
        if has_drift:
            print("\n❌ Drift detected")
        else:
            print("\n✅ All projects aligned with eCOS M1 nodes")

    return 1 if has_drift and args.strict else 0


if __name__ == "__main__":
    raise SystemExit(main())
