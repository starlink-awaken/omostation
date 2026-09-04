"""BET-Y1Q4-T8-05 Cockpit portfolio read-only command tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cockpit.commands import portfolio as PF


def test_missing_control_projection_is_unavailable(tmp_path: Path) -> None:
    result = PF.load_control_projection(tmp_path)
    assert result["status"] == "unavailable"
    assert result["unavailable_reason"] == "missing_control_projection"


def test_digest_bound_ok_payload(tmp_path: Path) -> None:
    control = tmp_path / ".omo/_control/portfolio-status.json"
    control.parent.mkdir(parents=True)
    payload = {
        "schema_version": "portfolio-status-projection/v1",
        "source_digest": "sha256:" + ("a" * 64),
        "status": "projected",
        "broker_ok": True,
        "bet_count": 3,
        "vision_id": "VISION-TEST",
        "status_counts": {"done": 2, "candidate": 1},
    }
    control.write_text(json.dumps(payload), encoding="utf-8")
    result = PF.load_control_projection(tmp_path)
    assert result["status"] == "ok"
    assert result["source_digest"] == payload["source_digest"]
    text = PF._format_status(result)
    assert "status=ok" in text
    assert payload["source_digest"] in text


def test_projection_marked_unavailable(tmp_path: Path) -> None:
    control = tmp_path / ".omo/_control/portfolio-status.json"
    control.parent.mkdir(parents=True)
    payload = {
        "source_digest": "sha256:" + ("b" * 64),
        "status": "unavailable",
        "unavailable_reason": "PORTFOLIO_BROKER_OWNER_MISSING",
    }
    control.write_text(json.dumps(payload), encoding="utf-8")
    result = PF.load_control_projection(tmp_path)
    assert result["status"] == "unavailable"
    assert "PORTFOLIO_BROKER_OWNER_MISSING" in result["unavailable_reason"]


def test_malformed_and_invalid_digest(tmp_path: Path) -> None:
    control = tmp_path / ".omo/_control/portfolio-status.json"
    control.parent.mkdir(parents=True)
    control.write_text("{not-json", encoding="utf-8")
    assert PF.load_control_projection(tmp_path)["status"] == "unavailable"
    control.write_text(json.dumps({"status": "projected", "source_digest": "nope"}), encoding="utf-8")
    assert PF.load_control_projection(tmp_path)["unavailable_reason"] == "digest_missing_or_invalid"


def test_objectives_critical_path_blockers_honest_unavailable(tmp_path: Path) -> None:
    control = tmp_path / ".omo/_control/portfolio-status.json"
    control.parent.mkdir(parents=True)
    payload = {
        "source_digest": "sha256:" + ("c" * 64),
        "status": "projected",
        "bet_count": 1,
    }
    control.write_text(json.dumps(payload), encoding="utf-8")
    result = PF.load_control_projection(tmp_path)
    assert "objectives=unavailable" in PF._format_objectives(result)
    assert "critical_path=unavailable" in PF._format_critical_path(result)
    assert "blockers=unavailable" in PF._format_blockers(result)


def test_register_portfolio_subcommand_dispatch() -> None:
    import argparse

    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd")
    PF.register_portfolio_subcommand(sub)
    args = parser.parse_args(["portfolio", "status"])
    assert args.cmd == "portfolio"
    assert args.portfolio_command == "status"
    assert callable(args.func)


def test_hostile_no_ledger_goals_omo_writers(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Any attempt to call known writer entrypoints from the handler must fail."""

    def boom(*_a, **_k):
        raise AssertionError("writer entrypoint invoked")

    # Monkeypatch common write surfaces that must never be used by portfolio command.
    monkeypatch.setattr(Path, "write_text", boom, raising=False)
    monkeypatch.setattr(Path, "write_bytes", boom, raising=False)

    # Missing projection → unavailable without writes
    result = PF.load_control_projection(tmp_path)
    assert result["status"] == "unavailable"
    # Formatting also must not write
    text = PF._format_status(result)
    assert "unavailable" in text
