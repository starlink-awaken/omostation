"""Tests for /api/omo/doctor (ADR-0201)."""

from __future__ import annotations

import json
from pathlib import Path

from cockpit.dashboard.helpers_doctor_cron import load_doctor_cron_status


def test_load_missing(tmp_path: Path):
    r = load_doctor_cron_status(tmp_path)
    assert r["available"] is False
    assert r["status"] == "missing"
    assert r["adr"] == "0201"


def test_load_latest_with_alert(tmp_path: Path):
    cron = tmp_path / "runtime" / "cron"
    cron.mkdir(parents=True)
    # history: 2 prior warns
    hist = cron / "omo-doctor-history.jsonl"
    rows = []
    for i in range(2):
        rows.append(
            json.dumps(
                {
                    "ts": f"2026-07-1{i}T09:20:00+00:00",
                    "highlights": {"path_acl_status": "warn", "warn": 1},
                }
            )
        )
    hist.write_text("\n".join(rows) + "\n")
    latest = {
        "written_at": "2026-07-15T09:20:00+00:00",
        "highlights": {
            "path_acl_status": "warn",
            "path_acl_detail": "1 ACL red flag",
            "path_acl_warn_streak": 3,
            "path_acl_alert": True,
            "path_acl_alert_threshold": 3,
            "ok": 4,
            "warn": 1,
            "fail": 0,
            "error": 0,
            "total": 5,
        },
        "doctor": {"summary": {"ok": 4, "warn": 1}},
    }
    (cron / "omo-doctor-latest.json").write_text(json.dumps(latest))
    r = load_doctor_cron_status(tmp_path)
    assert r["available"] is True
    assert r["status"] == "alert"
    assert r["highlights"]["path_acl_alert"] is True
    assert r["highlights"]["path_acl_warn_streak"] == 3
    assert len(r["history_tail"]) >= 1
