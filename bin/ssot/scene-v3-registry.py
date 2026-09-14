#!/usr/bin/env python3
"""Scene v3 Registry — auto-generate index of all v3 scene cards.

Scans .omo/_truth/scenarios/v3/ and produces:
  - .omo/_truth/registry/scene-cards-v3.yaml (structured index)
  - Terminal report (domain distribution, lifecycle stats, capability catalog)

Usage:
  python3 bin/ssot/scene-v3-registry.py scan
  python3 bin/ssot/scene-v3-registry.py generate
  python3 bin/ssot/scene-v3-registry.py report
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SCENES_DIR = ROOT / ".omo" / "_truth" / "scenarios" / "v3"
REGISTRY_PATH = ROOT / ".omo" / "_truth" / "registry" / "scene-cards-v3.yaml"


def scan_scenes() -> list[dict[str, Any]]:
    """Scan all v3 scene cards."""
    import yaml
    scenes = []
    if not SCENES_DIR.is_dir():
        return scenes
    for p in sorted(SCENES_DIR.glob("*.yaml")):
        try:
            with open(p, encoding="utf-8") as f:
                docs = list(yaml.safe_load_all(f))
            body = docs[-1] if len(docs) > 1 else docs[0]
            if isinstance(body, dict) and body.get("schema") == "scene-card/v3":
                scenes.append({
                    "scene_id": body.get("scene_id", p.stem),
                    "name": body.get("name", "?"),
                    "scene_class": body.get("scene_class", "?"),
                    "scene_type": body.get("scene_type", "?"),
                    "domain": body.get("domain", "?"),
                    "lifecycle": body.get("lifecycle", "?"),
                    "activation": body.get("activation", "?"),
                    "owner": body.get("owner", "?"),
                    "capability_refs": body.get("runtime", {}).get("sandbox", {}).get("capabilities", []),
                    "upstream": [u.get("scene", "?") for u in body.get("topology", {}).get("upstream", [])],
                    "downstream": [d.get("scene", "?") for d in body.get("topology", {}).get("downstream", [])],
                    "source_file": str(p.relative_to(ROOT)),
                })
        except Exception as e:
            print(f"  WARN: failed to parse {p}: {e}", file=sys.stderr)
    return scenes


def generate_registry(scenes: list[dict[str, Any]]) -> dict[str, Any]:
    """Generate structured registry."""
    # Aggregate stats
    domains: dict[str, int] = {}
    lifecycles: dict[str, int] = {}
    classes: dict[str, int] = {}
    all_capabilities: set[str] = set()

    for s in scenes:
        domains[s["domain"]] = domains.get(s["domain"], 0) + 1
        lifecycles[s["lifecycle"]] = lifecycles.get(s["lifecycle"], 0) + 1
        classes[s["scene_class"]] = classes.get(s["scene_class"], 0) + 1
        for cap in s["capability_refs"]:
            all_capabilities.add(cap)

    return {
        "schema": "scene-registry/v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "total_scenes": len(scenes),
        "domains": domains,
        "lifecycles": lifecycles,
        "classes": classes,
        "capabilities": sorted(all_capabilities),
        "scenes": scenes,
    }


def write_registry(registry: dict[str, Any]) -> None:
    """Write registry to YAML."""
    import yaml
    REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(REGISTRY_PATH, "w", encoding="utf-8") as f:
        yaml.dump(registry, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
    print(f"Registry written to {REGISTRY_PATH}")


def print_report(registry: dict[str, Any]) -> None:
    """Print terminal report."""
    print(f"\n{'='*60}")
    print(f"Scene v3 Registry Report")
    print(f"{'='*60}")
    print(f"Total scenes: {registry['total_scenes']}")
    print(f"Generated: {registry['generated_at']}")

    print(f"\nDomains:")
    for domain, count in sorted(registry["domains"].items()):
        print(f"  {domain:<15} {count:>3}")

    print(f"\nLifecycle:")
    for level, count in sorted(registry["lifecycles"].items()):
        print(f"  {level:<15} {count:>3}")

    print(f"\nClasses:")
    for cls, count in sorted(registry["classes"].items()):
        print(f"  {cls:<15} {count:>3}")

    print(f"\nCapabilities ({len(registry['capabilities'])}):")
    for cap in registry["capabilities"]:
        print(f"  - {cap}")

    print(f"\n{'='*60}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("scan", help="Scan and report")
    sub.add_parser("generate", help="Generate registry file")
    sub.add_parser("report", help="Print detailed report")

    args = parser.parse_args(argv)
    command = args.command or "scan"

    scenes = scan_scenes()
    if not scenes:
        print("No v3 scene cards found.")
        return 1

    registry = generate_registry(scenes)

    if command == "generate":
        write_registry(registry)
    elif command == "report":
        print_report(registry)
    else:
        print_report(registry)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
