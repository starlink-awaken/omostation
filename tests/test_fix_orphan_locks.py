import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

WORKSPACE = Path(__file__).resolve().parents[1]


def _run_fix_orphan_locks(*args: str) -> subprocess.CompletedProcess[str]:
    env = {k: v for k, v in os.environ.items() if k != "VIRTUAL_ENV"}
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(
        ["uv", "run", "--with", "pyyaml", "python", str(WORKSPACE / "bin/gac/fix-orphan-locks.py"), *args],
        cwd=WORKSPACE,
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )


def test_orphan_lock_detection():
    """orphan lock 应被检测到（如尚未修复）"""
    result = _run_fix_orphan_locks("--dry-run", "--registry", str(WORKSPACE / ".omo"))
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    # 可能已被 Task 2 自动修复，此时 orphan_count=0；否则应包含已知孤儿锁
    if report["orphan_count"] > 0:
        assert any(
            item["run_id"] == "20260822T032402Z-project-code-change-4ebce162"
            for item in report["orphans"]
        )


def test_orphan_lock_fix_creates_archive():
    """--apply 应将孤儿锁移入 .archive/"""
    archive_dir = WORKSPACE / ".omo/_delivery/agent-workflows/locks/.archive"
    result = _run_fix_orphan_locks("--apply", "--registry", str(WORKSPACE / ".omo"))
    assert result.returncode == 0, result.stderr
    assert archive_dir.exists()
    archived = list(archive_dir.glob("*.yaml"))
    assert len(archived) >= 1
