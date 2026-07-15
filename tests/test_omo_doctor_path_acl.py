"""Doctor path-acl check (ADR-0199)."""

from __future__ import annotations

import os
from pathlib import Path

from omo.omo_doctor import _check_path_acl


def test_path_acl_ok_on_clean_or_missing(tmp_path: Path, monkeypatch):
    # Point WORKSPACE-like root via path-acl profile surfaces under tmp
    monkeypatch.setenv("OMO_PATH_ACL_PROFILE", str(tmp_path / "nope.yaml"))
    # empty workspace — missing surfaces are info, not warn
    # run_path_acl_doctor uses workspace_root arg only via doctor helper
    # _check_path_acl uses WORKSPACE_ROOT; monkeypatch omo_doctor root by cwd
    monkeypatch.chdir(tmp_path)
    # Also patch WORKSPACE_ROOT used in doctor
    import omo.omo_doctor as d

    monkeypatch.setattr(d, "WORKSPACE_ROOT", tmp_path)
    monkeypatch.setattr(d, "OMO_ROOT", tmp_path / ".omo")
    r = _check_path_acl()
    assert r["id"] == "path-acl"
    assert r["status"] == "ok"


def test_path_acl_warns_on_777(tmp_path: Path, monkeypatch):
    import omo.omo_doctor as d

    state = tmp_path / ".omo" / "state"
    state.mkdir(parents=True)
    os.chmod(state, 0o777)
    monkeypatch.setattr(d, "WORKSPACE_ROOT", tmp_path)
    monkeypatch.setattr(d, "OMO_ROOT", tmp_path / ".omo")
    r = _check_path_acl()
    assert r["status"] == "warn"
    assert (
        "world-writable" in r["detail"]
        or "0777" in r["detail"]
        or "mode_777" in r["detail"]
    )
    assert "omo acl plan" in r["detail"]
