#!/usr/bin/env python3
"""验证 bos-services.yaml 中 transport=internal 的 module_path 是否可解析。

Usage:
    python bin/ssot/check-bos-internal-routes.py [--project <name>] [--domain <domain>]

Exit code 0 = all internal routes resolvable, 1 = one or more broken.
"""

from __future__ import annotations

import argparse
import importlib
import sys
from pathlib import Path

WS = Path(__file__).resolve().parents[2]


def get_bos_paths(project: str | None = None) -> list[Path]:
    """Get bos-services.yaml paths to check."""
    if project:
        return [WS / "projects" / project / "etc" / "bos-services.yaml"]
    paths = []
    for proj_dir in (WS / "projects").iterdir():
        bos = proj_dir / "etc" / "bos-services.yaml"
        if bos.exists():
            paths.append(bos)
    return paths


def inject_project_paths() -> None:
    """Inject all project src/ directories into sys.path."""
    for proj_dir in (WS / "projects").iterdir():
        src = proj_dir / "src"
        if src.is_dir() and str(src) not in sys.path:
            sys.path.insert(0, str(src))


def validate_bos_file(bos_path: Path, domain_filter: str | None = None) -> list[str]:
    """Validate internal routes in a bos-services.yaml file."""
    try:
        import yaml
    except ImportError:
        print("ERROR: pyyaml required. Run: uv run --with pyyaml python bin/ssot/check-bos-internal-routes.py")
        sys.exit(2)

    errors = []
    data = yaml.safe_load(bos_path.read_text())

    for svc in data.get("services", []):
        if svc.get("transport") != "internal":
            continue

        uri = svc.get("uri", "<unknown>")
        mp = svc.get("module_path", "")
        fn = svc.get("func_name", "")
        domain = svc.get("domain", "")

        # Optional domain filter
        if domain_filter and domain != domain_filter:
            continue

        if not mp:
            errors.append(f"{uri}: missing module_path")
            continue
        if not fn:
            errors.append(f"{uri}: missing func_name")
            continue

        try:
            mod = importlib.import_module(mp)
            if not hasattr(mod, fn):
                errors.append(f"{uri}: {mp} exists but missing {fn}")
        except ModuleNotFoundError:
            errors.append(f"{uri}: module_path={mp} not importable")
        except Exception as e:
            errors.append(f"{uri}: import error: {e}")

    return errors


def main():
    parser = argparse.ArgumentParser(description="Validate BOS internal route module_path resolvability")
    parser.add_argument("--project", type=str, help="Check specific project only")
    parser.add_argument("--domain", type=str, help="Filter by domain (e.g., governance)")
    args = parser.parse_args()

    inject_project_paths()
    bos_paths = get_bos_paths(args.project)

    if not bos_paths:
        print("No bos-services.yaml found")
        return 0

    total_errors = 0
    for bos_path in bos_paths:
        print(f"\n📋 Checking: {bos_path.relative_to(WS)}")
        errors = validate_bos_file(bos_path, domain_filter=args.domain)
        if errors:
            total_errors += len(errors)
            for err in errors:
                print(f"  ❌ {err}")
        else:
            print("  ✓ All internal routes resolvable")

    if total_errors:
        print(f"\n❌ {total_errors} error(s) found")
        return 1
    print("\n✓ All internal routes valid")
    return 0


if __name__ == "__main__":
    sys.exit(main())

