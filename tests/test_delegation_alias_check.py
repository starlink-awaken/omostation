from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "bin" / "delegation-alias-check.py"
SPEC = importlib.util.spec_from_file_location("delegation_alias_check", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
ALIASES = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ALIASES)


def test_compare_normalizes_prefixes_deduplicates_and_ignores_blank_values() -> None:
    result = ALIASES.compare(
        [" coder ", "coder", ""],
        ["lmstudio/coder", "  ", "lmstudio/spare"],
    )

    assert result == {
        "IN_OPENCODE_ONLY": [],
        "IN_LITELLM_ONLY": ["spare"],
        "IN_BOTH": ["coder"],
    }


def test_unused_gateway_capacity_is_diagnostic_not_a_routing_failure() -> None:
    result = {
        "IN_OPENCODE_ONLY": [],
        "IN_LITELLM_ONLY": ["spare"],
        "IN_BOTH": ["coder"],
    }

    assert ALIASES.drift_detected(result) is False


def test_missing_gateway_route_remains_blocking() -> None:
    result = {
        "IN_OPENCODE_ONLY": ["coding"],
        "IN_LITELLM_ONLY": [],
        "IN_BOTH": ["coder"],
    }

    assert ALIASES.drift_detected(result) is True


def test_cli_reports_unsynced_but_route_safe_for_unused_capacity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    opencode = tmp_path / "opencode.json"
    litellm = tmp_path / "litellm.yaml"
    opencode.write_text(json.dumps({"provider": {"omlxc": {"models": {"coder": {}}}}}))
    litellm.write_text(
        "model_list:\n"
        "  - model_name: lmstudio/coder\n"
        "  - model_name: lmstudio/spare\n"
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            str(SCRIPT),
            "--json",
            "--opencode-config",
            str(opencode),
            "--litellm-config",
            str(litellm),
        ],
    )

    exit_code = ALIASES.main()
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["synced"] is False
    assert payload["route_safe"] is True
    assert payload["IN_LITELLM_ONLY"] == ["spare"]


def test_cli_blocks_when_an_opencode_route_is_missing_from_gateway(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    opencode = tmp_path / "opencode.json"
    litellm = tmp_path / "litellm.yaml"
    opencode.write_text(json.dumps({"provider": {"omlxc": {"models": {"coding": {}}}}}))
    litellm.write_text("model_list:\n  - model_name: lmstudio/coder\n")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            str(SCRIPT),
            "--json",
            "--opencode-config",
            str(opencode),
            "--litellm-config",
            str(litellm),
        ],
    )

    exit_code = ALIASES.main()
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 1
    assert payload["synced"] is False
    assert payload["route_safe"] is False
    assert payload["IN_OPENCODE_ONLY"] == ["coding"]
