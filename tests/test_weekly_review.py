#!/usr/bin/env python3
"""Tests for weekly-review.py aggregation, heartbeat write, and M3 ritual check."""

import importlib.util
import json
import sys
import tempfile
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest

# Add bin/ to path for imports
REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "bin" / "ssot"))
sys.path.insert(0, str(REPO / "bin" / "gac"))


def _import_hyphenated(path: Path, module_name: str):
    """Import a Python file with hyphens in the name."""
    spec = importlib.util.spec_from_file_location(module_name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = mod
    spec.loader.exec_module(mod)
    return mod


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def tmp_ws(tmp_path):
    """Create a minimal workspace skeleton for testing."""
    (tmp_path / ".omo" / "state" / "heartbeats").mkdir(parents=True)
    (tmp_path / ".omo" / "debt" / "items").mkdir(parents=True)
    (tmp_path / ".omo" / "_control" / "cockpit-inbox").mkdir(parents=True)
    (tmp_path / ".omo" / "tasks" / "planned").mkdir(parents=True)
    (tmp_path / "bin" / "ssot").mkdir(parents=True)
    (tmp_path / "bin" / "gac").mkdir(parents=True)
    (tmp_path / "bin" / "mof").mkdir(parents=True)
    return tmp_path


@pytest.fixture
def fake_debt_items(tmp_ws):
    """Create fake debt items for testing."""
    items_dir = tmp_ws / ".omo" / "debt" / "items"
    # Open item
    (items_dir / "MDEAD-001.yaml").write_text(
        'id: MDEAD-001\ntitle: "引用断链: some-tool"\n'
        "lifecycle_state: proposed\nseverity: medium\n",
        encoding="utf-8",
    )
    # Another open item
    (items_dir / "D-99.yaml").write_text(
        "id: D-99\ntitle: 测试债务\n"
        "lifecycle_state: open\nseverity: low\n",
        encoding="utf-8",
    )
    # Resolved item (should not count)
    (items_dir / "D-50.yaml").write_text(
        "id: D-50\ntitle: 已解决\n"
        "lifecycle_state: resolved\nseverity: medium\n",
        encoding="utf-8",
    )
    return items_dir


@pytest.fixture
def weekly_review_mod():
    """Import weekly-review.py module."""
    path = REPO / "bin" / "ssot" / "weekly-review.py"
    return _import_hyphenated(path, "weekly_review")


@pytest.fixture
def meta_doctor_mod():
    """Import meta-doctor.py module."""
    path = REPO / "bin" / "gac" / "meta-doctor.py"
    return _import_hyphenated(path, "meta_doctor")


# ── Test: scan_debt_counts ────────────────────────────────────────────────────

def test_scan_debt_counts_basic(tmp_ws, fake_debt_items, weekly_review_mod):
    """scan_debt_counts should count open + proposed, list MDEAD titles."""
    result = weekly_review_mod.scan_debt_counts(tmp_ws)
    assert result["open_count"] == 1  # D-99
    assert result["proposed_count"] == 1  # MDEAD-001
    assert result["total"] == 2
    assert len(result["mdead_titles"]) == 1
    assert "引用断链" in result["mdead_titles"][0]


def test_scan_debt_counts_empty(tmp_ws, weekly_review_mod):
    """Empty debt dir → zero counts."""
    result = weekly_review_mod.scan_debt_counts(tmp_ws)
    assert result["open_count"] == 0
    assert result["proposed_count"] == 0
    assert result["total"] == 0
    assert result["mdead_titles"] == []


# ── Test: collect_decisions ───────────────────────────────────────────────────

def test_collect_decisions_returns_list(tmp_ws, weekly_review_mod):
    """collect_decisions should return a list (may be empty if no tasks)."""
    result = weekly_review_mod.collect_decisions(tmp_ws)
    assert isinstance(result, list)


# ── Test: write_heartbeat ─────────────────────────────────────────────────────

def test_write_heartbeat_creates_file(tmp_ws, weekly_review_mod):
    """write_heartbeat should create heartbeats/weekly-review.json with ok:true."""
    hb_path = tmp_ws / ".omo" / "state" / "heartbeats" / "weekly-review.json"
    assert not hb_path.exists()

    weekly_review_mod.write_heartbeat(tmp_ws)
    assert hb_path.exists()

    data = json.loads(hb_path.read_text(encoding="utf-8"))
    assert data["ok"] is True
    assert "generated_at" in data
    # Verify timestamp is parseable
    datetime.fromisoformat(data["generated_at"].replace("Z", "+00:00"))


def test_write_heartbeat_overwrites(tmp_ws, weekly_review_mod):
    """write_heartbeat should overwrite existing heartbeat file."""
    hb_path = tmp_ws / ".omo" / "state" / "heartbeats" / "weekly-review.json"
    hb_path.write_text('{"old": true}', encoding="utf-8")

    weekly_review_mod.write_heartbeat(tmp_ws)
    data = json.loads(hb_path.read_text(encoding="utf-8"))
    assert "old" not in data
    assert data["ok"] is True


# ── Test: build_card (aggregation structure) ──────────────────────────────────

def test_build_card_has_required_sections(tmp_ws, fake_debt_items, weekly_review_mod):
    """build_card output should have health, value, debt, decisions sections."""
    card = weekly_review_mod.build_card(tmp_ws)
    assert "health" in card
    assert "value" in card
    assert "debt" in card
    assert "decisions" in card
    assert "generated_at" in card


def test_build_card_health_section(tmp_ws, weekly_review_mod):
    """Health section should have score field (or 'n/a')."""
    card = weekly_review_mod.build_card(tmp_ws)
    assert "score" in card["health"]


def test_build_card_debt_section(tmp_ws, fake_debt_items, weekly_review_mod):
    """Debt section should reflect counts from debt items."""
    card = weekly_review_mod.build_card(tmp_ws)
    assert card["debt"]["open_count"] >= 0
    assert card["debt"]["proposed_count"] >= 0
    assert isinstance(card["debt"]["mdead_titles"], list)


# ── Test: M3 ritual check in meta-doctor ──────────────────────────────────────

def test_check_ritual_missing_heartbeat(tmp_ws, meta_doctor_mod):
    """Missing weekly-review heartbeat → returns T1 debt proposal."""
    proposals = meta_doctor_mod.check_ritual(tmp_ws)
    assert len(proposals) == 1
    p = proposals[0]
    assert p["id"] == "M3-owner-review-lapsed"
    assert "断供" in p["title"] or "lapsed" in p["title"].lower()
    assert p["severity"] == "medium"


def test_check_ritual_stale_heartbeat(tmp_ws, meta_doctor_mod):
    """Heartbeat older than 336h (14 days) → returns T1 debt proposal."""
    hb_path = tmp_ws / ".omo" / "state" / "heartbeats" / "weekly-review.json"
    stale_time = datetime.now(UTC) - timedelta(hours=337)
    hb_path.write_text(
        json.dumps({"generated_at": stale_time.isoformat(), "ok": True}),
        encoding="utf-8",
    )

    proposals = meta_doctor_mod.check_ritual(tmp_ws)
    assert len(proposals) == 1
    assert proposals[0]["id"] == "M3-owner-review-lapsed"


def test_check_ritual_fresh_heartbeat(tmp_ws, meta_doctor_mod):
    """Fresh heartbeat (< 336h) → no proposals."""
    hb_path = tmp_ws / ".omo" / "state" / "heartbeats" / "weekly-review.json"
    fresh_time = datetime.now(UTC) - timedelta(hours=1)
    hb_path.write_text(
        json.dumps({"generated_at": fresh_time.isoformat(), "ok": True}),
        encoding="utf-8",
    )

    proposals = meta_doctor_mod.check_ritual(tmp_ws)
    assert len(proposals) == 0


def test_check_ritual_bad_json(tmp_ws, meta_doctor_mod):
    """Corrupt heartbeat file → treated as missing → proposal."""
    hb_path = tmp_ws / ".omo" / "state" / "heartbeats" / "weekly-review.json"
    hb_path.write_text("NOT JSON", encoding="utf-8")

    proposals = meta_doctor_mod.check_ritual(tmp_ws)
    assert len(proposals) == 1
    assert proposals[0]["id"] == "M3-owner-review-lapsed"


# ── Test: main() integration ─────────────────────────────────────────────────

def test_main_json_output(tmp_ws, fake_debt_items, capsys, weekly_review_mod):
    """--json flag should produce valid JSON with required keys."""
    sys.argv = ["weekly-review.py", "--json"]
    original_ws = weekly_review_mod.WORKSPACE
    weekly_review_mod.WORKSPACE = tmp_ws
    try:
        ret = weekly_review_mod.main()
    finally:
        weekly_review_mod.WORKSPACE = original_ws

    assert ret == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert "health" in data
    assert "value" in data
    assert "debt" in data
    assert "decisions" in data


def test_main_post_inbox(tmp_ws, fake_debt_items, capsys, weekly_review_mod):
    """--post-inbox should write JSON to cockpit-inbox and print path."""
    original_ws = weekly_review_mod.WORKSPACE
    weekly_review_mod.WORKSPACE = tmp_ws
    sys.argv = ["weekly-review.py", "--post-inbox"]
    try:
        ret = weekly_review_mod.main()
    finally:
        weekly_review_mod.WORKSPACE = original_ws

    assert ret == 0
    inbox_path = tmp_ws / ".omo" / "_control" / "cockpit-inbox" / "weekly-review-latest.json"
    assert inbox_path.exists()
    data = json.loads(inbox_path.read_text(encoding="utf-8"))
    assert "health" in data
    captured = capsys.readouterr()
    assert str(inbox_path) in captured.out
