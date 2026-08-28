from __future__ import annotations

import importlib.util
import json
from pathlib import Path

MODULE_PATH = Path(__file__).parents[1] / "bin" / "mof" / "gen-service-configs.py"


def _module():
    spec = importlib.util.spec_from_file_location("service_configs_under_test", MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_lifecycle_only_launchd_record_does_not_require_generated_plist_fields() -> None:
    module = _module()

    violations = module.validate_service_declaration(
        {
            "id": "omo.governor",
            "enabled": True,
            "scheduler": "launchd",
            "generate": False,
        }
    )

    assert violations == []


def test_generated_launchd_record_requires_label_and_program() -> None:
    module = _module()

    violations = module.validate_service_declaration(
        {
            "id": "broken.generated",
            "enabled": True,
            "scheduler": "launchd",
        }
    )

    assert "broken.generated: launchd generator requires label" in violations
    assert "broken.generated: launchd generator requires program.interpreter" in violations
    assert "broken.generated: launchd generator requires program.entrypoint" in violations


def test_check_skips_byte_comparison_when_host_observer_is_unavailable(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    module = _module()
    monkeypatch.setattr(module, "_launchd_dir", lambda: tmp_path / "missing-launchagents")
    monkeypatch.setattr(
        module,
        "load_services",
        lambda: [
            {
                "id": "generated.valid",
                "enabled": True,
                "scheduler": "launchd",
                "label": "com.example.valid",
                "program": {
                    "interpreter": "stable-python3",
                    "entrypoint": "bin/example.py",
                },
            }
        ],
    )
    monkeypatch.setattr(module.sys, "argv", ["gen-service-configs.py", "--check", "--json"])

    assert module.main() == 0
    assert json.loads(capsys.readouterr().out) == {
        "ok": True,
        "skipped": True,
        "reason": "launchd_observer_unavailable",
        "validation_errors": [],
    }


def test_observer_unavailable_does_not_mask_malformed_declarations(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    """spec Verification 3: observer 缺失只 skip 字节比对, 缺 label 的
    generate 声明仍必须 fail validation (skip 不是逃生门)."""
    module = _module()
    monkeypatch.setattr(module, "_launchd_dir", lambda: tmp_path / "missing-launchagents")
    monkeypatch.setattr(
        module,
        "load_services",
        lambda: [
            {
                "id": "broken.missing_label",
                "enabled": True,
                "scheduler": "launchd",
            }
        ],
    )
    monkeypatch.setattr(module.sys, "argv", ["gen-service-configs.py", "--check", "--json"])

    assert module.main() == 1
    report = json.loads(capsys.readouterr().out)
    assert report["skipped"] is True
    assert report["ok"] is False
    assert report["reason"] == "launchd_observer_unavailable"
    assert any("requires label" in e for e in report["validation_errors"])
