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


def test_plan_actions_for_777(tmp_path: Path):
    from omo.omo_path_acl import plan_acl_actions

    target = tmp_path / ".omo" / "state"
    target.mkdir(parents=True)
    os.chmod(target, 0o777)
    plan = plan_acl_actions(tmp_path)
    assert plan["dry_run"] is True
    assert plan["mutation"] is False
    assert plan["action_count"] >= 1
    assert any(a["op"] == "chmod" for a in plan["actions"])


def test_apply_refuses_without_env(tmp_path: Path, monkeypatch):
    from omo.omo_path_acl import apply_acl_actions

    monkeypatch.delenv("OMO_OS_ACL", raising=False)
    target = tmp_path / ".omo" / "state"
    target.mkdir(parents=True)
    os.chmod(target, 0o777)
    report = apply_acl_actions(tmp_path, force=False)
    assert report["mutation"] is False
    assert report.get("applied") is False
    # still 0777
    assert stat.S_IMODE(target.stat().st_mode) == 0o777


def test_apply_with_force_strips_other_write(tmp_path: Path):
    from omo.omo_path_acl import apply_acl_actions

    target = tmp_path / ".omo" / "state"
    target.mkdir(parents=True)
    os.chmod(target, 0o777)
    report = apply_acl_actions(tmp_path, force=True)
    assert report["mutation"] is True
    assert report.get("applied_ok", 0) >= 1
    mode = stat.S_IMODE(target.stat().st_mode)
    assert not (mode & stat.S_IWOTH)


def test_plan_named_acl_script_linux_dry_run(tmp_path: Path):
    from omo.omo_path_acl import plan_named_acl_script

    (tmp_path / ".omo" / "state").mkdir(parents=True)
    plan = plan_named_acl_script(tmp_path, platform="linux")
    assert plan["dry_run"] is True
    assert plan["mutation"] is False
    assert plan["adr"] == "0196"
    assert "script" in plan
    assert "setfacl" in plan["script"] or "WARN" in plan["script"]
    assert plan["command_count"] >= 1


def test_plan_named_acl_script_macos(tmp_path: Path):
    from omo.omo_path_acl import plan_named_acl_script

    plan = plan_named_acl_script(tmp_path, platform="macos")
    assert plan["platform"] == "macos"
    assert "chmod +a" in plan["script"]


def test_apply_named_acl_refuses_without_env(tmp_path: Path, monkeypatch):
    from omo.omo_path_acl import apply_named_acl_actions

    monkeypatch.delenv("OMO_OS_ACL", raising=False)
    (tmp_path / ".omo" / "state").mkdir(parents=True)
    os.chmod(tmp_path / ".omo" / "state", 0o777)
    r = apply_named_acl_actions(tmp_path, force=False)
    assert r["mutation"] is False
    assert r.get("applied") is False
    assert "OMO_OS_ACL" in (r.get("error") or "")


def test_apply_named_acl_force_strips_other_write(tmp_path: Path):
    from omo.omo_path_acl import apply_named_acl_actions

    # create profile surfaces
    for rel in (".omo/state", ".omo/_control", ".omo/_delivery"):
        p = tmp_path / rel
        p.mkdir(parents=True)
        os.chmod(p, 0o777)

    # Use linux path but chmod_o-w always runs; setfacl may fail/skip on mac
    r = apply_named_acl_actions(tmp_path, platform="linux", force=True)
    assert r["adr"] == "0198"
    assert r["mutation"] is True
    assert r.get("applied") is True
    for rel in (".omo/state", ".omo/_control", ".omo/_delivery"):
        mode = stat.S_IMODE((tmp_path / rel).stat().st_mode)
        assert not (mode & stat.S_IWOTH), f"{rel} still world-writable: {oct(mode)}"
    # chmod_o-w steps should succeed
    chmod_steps = [x for x in r["results"] if x.get("op") == "chmod_o-w"]
    assert chmod_steps
    assert all(x.get("ok") for x in chmod_steps)


def test_apply_named_acl_skips_missing_paths(tmp_path: Path):
    from omo.omo_path_acl import apply_named_acl_actions

    # no .omo dirs — all skipped
    r = apply_named_acl_actions(tmp_path, force=True)
    assert r["mutation"] is True
    skipped = [x for x in r["results"] if x.get("skipped")]
    assert skipped
