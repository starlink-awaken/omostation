from __future__ import annotations

import importlib.util
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
