#!/usr/bin/env python3
"""Tool Usage Audit — scan bin/ssot/ for dormant/orphaned tools.

Path B (减法收敛): identifies zero-call scripts without deleting them.
Checks: Makefile references, CI workflow references, cross-script imports.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]


def _scan_references(root: Path, name: str) -> dict[str, bool]:
    """Check if tool name appears in Makefile, CI workflows, or other scripts."""
    makefile = root / "Makefile"
    in_makefile = name in makefile.read_text() if makefile.exists() else False

    in_ci = False
    ci_dir = root / ".github" / "workflows"
    if ci_dir.is_dir():
        for wf in ci_dir.glob("*.yml"):
            if name in wf.read_text():
                in_ci = True
                break

    in_scripts = False
    for script_dir in [root / "bin", root / "projects"]:
        if not script_dir.is_dir():
            continue
        for py_file in script_dir.rglob("*.py"):
            if py_file.stem == name:
                continue
            try:
                if name in py_file.read_text():
                    in_scripts = True
                    break
            except Exception:
                continue
        if in_scripts:
            break

    return {"makefile": in_makefile, "ci": in_ci, "scripts": in_scripts}


def audit_tools(root: Path) -> dict[str, Any]:
    """Audit all bin/ssot/ tools."""
    ssot_dir = root / "bin" / "ssot"
    if not ssot_dir.is_dir():
        return {"error": "bin/ssot/ not found"}

    tools: list[dict[str, Any]] = []
    active_count = 0
    dormant_count = 0

    for py_file in sorted(ssot_dir.glob("*.py")):
        name = py_file.stem
        line_count = sum(1 for _ in open(py_file))
        refs = _scan_references(root, name)
        is_active = any(refs.values())
        status = "active" if is_active else "dormant"

        if is_active:
            active_count += 1
        else:
            dormant_count += 1

        tools.append({
            "name": name,
            "lines": line_count,
            "status": status,
            "refs": refs,
        })

    return {
        "schema": "tool-usage-audit/v1",
        "total_tools": len(tools),
        "active": active_count,
        "dormant": dormant_count,
        "dormant_tools": [t["name"] for t in tools if t["status"] == "dormant"],
        "tools": tools,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    result = audit_tools(args.root)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"Tool Usage Audit: {result['total_tools']} tools ({result['active']} active, {result['dormant']} dormant)")
        print()
        print("Dormant tools (no Makefile/CI/script references):")
        for name in result.get("dormant_tools", []):
            print(f"  ⚠️  {name}")
        if not result.get("dormant_tools"):
            print("  (none — all tools have references)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
