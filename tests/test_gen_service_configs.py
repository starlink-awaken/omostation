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


def test_stable_python_prefers_fixed_homebrew_path_over_uv_like_path(monkeypatch) -> None:
    module = _module()
    monkeypatch.setenv("PATH", "/usr/bin:/opt/homebrew/bin")
    monkeypatch.setattr(
        module.Path,
        "is_file",
        lambda path: str(path) == "/opt/homebrew/bin/python3",
    )

    assert module._stable_python3() == "/opt/homebrew/bin/python3"


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


# ── BET-Y1Q4-T16: cron 准入 ──


def test_cron_enabled_placeholder_entrypoint_rejected() -> None:
    """批次 18 回归: `projects/omo` 占位 entrypoint 且无 crontab_token 必须被拒。"""
    module = _module()

    violations = module.validate_service_declaration(
        {
            "id": "cron.new_thing",
            "enabled": True,
            "scheduler": "cron",
            "program": {"interpreter": "uv", "entrypoint": "projects/omo"},
        }
    )

    assert len(violations) == 1
    assert "cron 准入失败" in violations[0]


def test_cron_enabled_omostation_word_boundary_not_matched_by_omo() -> None:
    """批次 18 回归: entrypoint basename `omostation-xxx` 不得被 id 尾段 `omo` 子串误命中。"""
    module = _module()

    violations = module.validate_service_declaration(
        {
            "id": "cron.omo",
            "enabled": True,
            "scheduler": "cron",
            "program": {"interpreter": "bash", "entrypoint": "bin/omostation-helper.sh"},
        }
    )

    assert len(violations) == 1
    assert "cron 准入失败" in violations[0]


def test_cron_enabled_explicit_crontab_token_passes() -> None:
    """显式 crontab_token 即放行 (现实性由 ops check-signals 对本机 crontab 核验)。"""
    module = _module()

    violations = module.validate_service_declaration(
        {
            "id": "cron.ssot_guardian",
            "enabled": True,
            "scheduler": "cron",
            "program": {"interpreter": "uv", "entrypoint": "projects/omo"},
            "crontab_token": "ssot-guardian",
        }
    )

    assert violations == []


def test_cron_enabled_entrypoint_basename_tail_match_passes() -> None:
    """entrypoint basename 词边界命中 id 尾段 (含下划线->连字符变体) 即放行。"""
    module = _module()

    assert (
        module.validate_service_declaration(
            {
                "id": "cron.log_rotate",
                "enabled": True,
                "scheduler": "cron",
                "program": {"interpreter": "python3", "entrypoint": "bin/ssot/log-rotate.py"},
            }
        )
        == []
    )


def test_cron_disabled_placeholder_grandfathered() -> None:
    """存量 disabled 占位条目不报错 (只拦新增/再激活)。"""
    module = _module()

    violations = module.validate_service_declaration(
        {
            "id": "cron.debt_refresh",
            "enabled": False,
            "scheduler": "cron",
            "program": {"interpreter": "uv", "entrypoint": "projects/omo"},
        }
    )

    assert violations == []


def test_cron_enabled_missing_entrypoint_rejected() -> None:
    module = _module()

    violations = module.validate_service_declaration(
        {"id": "cron.bare", "enabled": True, "scheduler": "cron"}
    )

    assert len(violations) == 1
    assert "requires program.entrypoint" in violations[0]
