#!/usr/bin/env python3
"""Cross-project test runner — run tests for all subprojects."""

from __future__ import annotations

import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]

PYTHON_PROJECTS = [
    ("ecos", "projects/ecos", ["uv", "run", "pytest", "tests/", "-q"], 600),
    ("omlxc", "projects/omlxc", ["uv", "run", "pytest", "tests/", "-q"], 180),
    ("cockpit", "projects/cockpit", ["uv", "run", "pytest", "tests/", "-q"], 120),
    ("family-hub", "projects/family-hub", ["uv", "run", "pytest", "tests/", "-q"], 120),
    ("knowledge", "projects/knowledge", ["uv", "run", "pytest", "tests/", "-q"], 120),
    ("model-driven", "projects/model-driven", ["uv", "run", "pytest", "tests/", "-q"], 180),
    ("observability", "projects/observability", ["uv", "run", "pytest", "tests/", "-q"], 120),
    ("aetherforge", "projects/aetherforge", ["uv", "run", "pytest", "tests/", "-q"], 180),
    ("l4-kernel", "projects/l4-kernel", ["uv", "run", "pytest", "tests/", "-q"], 300),
    ("metaos", "projects/metaos", ["uv", "run", "pytest", "tests/", "-q"], 120),
    ("runtime", "projects/runtime", ["uv", "run", "pytest", "tests/", "-q"], 300),
]

TYPESCRIPT_PROJECTS = [
    ("cockpit-ui", "projects/cockpit-ui", ["bun", "run", "test:unit"], 180),
]


def run_project(name: str, cwd: Path, cmd: list[str], timeout: int = 120) -> dict:
    """Run tests for a single project."""
    try:
        proc = subprocess.run(
            cmd,
            cwd=WORKSPACE / cwd,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
        )
        return {
            "name": name,
            "cwd": str(cwd),
            "cmd": " ".join(cmd),
            "exit_code": proc.returncode,
            "passed": proc.returncode == 0,
            "output": (proc.stdout + proc.stderr)[-500:],
        }
    except subprocess.TimeoutExpired:
        return {
            "name": name,
            "cwd": str(cwd),
            "cmd": " ".join(cmd),
            "exit_code": -1,
            "passed": False,
            "output": "TIMEOUT",
        }
    except Exception as exc:
        return {
            "name": name,
            "cwd": str(cwd),
            "cmd": " ".join(cmd),
            "exit_code": -2,
            "passed": False,
            "output": str(exc),
        }


def main() -> int:
    results = []
    
    print("=" * 60)
    print("Cross-project test matrix")
    print("=" * 60)
    
    for name, cwd, cmd, timeout in PYTHON_PROJECTS:
        print(f"\n[{name}] running: {' '.join(cmd)}")
        result = run_project(name, cwd, cmd, timeout=timeout)
        results.append(result)
        status = "PASS" if result["passed"] else "FAIL"
        print(f"[{name}] {status} (exit={result['exit_code']})")
        if not result["passed"]:
            print(result["output"][-200:])
    
    for name, cwd, cmd, timeout in TYPESCRIPT_PROJECTS:
        print(f"\n[{name}] running: {' '.join(cmd)}")
        result = run_project(name, cwd, cmd, timeout=timeout)
        results.append(result)
        status = "PASS" if result["passed"] else "FAIL"
        print(f"[{name}] {status} (exit={result['exit_code']})")
        if not result["passed"]:
            print(result["output"][-200:])
    
    passed = sum(1 for r in results if r["passed"])
    total = len(results)
    print("\n" + "=" * 60)
    print(f"Results: {passed}/{total} passed")
    print("=" * 60)
    
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
