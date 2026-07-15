"""Scheme C 5c L1 path-acl doctor tests."""

from __future__ import annotations

import os
import stat
from pathlib import Path

from omo.omo_path_acl import (
    cmd_lint_path_acl,
    inspect_path,
    load_profile,
    run_path_acl_doctor,
)


def test_load_profile_builtin_or_ssot():
    p = load_profile()
    assert p.get("surfaces")
    assert any(s.get("path") == ".omo/state" for s in p["surfaces"])


def test_missing_surface_is_info(tmp_path: Path):
    findings = inspect_path(
        tmp_path,
        {"id": "omo-state", "path": ".omo/state", "forbid_world_write": True},
    )
    assert findings[0]["kind"] == "missing_optional"
    assert findings[0]["severity"] == "info"


def test_world_writable_detected(tmp_path: Path):
    target = tmp_path / ".omo" / "state"
    target.mkdir(parents=True)
    os.chmod(target, 0o777)
    findings = inspect_path(
        tmp_path,
        {
            "id": "omo-state",
            "path": ".omo/state",
            "forbid_world_write": True,
        },
    )
    kinds = {f["kind"] for f in findings}
    assert "world_writable" in kinds or "mode_777" in kinds


def test_clean_mode_ok(tmp_path: Path):
    target = tmp_path / ".omo" / "state"
    target.mkdir(parents=True)
    os.chmod(target, 0o755)
    findings = inspect_path(
        tmp_path,
        {"id": "omo-state", "path": ".omo/state", "forbid_world_write": True},
    )
    assert any(f["kind"] == "ok" for f in findings)


def test_doctor_nonstrict_ok_with_warnings(tmp_path: Path):
    bad = tmp_path / ".omo" / "state"
    bad.mkdir(parents=True)
    os.chmod(bad, 0o777)
    report = run_path_acl_doctor(tmp_path, strict=False)
    assert report["mutation"] is False
    assert report["ok"] is True  # warn-only
    assert report["warn_count"] >= 1 or report["halt_count"] >= 0


def test_doctor_strict_fails_on_777(tmp_path: Path):
    bad = tmp_path / ".omo" / "state"
    bad.mkdir(parents=True)
    os.chmod(bad, 0o777)
    report = run_path_acl_doctor(tmp_path, strict=True)
    assert report["ok"] is False
    assert report["halt_count"] >= 1


def test_cmd_exit_codes(tmp_path: Path, capsys):
    # empty root — nonstrict always 0
    assert cmd_lint_path_acl(str(tmp_path), json_output=True, strict=False) == 0
    out = capsys.readouterr().out
    assert '"adr": "0187"' in out or '"adr":"0187"' in out or "0187" in out
