"""Task 3 CLI contracts for validation and migration."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from typer.testing import CliRunner

import omlxc.cli as cli_module
from omlxc.cli import app
from omlxc.config import write_config_atomic

runner = CliRunner()


def _legacy_source(path: Path) -> Path:
    models = {
        "model-a": {
            "alias": "/models/model-a",
            "category": "general",
            "engine": "mlx_lm",
            "params": {"max_tokens": 4096},
            "port": 8100,
            "reasoning": False,
            "role": "chat",
            "size_gb": 4.0,
        }
    }
    payload = {
        "version": 2,
        "host": "node-a.example.invalid",
        "omlx_app": {
            "base_url": "https://node-a.example.invalid:8000",
            "request_defaults": {"thinking_budget": 0},
        },
        "defaults": {"max_tokens": 4096},
        "models": models,
        "cluster": {
            "nodes": [
                {
                    "name": "Node A",
                    "role": "local",
                    "host": "node-a.example.invalid",
                    "probe": {"ollama": 11434},
                }
            ]
        },
        "autopilot": {
            "mem_free_pct_floor": 20.0,
            "resident": ["model-a"],
            "remote_resident": [],
        },
        "fallback": {"model-a": "fallback-a"},
        "fallback_ollama": {"model-a": "ollama-a"},
        "presets": {"fast": ["model-a"]},
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_config_validate_emits_success_envelope(tmp_path: Path) -> None:
    config = tmp_path / "config.toml"
    config.write_text(
        f"""
schema_version = 1

[daemon]
socket_path = "{tmp_path / "omlxcd.sock"}"

[storage]
database_path = "{tmp_path / "state.db"}"
""".strip(),
        encoding="utf-8",
    )

    result = runner.invoke(app, ["config", "validate", "--path", str(config), "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["schema_version"] == "1"
    assert payload["request_id"]
    assert payload["data"] == {
        "config_schema_version": 1,
        "status": "valid",
    }


def test_config_validate_emits_sanitized_structured_error(tmp_path: Path) -> None:
    config = tmp_path / "config.toml"
    config.write_text(
        'schema_version = 1\nsecret = "must-not-leak"\n',
        encoding="utf-8",
    )

    result = runner.invoke(app, ["config", "validate", "--path", str(config), "--json"])

    assert result.exit_code == 2
    assert result.stdout == ""
    payload = json.loads(result.stderr)
    assert payload["schema_version"] == "1"
    assert payload["request_id"]
    assert payload["error"]["code"] == "E100"
    assert "must-not-leak" not in result.stderr


def test_config_validate_credential_policy_error_does_not_leak_input(tmp_path: Path) -> None:
    plaintext = "synthetic-cli-credential-plaintext"
    config = tmp_path / "config.toml"
    config.write_text(
        f"""
schema_version = 1

[policies.sampling_defaults]
apiKeys = "{plaintext}"
""".strip(),
        encoding="utf-8",
    )

    result = runner.invoke(app, ["config", "validate", "--path", str(config), "--json"])

    assert result.exit_code == 2
    assert result.stdout == ""
    payload = json.loads(result.stderr)
    assert payload["error"]["code"] == "E100"
    assert plaintext not in result.stderr


def test_config_migrate_defaults_to_summary_plan_without_writing(tmp_path: Path) -> None:
    source = _legacy_source(tmp_path / "models.json")
    target = tmp_path / "config.toml"

    result = runner.invoke(
        app,
        ["config", "migrate", "--from", str(source), "--target", str(target)],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["schema_version"] == "1"
    assert payload["request_id"]
    assert payload["data"]["model_count"] == 1
    assert payload["data"]["node_count"] == 1
    assert payload["data"]["will_write"] is False
    assert "example.invalid" not in result.stdout
    assert "/models/" not in result.stdout
    assert not target.exists()


def test_config_migrate_apply_requires_yes_before_read_or_write(tmp_path: Path) -> None:
    target = tmp_path / "config.toml"

    result = runner.invoke(
        app,
        [
            "config",
            "migrate",
            "--from",
            str(tmp_path / "missing.json"),
            "--target",
            str(target),
            "--apply",
        ],
    )

    assert result.exit_code == 2
    payload = json.loads(result.stderr)
    assert payload["error"]["code"] == "E100"
    assert not target.exists()


def test_config_migrate_apply_writes_private_target_and_snapshot(tmp_path: Path) -> None:
    source = _legacy_source(tmp_path / "models.json")
    target = tmp_path / "config.toml"

    first = runner.invoke(
        app,
        [
            "config",
            "migrate",
            "--from",
            str(source),
            "--target",
            str(target),
            "--apply",
            "--yes",
        ],
    )
    original = target.read_bytes()
    second = runner.invoke(
        app,
        [
            "config",
            "migrate",
            "--from",
            str(source),
            "--target",
            str(target),
            "--apply",
            "--yes",
        ],
    )

    assert first.exit_code == second.exit_code == 0
    assert target.stat().st_mode & 0o777 == 0o600
    snapshots = list(tmp_path.glob("config.toml.snapshot-*"))
    assert len(snapshots) == 1
    assert snapshots[0].read_bytes() == original
    assert snapshots[0].stat().st_mode & 0o777 == 0o600
    payload = json.loads(second.stdout)
    assert payload["data"]["will_write"] is True
    assert payload["data"]["snapshot_created"] is True


def test_config_migrate_cli_reports_replace_failure_without_damaging_target(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = _legacy_source(tmp_path / "models.json")
    target = tmp_path / "config.toml"
    target.write_text("original", encoding="utf-8")

    def injected_writer(path: Path, content: str) -> object:
        def fail_replace(
            _source: str | bytes | os.PathLike[str] | os.PathLike[bytes],
            _target: str | bytes | os.PathLike[str] | os.PathLike[bytes],
        ) -> None:
            raise OSError("injected replace failure")

        return write_config_atomic(path, content, replace=fail_replace)

    monkeypatch.setattr(cli_module, "write_config_atomic", injected_writer)

    result = runner.invoke(
        app,
        [
            "config",
            "migrate",
            "--from",
            str(source),
            "--target",
            str(target),
            "--apply",
            "--yes",
        ],
    )

    assert result.exit_code == 2
    assert json.loads(result.stderr)["error"]["code"] == "E100"
    assert target.read_text(encoding="utf-8") == "original"
    assert list(tmp_path.glob(".config.toml.*.tmp")) == []
