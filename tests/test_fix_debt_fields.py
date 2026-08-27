import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

WORKSPACE = Path(__file__).resolve().parents[1]


def _run_fix_debt_fields(*args: str) -> subprocess.CompletedProcess[str]:
    env = {k: v for k, v in os.environ.items() if k != "VIRTUAL_ENV"}
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(
        ["uv", "run", "--with", "pyyaml", "python", str(WORKSPACE / "bin/gac/fix-debt-fields.py"), *args],
        cwd=WORKSPACE,
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )


def test_debt_field_conflict_detection(tmp_path: Path):
    """debt YAML 字段冲突应被检测到"""
    debt_dir = tmp_path / ".omo/debt/items"
    debt_dir.mkdir(parents=True)
    conflict_file = debt_dir / "TEST-CONFLICT.yaml"
    conflict_file.write_text(
        "id: TEST-CONFLICT\nlifecycle_state: open\nstatus: closed\n", encoding="utf-8"
    )
    result = _run_fix_debt_fields("--dry-run", "--root", str(tmp_path))
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["conflict_count"] >= 1
    assert any(item["id"] == "TEST-CONFLICT" for item in report["conflicts"])


def test_debt_field_fix_removes_status(tmp_path: Path):
    """--apply 应删除 deprecated status 字段"""
    debt_dir = tmp_path / ".omo/debt/items"
    debt_dir.mkdir(parents=True)
    conflict_file = debt_dir / "TEST-CONFLICT.yaml"
    conflict_file.write_text(
        "id: TEST-CONFLICT\nlifecycle_state: open\nstatus: closed\n", encoding="utf-8"
    )
    result = _run_fix_debt_fields("--apply", "--root", str(tmp_path))
    assert result.returncode == 0, result.stderr
    content = conflict_file.read_text(encoding="utf-8")
    assert "status:" not in content
    assert "lifecycle_state: open" in content
