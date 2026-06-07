from __future__ import annotations

import sqlite3
from pathlib import Path

import yaml

from omo.omo_provider_plane import (
    apply_provider_to_litellm_config,
    select_cc_switch_provider,
    summarize_codexbar_usage,
    write_provider_plane_snapshot,
)

_WORKSPACE = Path(__file__).resolve().parents[2]


import os
from unittest.mock import patch

def _seed_m1_dir(tmp_path: Path) -> Path:
    m1_dir = tmp_path / "m1" / "compute_engine"
    m1_dir.mkdir(parents=True)
    (m1_dir / "ENG-DEEPSEEK.yaml").write_text(
        """
id: ENG-DEEPSEEK
type: compute_engine
engine_type: cloud_api
base_url: "https://api.deepseek.com/anthropic"
supported_protocols: ["openai", "anthropic"]
cost_multiplier: 1.0
status: active
        """
    )
    return m1_dir


def test_select_cc_switch_provider_prefers_healthy_entry_and_extracts_runtime(tmp_path: Path) -> None:
    m1_dir = _seed_m1_dir(tmp_path)

    with patch.dict(os.environ, {"ANTHROPIC_AUTH_TOKEN": "secret-token"}):
        provider = select_cc_switch_provider(m1_dir=m1_dir, app_type="claude")

        assert provider.name == "ENG-DEEPSEEK"
        assert provider.base_url == "https://api.deepseek.com/anthropic"
        assert provider.api_key == "secret-token"
        assert provider.model == "gpt-4o"
        assert provider.is_healthy is True


def test_apply_provider_to_litellm_config_updates_target_model_only(tmp_path: Path) -> None:
    config_path = tmp_path / "litellm_config.yaml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "model_list": [
                    {
                        "model_name": "gpt-4o",
                        "litellm_params": {"model": "openai/gpt-4o", "api_key": "os.environ/OPENAI_API_KEY"},
                    },
                    {
                        "model_name": "claude-3-5-sonnet",
                        "litellm_params": {"model": "anthropic/claude-3-5-sonnet-20241022", "api_key": "os.environ/ANTHROPIC_API_KEY"},
                    },
                ]
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    m1_dir = _seed_m1_dir(tmp_path)
    with patch.dict(os.environ, {"ANTHROPIC_AUTH_TOKEN": "secret-token"}):
        provider = select_cc_switch_provider(m1_dir=m1_dir, app_type="claude")

    apply_provider_to_litellm_config(config_path, target_model_name="claude-3-5-sonnet", provider=provider)

    data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    assert data["model_list"][0]["litellm_params"] == {"model": "openai/gpt-4o", "api_key": "os.environ/OPENAI_API_KEY"}
    assert data["model_list"][1]["litellm_params"]["api_key"] == "secret-token"
    assert data["model_list"][1]["litellm_params"]["api_base"] == "https://api.deepseek.com/anthropic"
    assert data["model_list"][1]["litellm_params"]["model"] == "anthropic/gpt-4o"


def test_quota_summary_and_snapshot_redact_sensitive_fields(tmp_path: Path) -> None:
    quota_summary = summarize_codexbar_usage(
        """
        [
          {"provider":"codex","credits":{"remaining":25},"usage":{"secondary":{"usedPercent":12}}},
          {"provider":"openrouter","usage":{"openRouterUsage":{"balance":8.5,"usedPercent":31}}},
          {"provider":"openai","error":{"message":"key missing"}}
        ]
        """
    )
    snapshot_path = tmp_path / "provider-plane.yaml"

    write_provider_plane_snapshot(
        snapshot_path,
        selected_provider={
            "app_type": "claude",
            "provider_name": "DeepSeek",
            "base_url": "https://api.deepseek.com/anthropic",
            "model": "DeepSeek-V4-pro",
            "source": "cc-switch",
        },
        quota_summary=quota_summary,
        litellm_health={"healthy_count": 1, "unhealthy_count": 0},
    )

    snapshot = yaml.safe_load(snapshot_path.read_text(encoding="utf-8"))
    assert snapshot["selected_provider"]["provider_name"] == "DeepSeek"
    assert "api_key" not in snapshot["selected_provider"]
    assert snapshot["quota_summary"]["providers"]["codex"]["available"] is True
    assert snapshot["quota_summary"]["providers"]["openrouter"]["balance"] == 8.5
    assert snapshot["litellm_health"]["healthy_count"] == 1


def test_provider_snapshot_summarizes_litellm_health(tmp_path: Path) -> None:
    snapshot_path = tmp_path / "provider-plane.yaml"

    write_provider_plane_snapshot(
        snapshot_path,
        selected_provider={
            "app_type": "claude",
            "provider_name": "DeepSeek",
            "base_url": "https://api.deepseek.com/anthropic",
            "model": "DeepSeek-V4-pro",
            "source": "cc-switch",
        },
        quota_summary={"provider_count": 0, "providers": {}},
        litellm_health={
            "healthy_count": 1,
            "unhealthy_count": 1,
            "healthy_endpoints": [
                {
                    "model": "anthropic/DeepSeek-V4-pro",
                    "api_base": "https://api.deepseek.com/anthropic",
                    "litellm_metadata": {"user_api_key": "should-not-leak"},
                }
            ],
            "unhealthy_endpoints": [
                {
                    "model": "openai/gpt-4o",
                    "error": "missing key",
                    "litellm_metadata": {"user_api_key": "should-not-leak"},
                }
            ],
        },
    )

    snapshot = yaml.safe_load(snapshot_path.read_text(encoding="utf-8"))
    assert snapshot["litellm_health"]["healthy_count"] == 1
    assert snapshot["litellm_health"]["unhealthy_count"] == 1
    assert snapshot["litellm_health"]["healthy_models"] == ["anthropic/DeepSeek-V4-pro"]
    assert snapshot["litellm_health"]["unhealthy_models"] == ["openai/gpt-4o"]
    assert "healthy_endpoints" not in snapshot["litellm_health"]
    assert "unhealthy_endpoints" not in snapshot["litellm_health"]
