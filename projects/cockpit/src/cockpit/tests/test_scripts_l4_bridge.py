"""Tests for L4 bridge MCP tools — workspace_context, cards_status, cards_check, vault_search."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ── conftest helpers ────────────────────────────────────


@pytest.fixture
def _patch_da(monkeypatch):
    mock_da = MagicMock()
    monkeypatch.setattr("scripts.cockpit_mcp._da", mock_da)
    return mock_da


@pytest.fixture
def _mock_cards_dir(tmp_path, monkeypatch):
    cards_dir = tmp_path / "CARDS"
    cards_dir.mkdir()

    # Create a P0 debt card
    debt_dir = cards_dir / "debts"
    debt_dir.mkdir()
    (debt_dir / "DEBT-001.md").write_text(
        "---\nid: DEBT-001\ntype: debt\nstatus: in_progress\n"
        'title: 修复 cockpit MCP\npriority: P0\ndomain: meta\ncreated: 2026-06-06\ntags: []\n---\n\n# 修复 cockpit MCP\n'
    )

    # Create a closed card
    task_dir = cards_dir / "tasks"
    task_dir.mkdir()
    (task_dir / "TASK-old.md").write_text(
        "---\nid: TASK-old\ntype: task\nstatus: closed\n"
        'title: 旧任务\npriority: P1\ndomain: meta\ncreated: 2026-06-01\ntags: []\n---\n'
    )

    monkeypatch.setattr("scripts.cockpit_mcp._CARDS_DIR", cards_dir)
    return cards_dir


@pytest.fixture
def _mock_vault_dir(tmp_path, monkeypatch):
    vault_dir = tmp_path / "vault"
    vault_dir.mkdir()
    active_dir = vault_dir / "1-active"
    active_dir.mkdir(parents=True)
    (active_dir / "方法论.md").write_text("# 方法论\n\n使用 OMO MCP 工具管理任务。禁止直接操作 .omo 目录。")
    monkeypatch.setattr("scripts.cockpit_mcp._VAULT_DIR", vault_dir)
    return vault_dir


@pytest.fixture
def _mock_omo(monkeypatch):
    monkeypatch.setattr(
        "scripts.cockpit_mcp._read_omo_goals",
        lambda: {"phase": 28, "theme": "测试", "status": "active", "goals": []},
    )
    monkeypatch.setattr(
        "scripts.cockpit_mcp._read_omo_constraints",
        lambda: ["禁止直接改写 .omo", "修改后立即 git commit"],
    )


# ══════════════════════════════════════════════════════════


class TestWorkspaceContext:
    def test_returns_phase(self, _patch_da, _mock_cards_dir, _mock_omo):
        from scripts.cockpit_mcp import workspace_context

        result = json.loads(workspace_context())
        assert result["phase"] == 28
        assert "constraints" in result

    def test_counts_p0_cards(self, _patch_da, _mock_cards_dir, _mock_omo):
        from scripts.cockpit_mcp import workspace_context

        result = json.loads(workspace_context())
        assert result["cards_summary"]["p0_open"] == 1
        assert "修复 cockpit MCP" in str(result["cards_summary"]["p0_titles"])

    def test_has_guidance(self, _patch_da, _mock_cards_dir, _mock_omo):
        from scripts.cockpit_mcp import workspace_context

        result = json.loads(workspace_context())
        assert "next_guidance" in result
        assert "P0" in str(result["next_guidance"])

    def test_fallback_when_cards_empty(self, _patch_da, tmp_path, _mock_omo, monkeypatch):
        monkeypatch.setattr("scripts.cockpit_mcp._CARDS_DIR", tmp_path / "nonexistent")
        from scripts.cockpit_mcp import workspace_context

        result = json.loads(workspace_context())
        assert result["cards_summary"]["total"] == 0


class TestCardsStatus:
    def test_returns_active_only(self, _patch_da, _mock_cards_dir):
        from scripts.cockpit_mcp import cards_status

        result = json.loads(cards_status())
        assert len(result) == 1  # only DEBT-001 active, TASK-old closed
        assert result[0]["id"] == "DEBT-001"
        assert result[0]["priority"] == "P0"

    def test_empty_directory(self, _patch_da, tmp_path, monkeypatch):
        monkeypatch.setattr("scripts.cockpit_mcp._CARDS_DIR", tmp_path / "empty")
        (tmp_path / "empty").mkdir()
        from scripts.cockpit_mcp import cards_status

        result = json.loads(cards_status())
        assert result == []


class TestCardsCheck:
    def test_compliant_when_no_issues(self, _patch_da, _mock_cards_dir, _mock_omo):
        from scripts.cockpit_mcp import cards_check

        result = json.loads(cards_check())
        assert result["compliant"] is True

    def test_closed_card_fails(self, _patch_da, _mock_cards_dir, _mock_omo):
        from scripts.cockpit_mcp import cards_check

        result = json.loads(cards_check(card_id="TASK-old"))
        assert result["compliant"] is False
        assert "已关闭" in str(result["violations"])

    def test_nonexistent_card_fails(self, _patch_da, _mock_cards_dir, _mock_omo):
        from scripts.cockpit_mcp import cards_check

        result = json.loads(cards_check(card_id="NONEXISTENT"))
        assert result["compliant"] is False


class TestVaultSearch:
    def test_finds_keyword(self, _patch_da, _mock_vault_dir):
        from scripts.cockpit_mcp import vault_search

        result = json.loads(vault_search(keyword="OMO"))
        assert result["total"] >= 1
        assert "OMO" in str(result["results"])

    def test_no_match(self, _patch_da, _mock_vault_dir):
        from scripts.cockpit_mcp import vault_search

        result = json.loads(vault_search(keyword="zzz_no_match"))
        assert result["total"] == 0

    def test_empty_keyword(self, _patch_da, _mock_vault_dir):
        from scripts.cockpit_mcp import vault_search

        result = json.loads(vault_search())
        assert result["total"] == 0
