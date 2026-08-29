from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_evidence_smoke():
    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location("evidence_smoke_under_test", root / "bin/gac/evidence-smoke.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_stdio_script_is_resolved_relative_to_declared_directory(tmp_path, monkeypatch):
    module = _load_evidence_smoke()
    monkeypatch.setattr(module, "WORKSPACE", tmp_path)
    script = tmp_path / "projects/omlxc/examples/live.py"
    script.parent.mkdir(parents=True)
    script.write_text("print('ok')\n", encoding="utf-8")

    ok, reason = module._check_stdio(
        ["uv", "run", "--directory", "projects/omlxc", "python", "examples/live.py"]
    )

    assert (ok, reason) == (True, "ok (script)")


def test_stdio_missing_script_fails_closed_below_declared_directory(tmp_path, monkeypatch):
    module = _load_evidence_smoke()
    monkeypatch.setattr(module, "WORKSPACE", tmp_path)
    (tmp_path / "projects/omlxc").mkdir(parents=True)

    ok, reason = module._check_stdio(
        ["uv", "run", "--directory", "projects/omlxc", "python", "examples/missing.py"]
    )

    assert ok is False
    assert reason == "script not found: examples/missing.py"


def test_stdio_script_without_directory_remains_workspace_relative(tmp_path, monkeypatch):
    module = _load_evidence_smoke()
    monkeypatch.setattr(module, "WORKSPACE", tmp_path)
    script = tmp_path / "scripts/live.py"
    script.parent.mkdir(parents=True)
    script.write_text("print('ok')\n", encoding="utf-8")

    ok, reason = module._check_stdio(["python", "scripts/live.py"])

    assert (ok, reason) == (True, "ok (script)")
