#!/usr/bin/env python3
"""Check that bin/ scripts are registered in bin/_registry/."""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
BIN_DIR = REPO / "bin"
REGISTRY_DIR = REPO / "bin" / "_registry"


def find_registered_scripts() -> set[str]:
    registered = set()
    if not REGISTRY_DIR.exists():
        return registered
    for path in REGISTRY_DIR.rglob("*.yaml"):
        try:
            text = path.read_text(encoding="utf-8")
            if "id:" in text and ".py" in text:
                for line in text.splitlines():
                    line = line.strip()
                    if line.startswith("id: ") and line.endswith(".py"):
                        script = line[4:].strip()
                        if script.startswith("bin/"):
                            registered.add(script)
        except Exception:
            continue
    return registered


def main() -> int:
    registered = find_registered_scripts()
    unregistered = []
    for path in sorted(BIN_DIR.rglob("*.py")):
        if any(part.startswith("_") for part in path.relative_to(BIN_DIR).parts):
            continue
        rel = f"bin/{path.relative_to(BIN_DIR)}"
        if rel not in registered:
            unregistered.append(rel)

    if unregistered:
        print(f"FAIL: {len(unregistered)} scripts not registered in bin/_registry/")
        for u in unregistered[:20]:
            print(f"  - {u}")
        if len(unregistered) > 20:
            print(f"  ... and {len(unregistered) - 20} more")
        return 1

    print("PASS: all bin/ scripts are registered in bin/_registry/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
