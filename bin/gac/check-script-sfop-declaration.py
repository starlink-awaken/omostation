#!/usr/bin/env python3
"""Check that bin/ scripts declare SFOP_SLOT and DAO_LAYER."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
BIN_DIR = REPO / "bin"


def check_file(path: Path) -> tuple[bool, str | None]:
    try:
        text = path.read_text(encoding="utf-8")
        tree = ast.parse(text)
    except Exception as e:
        return False, f"parse_error: {e}"

    assignments: dict[str, ast.expr] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    assignments[target.id] = node.value

    missing = []
    for name in ("SFOP_SLOT", "DAO_LAYER"):
        if name not in assignments:
            missing.append(name)

    if missing:
        return False, f"missing declarations: {', '.join(missing)}"

    return True, None


def main() -> int:
    errors = []
    for path in sorted(BIN_DIR.rglob("*.py")):
        if any(part.startswith("_") and part not in ("__init__.py",) for part in path.relative_to(BIN_DIR).parts):
            continue
        ok, err = check_file(path)
        if not ok:
            errors.append(f"{path.relative_to(REPO)}: {err}")

    if errors:
        print(f"FAIL: {len(errors)} scripts missing SFOP_SLOT/DAO_LAYER declarations")
        for e in errors[:20]:
            print(f"  - {e}")
        if len(errors) > 20:
            print(f"  ... and {len(errors) - 20} more")
        return 1

    print("PASS: all bin/ scripts declare SFOP_SLOT/DAO_LAYER")
    return 0


if __name__ == "__main__":
    sys.exit(main())
