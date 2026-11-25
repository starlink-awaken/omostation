"""`check-work-landed` 在 runs 目录缺席时必须自报「没测成」。

`.omo/_delivery/agent-workflows/runs/` 是 gitignore 面 —— CI 的干净检出里不存在。
旧实现在那里返回 `ok: true, summary.closed=0`，与「扫了 170+ 个 run 且全部已落地」
同形（空绿）：本机它真的在查每个 claimed ref 有没有落地，CI 永远看不到读数。
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[3] / "bin" / "gac" / "check-work-landed.py"


@pytest.fixture(scope="module")
def mod():
    spec = importlib.util.spec_from_file_location("check_work_landed_nm", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_absent_runs_dir_declares_not_measured(mod, monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(mod, "RUNS_DIR", tmp_path / "absent-runs")
    rc = mod.main(["--json"])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0, "缺输入不是仓库缺陷，不该阻断"
    assert out["measured"] is False
    assert out["reason"] == "no_runs_dir"


def test_present_runs_dir_is_measured(mod, monkeypatch, tmp_path, capsys):
    """目录在 ⇒ 必须算测过（反向判据：不是恒 `measured: false`）。"""
    runs = tmp_path / "runs"
    runs.mkdir()
    monkeypatch.setattr(mod, "RUNS_DIR", runs)

    rc = mod.main(["--json"])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert out["measured"] is True
    assert out["summary"]["closed"] == 0
