import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "bin/panorama/panorama-collect.py"


def _module():
    spec = importlib.util.spec_from_file_location("panorama_claims_task16_test", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_claims_task16_projection_parses_readonly_preflight(tmp_path, monkeypatch) -> None:
    module = _module()
    runtime_root = tmp_path / "runtime"
    code_root = tmp_path / "code"
    script = code_root / "bin/gac/claims-shadow-preflight.py"
    script.parent.mkdir(parents=True)
    script.write_text("", encoding="utf-8")
    monkeypatch.setattr(module, "ROOT", runtime_root)
    monkeypatch.setattr(module, "CODE_ROOT", code_root)

    def fake_run(command, **kwargs):
        assert command[1] == str(script)
        assert command[2] == "--json"
        assert command[3] == "--integration-root"
        assert command[4] in {str(runtime_root), str(code_root)}
        assert kwargs["cwd"] == runtime_root
        return type("Completed", (), {"stdout": json.dumps({
            "schema": "claims-shadow-preflight/v1",
            "available": True,
            "readiness": "BLOCKED",
            "activation_allowed": False,
            "hard_blockers": [],
            "blockers": ["root_head_not_equal_origin_main"],
        })})()

    monkeypatch.setattr(module.subprocess, "run", fake_run)
    report = module.collect_claims_task16_preflight()
    print(report)

    assert report["available"] is True
    assert report["verdict"] == "BLOCKED"
    assert report["activation_allowed"] is False
    assert report["blocker_count"] == 1
    assert report["preflight"]["blockers"] == ["root_head_not_equal_origin_main"]
    assert report["isolated_preflight"]["preflight"]["blockers"] == [
        "root_head_not_equal_origin_main"
    ]
    assert report["isolated_technical_ready"] is False

    assert report["isolated_preflight"]["preflight"]["blockers"] == [
        "root_head_not_equal_origin_main"
    ]
    assert report["isolated_technical_ready"] is False


def test_claims_task16_projection_fails_closed_on_invalid_payload(tmp_path, monkeypatch) -> None:
    module = _module()
    code_root = tmp_path / "code"
    script = code_root / "bin/gac/claims-shadow-preflight.py"
    script.parent.mkdir(parents=True)
    script.write_text("", encoding="utf-8")
    monkeypatch.setattr(module, "ROOT", tmp_path / "runtime")
    monkeypatch.setattr(module, "CODE_ROOT", code_root)
    monkeypatch.setattr(
        module.subprocess,
        "run",
        lambda command, **kwargs: type("Completed", (), {"stdout": "not-json"})(),
    )

    report = module.collect_claims_task16_preflight()

    assert report["available"] is False
    assert report["verdict"] == "UNAVAILABLE"
    assert report["canonical_error"] == "JSONDecodeError"
    assert report["isolated_error"] == "JSONDecodeError"
    assert report["isolated_preflight"]["available"] is False
