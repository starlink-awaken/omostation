"""check-evidence-honest-closure 在 runs 目录缺席时必须自报「没测成」。

`.omo/_delivery/agent-workflows/runs/` 是 gitignore 面 —— CI 的干净检出里不存在。
旧实现在那里返回 `ok: true`「no runs directory」，等于对这个检查无条件放行（空绿）：
本机有 runs 时它真的在查「关闭的 run 有没有留 evidence」，CI 却永远看不到读数。
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

SCRIPT = (
    Path(__file__).resolve().parents[3] / "bin" / "gac" / "check-evidence-honest-closure.py"
)


@pytest.fixture(scope="module")
def mod():
    spec = importlib.util.spec_from_file_location("check_evidence_honest_closure_nm", SCRIPT)
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
    runs = tmp_path / "runs"
    runs.mkdir()
    (runs / "run-closed.yaml").write_text(
        "run_id: r1\nstatus: closed\nevidence:\n  - .omo/some-evidence.json\n",
        encoding="utf-8",
    )
    (runs / "run-active.yaml").write_text("run_id: r2\nstatus: active\n", encoding="utf-8")
    monkeypatch.setattr(mod, "RUNS_DIR", runs)

    rc = mod.main(["--json"])
    out = json.loads(capsys.readouterr().out)
    assert rc in (0, 1)
    assert out["measured"] is True
    assert out["summary"]["runs_checked"] == 1
