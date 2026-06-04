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


def _seed_cc_switch_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    cur = conn.cursor()
    cur.executescript(
        """
        CREATE TABLE providers (
            id TEXT PRIMARY KEY,
            app_type TEXT,
            name TEXT,
            settings_config TEXT,
            website_url TEXT,
            category TEXT,
            created_at INTEGER,
            sort_index INTEGER,
            notes TEXT,
            icon TEXT,
            icon_color TEXT,
            meta TEXT,
            is_current INTEGER,
            in_failover_queue INTEGER,
            cost_multiplier TEXT,
            limit_daily_usd REAL,
            limit_monthly_usd REAL,
            provider_type TEXT
        );
        CREATE TABLE provider_endpoints (
            id INTEGER PRIMARY KEY,
            provider_id TEXT,
            app_type TEXT,
            url TEXT,
            added_at INTEGER
        );
        CREATE TABLE provider_health (
            provider_id TEXT,
            app_type TEXT,
            is_healthy INTEGER,
            consecutive_failures INTEGER,
            last_success_at TEXT,
            last_failure_at TEXT,
            last_error TEXT,
            updated_at TEXT
        );
        """
    )
    cur.execute(
        """
        INSERT INTO providers (
            id, app_type, name, settings_config, website_url, category, created_at, sort_index,
            notes, icon, icon_color, meta, is_current, in_failover_queue, cost_multiplier,
            limit_daily_usd, limit_monthly_usd, provider_type
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "healthy-deepseek",
            "claude",
            "DeepSeek",
            '{"env":{"ANTHROPIC_AUTH_TOKEN":"secret-token","ANTHROPIC_BASE_URL":"https://api.deepseek.com/anthropic","ANTHROPIC_MODEL":"DeepSeek-V4-pro"}}',
            "https://platform.deepseek.com",
            "cn_official",
            0,
            1,
            "healthy",
            "deepseek",
            "#000000",
            "{}",
            1,
            0,
            "1.0",
            None,
            None,
            None,
        ),
    )
    cur.execute(
        "INSERT INTO provider_endpoints (provider_id, app_type, url, added_at) VALUES (?, ?, ?, ?)",
        ("healthy-deepseek", "claude", "https://api.deepseek.com/anthropic", 0),
    )
    cur.execute(
        """
        INSERT INTO provider_health (
            provider_id, app_type, is_healthy, consecutive_failures, last_success_at, last_failure_at, last_error, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ("healthy-deepseek", "claude", 1, 0, "2026-05-30T10:00:00Z", None, None, "2026-05-30T10:00:00Z"),
    )
    cur.execute(
        """
        INSERT INTO providers (
            id, app_type, name, settings_config, website_url, category, created_at, sort_index,
            notes, icon, icon_color, meta, is_current, in_failover_queue, cost_multiplier,
            limit_daily_usd, limit_monthly_usd, provider_type
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "unhealthy-openrouter",
            "claude",
            "OpenRouter",
            '{"env":{"ANTHROPIC_AUTH_TOKEN":"bad-token","ANTHROPIC_BASE_URL":"https://openrouter.ai/api","ANTHROPIC_MODEL":"anthropic/claude-sonnet-4.6"}}',
            "https://openrouter.ai",
            "aggregator",
            0,
            2,
            "unhealthy",
            "openrouter",
            "#111111",
            "{}",
            0,
            0,
            "1.0",
            None,
            None,
            None,
        ),
    )
    cur.execute(
        "INSERT INTO provider_endpoints (provider_id, app_type, url, added_at) VALUES (?, ?, ?, ?)",
        ("unhealthy-openrouter", "claude", "https://openrouter.ai/api", 0),
    )
    cur.execute(
        """
        INSERT INTO provider_health (
            provider_id, app_type, is_healthy, consecutive_failures, last_success_at, last_failure_at, last_error, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ("unhealthy-openrouter", "claude", 0, 4, None, "2026-05-29T10:00:00Z", "401", "2026-05-29T10:00:00Z"),
    )
    conn.commit()
    conn.close()


def test_select_cc_switch_provider_prefers_healthy_entry_and_extracts_runtime(tmp_path: Path) -> None:
    db_path = tmp_path / "cc-switch.db"
    _seed_cc_switch_db(db_path)

    provider = select_cc_switch_provider(db_path, app_type="claude")

    assert provider.name == "DeepSeek"
    assert provider.base_url == "https://api.deepseek.com/anthropic"
    assert provider.api_key == "secret-token"
    assert provider.model == "DeepSeek-V4-pro"
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
    db_path = tmp_path / "cc-switch.db"
    _seed_cc_switch_db(db_path)
    provider = select_cc_switch_provider(db_path, app_type="claude")

    apply_provider_to_litellm_config(config_path, target_model_name="claude-3-5-sonnet", provider=provider)

    data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    assert data["model_list"][0]["litellm_params"] == {"model": "openai/gpt-4o", "api_key": "os.environ/OPENAI_API_KEY"}
    assert data["model_list"][1]["litellm_params"]["api_key"] == "secret-token"
    assert data["model_list"][1]["litellm_params"]["api_base"] == "https://api.deepseek.com/anthropic"
    assert data["model_list"][1]["litellm_params"]["model"] == "anthropic/DeepSeek-V4-pro"


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


def test_agentmesh_gateway_config_prefers_local_litellm_for_claude_routes() -> None:
    config = yaml.safe_load((_WORKSPACE / "projects" / "agentmesh" / "config" / "gateway.yaml").read_text(encoding="utf-8"))
    models = config["models"]

    assert "litellm" in models["providers"]
    assert models["providers"]["litellm"]["base_url"] == "http://127.0.0.1:4000/v1"
    assert models["model_routing"]["claude"][0] == "litellm"
