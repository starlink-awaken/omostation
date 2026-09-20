#!/usr/bin/env python3
"""Unit tests for cross-repo-status.py.

Tests main_status() returns main + submodules, identifies checked-out
vs not-initialized submodules, and the alignment comparison.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "bin" / "mof" / "cross-repo-status.py"


def _load():
    spec = importlib.util.spec_from_file_location("cross_repo_status", SCRIPT)
    m = importlib.util.module_from_spec(spec)
    sys.modules["cross_repo_status"] = m
    spec.loader.exec_module(m)
    return m


def test_main_status_returns_main():
    m = _load()
    data = m.main_status()
    assert "main" in data
    main = data["main"]
    assert main["name"] == "omostation"
    assert isinstance(main["branch"], str) and len(main["branch"]) > 0
    assert len(main["head_sha"]) == 7
    assert "kind" in main


def test_main_status_has_submodules_list():
    m = _load()
    data = m.main_status()
    assert "submodules" in data
    assert isinstance(data["submodules"], list)
    assert data["total"] == len(data["submodules"])
    assert data["total"] >= 5  # workspace has at least 5 submodules


def test_checkout_status_consistency():
    """For each submodule in the list, checkout field matches reality."""
    m = _load()
    data = m.main_status()
    for s in data["submodules"]:
        if s["checkout"]:
            assert "branch" in s
            assert "head_sha" in s
            assert "head_matches_gitlink" in s
            assert isinstance(s["head_matches_gitlink"], bool)
        else:
            assert "reason" in s or s["checkout"] is False


def test_alignment_field_is_boolean():
    """head_matches_gitlink is boolean, even when checkout=False (omit)."""
    m = _load()
    data = m.main_status()
    for s in data["submodules"]:
        if s["checkout"]:
            assert isinstance(s["head_matches_gitlink"], bool)


def test_json_output_via_subprocess():
    """End-to-end: script --json returns valid JSON."""
    out = subprocess.run(
        [sys.executable, str(SCRIPT), "--json"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert out.returncode == 0, f"stderr: {out.stderr}"
    parsed = json.loads(out.stdout)
    assert "main" in parsed
    assert "submodules" in parsed
    assert parsed["total"] >= 5


def test_format_text_renders_table():
    m = _load()
    data = {
        "main": {
            "name": "omostation",
            "branch": "agent/test",
            "head_sha": "abc1234",
            "head_subject": "test commit",
            "dirty": False,
            "kind": "main",
        },
        "submodules": [
            {
                "name": "ecos",
                "path": "projects/ecos",
                "checkout": True,
                "branch": "main",
                "head_sha": "def5678",
                "head_subject": "ecos commit",
                "dirty": False,
                "gitlink_sha": "def5678",
                "head_matches_gitlink": True,
            },
            {
                "name": "omlxc",
                "path": "projects/omlxc",
                "checkout": False,
                "reason": "submodule not initialized",
            },
        ],
        "total": 2,
    }
    text = m.format_text(data)
    assert "omostation" in text
    assert "ecos" in text
    assert "omlxc" in text
    assert "YES" in text
    assert "NO" in text
    assert "✓" in text


if __name__ == "__main__":
    tests = [(name, obj) for name, obj in globals().items()
             if name.startswith("test_") and callable(obj)]
    failures = []
    for name, fn in tests:
        try:
            fn()
            print(f"  PASS {name}")
        except Exception as e:
            print(f"  FAIL {name}: {e}")
            failures.append((name, e))
    if failures:
        sys.exit(1)
    print(f"\n{len(tests)} tests passed")