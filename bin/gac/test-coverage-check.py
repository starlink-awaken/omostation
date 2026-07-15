#!/usr/bin/env python3
"""GaC 测试覆盖门禁 — 检查每个 Python 项目是否有测试目录和测试文件.

Exit 1 if:
  1. A Python project has `src/` but no `tests/` dir
  2. A Python project has `tests/` but no `test_*.py` files
"""
from __future__ import annotations

import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]
MIN_TESTS_PER_PROJECT = 1

# Projects that are allowed to have zero tests (non-Python or infrastructure)
EXEMPT = {
    "cockpit-ui",  # TypeScript/Bun
    "family-hub",  # config only
    "l4-kernel",   # system layer
    "omo-debt",    # debt data, not code
    "gbrain",      # TypeScript/Bun (uses test/ dir)
}

# Projects with non-standard test directory
TEST_DIR_OVERRIDES = {
    "cockpit": "src/cockpit/tests",  # tests live under src/
}


def main() -> int:
    errors: list[str] = []

    for proj_dir in sorted(WORKSPACE.glob("projects/*/")):
        name = proj_dir.name
        if name in EXEMPT:
            continue

        src_dir = proj_dir / "src"
        tests_dir = proj_dir / "tests"

        # Only check Python projects (have src/)
        if not src_dir.is_dir():
            continue

        # Use override path if defined, otherwise default to tests/
        test_dir = proj_dir / TEST_DIR_OVERRIDES.get(name, "tests")

        if not test_dir.is_dir():
            errors.append(f"  ⚠️  {name}: has src/ but no {test_dir.relative_to(WORKSPACE)} directory")
            continue

        test_files = list(test_dir.rglob("test_*.py"))
        if len(test_files) < MIN_TESTS_PER_PROJECT:
            errors.append(
                f"  ⚠️  {name}: tests/ has {len(test_files)} test file(s), "
                f"minimum {MIN_TESTS_PER_PROJECT}"
            )

    if errors:
        print(f"[TEST-COVERAGE] ❌ {len(errors)} 个项目测试覆盖不足:")
        for err in errors:
            print(err)
        return 1

    print("[TEST-COVERAGE] ✅ 所有 Python 项目均有测试目录")
    return 0


if __name__ == "__main__":
    sys.exit(main())
