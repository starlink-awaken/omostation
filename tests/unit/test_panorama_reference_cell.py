import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "bin/panorama/panorama-collect.py"


def _module():
    spec = importlib.util.spec_from_file_location("panorama_reference_cell_test", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_reference_cell_gate_projects_stale_evidence_fail_closed(tmp_path, monkeypatch) -> None:
    module = _module()
    code_root = tmp_path / "code"
    verifier = code_root / "bin/gac/reference-cell-dl-verify.py"
    verifier.parent.mkdir(parents=True)
    verifier.write_text("", encoding="utf-8")
    monkeypatch.setattr(module, "CODE_ROOT", code_root)

    payload = {
        "schema": "reference-cell-direct-local-r0-verification/v1",
        "verdict": "STALE",
        "reason": "evidence_stale",
        "latest_observed_at": "2026-09-09T07:57:16+00:00",
        "result": "PASS",
        "execution_backend": "local",
        "workspace_writes": 0,
    }

    def fake_run(command, **kwargs):
        assert command[1] == str(verifier)
        return type("Completed", (), {"stdout": json.dumps(payload)})()

    monkeypatch.setattr(module.subprocess, "run", fake_run)
    gate = module.collect_reference_cell_gate()

    assert gate["id"] == "RC-DL"
    assert gate["verdict"] == "STALE"
    assert gate["live"] is False
    assert "evidence_stale" not in gate["detail"]
    assert "2026-09-09" in gate["detail"]


def test_reference_cell_gate_fails_closed_on_missing_verifier(tmp_path, monkeypatch) -> None:
    module = _module()
    monkeypatch.setattr(module, "CODE_ROOT", tmp_path)
    gate = module.collect_reference_cell_gate()
    assert gate["verdict"] == "UNAVAILABLE"
    assert gate["live"] is False
