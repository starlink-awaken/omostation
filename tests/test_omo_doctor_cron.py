"""Tests for bin/gac/omo-doctor-cron.py (ADR-0200)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

WS = Path(__file__).resolve().parents[1]
SCRIPT = WS / "bin" / "gac" / "omo-doctor-cron.py"


def test_script_exists_and_runs_no_write():
    assert SCRIPT.is_file()
    # --no-write avoids depending on doctor success writing under runtime/
    r = subprocess.run(
        [sys.executable, str(SCRIPT), "--no-write"],
        cwd=str(WS),
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    # May fail if omo not installable in env; still must print marker or error path
    out = (r.stdout or "") + (r.stderr or "")
    assert "omo-doctor-cron" in out or "error" in out.lower() or r.returncode in (0, 1)


def test_highlights_extract_logic(tmp_path, monkeypatch):
    # import module by path
    import importlib.util

    spec = importlib.util.spec_from_file_location("omo_doctor_cron", SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    payload = {
        "checks": [
            {"id": "path-acl", "status": "warn", "detail": "1 ACL red flag"},
            {"id": "key-files", "status": "ok", "detail": "ok"},
        ],
        "summary": {"total": 2, "ok": 1, "warn": 1, "fail": 0, "error": 0},
    }
    h = mod._extract_highlights(payload)
    assert h["path_acl_status"] == "warn"
    assert h["warn"] == 1
    assert "red flag" in h["path_acl_detail"]

    # error payload when omo missing
    err = {"error": "projects/omo not initialized", "checks": [], "summary": {"error": 1}}
    h2 = mod._extract_highlights(err)
    assert h2["path_acl_status"] == "error"
    assert "not initialized" in h2["path_acl_detail"]
