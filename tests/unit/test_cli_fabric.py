"""Unit tests for omlxc fabric CLI commands."""

from __future__ import annotations

import json

from typer.testing import CliRunner

from omlxc.cli import app

runner = CliRunner()


def test_cli_fabric_inspect_json() -> None:
    result = runner.invoke(app, ["fabric", "inspect", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["schema_version"] == "1"
    assert "thermal_pressure" in payload["data"]
    assert "known_arch_profiles" in payload["data"]
    assert "coding" in payload["data"]["known_arch_profiles"]


def test_cli_fabric_inspect_human() -> None:
    result = runner.invoke(app, ["fabric", "inspect"])
    assert result.exit_code == 0
    assert "omlxc Compute Fabric" in result.stdout
    assert "Thermal Guard" in result.stdout
    assert "Semantic Triage" in result.stdout


def test_cli_fabric_triage_json() -> None:
    result = runner.invoke(
        app,
        ["fabric", "triage", "Design a lock-free queue to prevent ABA problem", "--json"],
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["data"]["tier"] == "reasoning"
    assert payload["data"]["confidence"] >= 0.8


def test_cli_fabric_vram_json() -> None:
    result = runner.invoke(app, ["fabric", "vram", "coding", "32768", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["data"]["model_id"] == "coding"
    assert payload["data"]["context_tokens"] == 32768
    assert payload["data"]["kv_cache_mb"] > 8000.0


def test_cli_fabric_warm_json() -> None:
    result = runner.invoke(app, ["fabric", "warm", "--model", "coding", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["data"]["model_id"] == "coding"
    assert payload["data"]["warmed_count"] >= 3
    assert payload["data"]["estimated_saved_tokens"] > 0


def test_cli_fabric_compact_json() -> None:
    # 32k tokens on 4GB node -> compaction advised
    result = runner.invoke(
        app,
        [
            "fabric",
            "compact",
            "--model",
            "coding",
            "--tokens",
            "32768",
            "--available-mb",
            "4096",
            "--json",
        ],
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["data"]["model_id"] == "coding"
    assert payload["data"]["compaction_advised"] is True
    assert payload["data"]["pruned_tokens"] > 0
    assert payload["data"]["compression_ratio"] > 0.0


def test_cli_fabric_compact_human() -> None:
    result = runner.invoke(
        app,
        ["fabric", "compact", "--model", "coding", "--tokens", "32768", "--available-mb", "4096"],
    )
    assert result.exit_code == 0
    assert "Context Window Compactor" in result.stdout
    assert "Compaction Advised" in result.stdout



def test_cli_fabric_warm_human() -> None:
    result = runner.invoke(app, ["fabric", "warm"])
    assert result.exit_code == 0
    assert "System Prefix Warmer" in result.stdout
    assert "Prefix Cache Ready" in result.stdout
