"""Scheme C 5c L1 — path ACL doctor (read-only, no host mutation).

ADR-0186 design + ADR-0187 implementation step 1:
  ``omo lint path-acl`` reports world-writable / overly-permissive modes on
  governed surfaces. Never calls chmod/setfacl/chown.

CI-safe: missing surfaces are INFO; world-write is WARN (or FAIL if strict).
"""

from __future__ import annotations

import json
import os
import stat
import sys
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None  # type: ignore[assignment]

from .omo_paths import WORKSPACE_ROOT


def _default_profile_path() -> Path:
    env = os.environ.get("OMO_PATH_ACL_PROFILE")
    if env:
        return Path(env)
    # projects/omo/etc/omo-path-acl.yaml
    return Path(__file__).resolve().parents[2] / "etc" / "omo-path-acl.yaml"


def _builtin_surfaces() -> list[dict[str, Any]]:
    return [
        {
            "id": "omo-state",
            "path": ".omo/state",
            "forbid_world_write": True,
            "must_exist": False,
        },
        {
            "id": "omo-control",
            "path": ".omo/_control",
            "forbid_world_write": True,
            "must_exist": False,
        },
        {
            "id": "omo-delivery",
            "path": ".omo/_delivery",
            "forbid_world_write": True,
            "must_exist": False,
        },
        {
            "id": "omo-truth",
            "path": ".omo/_truth",
            "forbid_world_write": True,
            "must_exist": False,
        },
        {
            "id": "spaces",
            "path": "spaces",
            "forbid_world_write": True,
            "must_exist": False,
        },
    ]


def load_profile(path: Path | None = None) -> dict[str, Any]:
    cfg_path = path or _default_profile_path()
    if yaml is None or not cfg_path.is_file():
        return {
            "version": 1,
            "strict": False,
            "surfaces": _builtin_surfaces(),
            "source": "builtin",
        }
    with cfg_path.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    if not isinstance(data, dict):
        return {
            "version": 1,
            "strict": False,
            "surfaces": _builtin_surfaces(),
            "source": "builtin-fallback",
        }
    data.setdefault("surfaces", _builtin_surfaces())
    data.setdefault("strict", False)
    data["source"] = str(cfg_path)
    return data


def _mode_oct(mode: int) -> str:
    return oct(stat.S_IMODE(mode))


def inspect_path(
    root: Path,
    surface: dict[str, Any],
) -> list[dict[str, Any]]:
    """Return findings for one surface (empty = clean)."""
    rel = str(surface.get("path") or "")
    target = (root / rel).resolve() if rel else root
    findings: list[dict[str, Any]] = []
    sid = str(surface.get("id") or rel or "unknown")

    if not target.exists():
        if surface.get("must_exist"):
            findings.append(
                {
                    "severity": "warn",
                    "kind": "missing_surface",
                    "surface": sid,
                    "path": rel,
                    "detail": "path does not exist",
                }
            )
        else:
            findings.append(
                {
                    "severity": "info",
                    "kind": "missing_optional",
                    "surface": sid,
                    "path": rel,
                    "detail": "path absent (OK for fresh clone)",
                }
            )
        return findings

    try:
        st = target.stat()
    except OSError as e:
        findings.append(
            {
                "severity": "warn",
                "kind": "stat_error",
                "surface": sid,
                "path": rel,
                "detail": str(e),
            }
        )
        return findings

    mode = stat.S_IMODE(st.st_mode)
    world_write = bool(mode & stat.S_IWOTH)
    group_write = bool(mode & stat.S_IWGRP)

    if surface.get("forbid_world_write", True) and world_write:
        findings.append(
            {
                "severity": "halt" if surface.get("strict_world_write") else "warn",
                "kind": "world_writable",
                "surface": sid,
                "path": rel,
                "mode": _mode_oct(mode),
                "detail": "other-write bit set; governed surface should not be world-writable",
                "recommend": f"chmod o-w {rel}",
            }
        )

    # sticky world-readable OK; flag overly open 777
    if mode == 0o777:
        findings.append(
            {
                "severity": "warn",
                "kind": "mode_777",
                "surface": sid,
                "path": rel,
                "mode": _mode_oct(mode),
                "detail": "mode 0777 is never appropriate for governed write plane",
                "recommend": f"chmod 775 or 755 {rel}",
            }
        )

    # group-write on git-owned truth is suspicious for multi-agent hosts
    if surface.get("expect") == "git-owned" and group_write and not world_write:
        findings.append(
            {
                "severity": "info",
                "kind": "group_writable_git_surface",
                "surface": sid,
                "path": rel,
                "mode": _mode_oct(mode),
                "detail": "SSOT surface is group-writable; ensure only operator group",
            }
        )

    if not findings:
        findings.append(
            {
                "severity": "info",
                "kind": "ok",
                "surface": sid,
                "path": rel,
                "mode": _mode_oct(mode),
                "detail": "no ACL red flags",
            }
        )
    return findings


def run_path_acl_doctor(
    workspace_root: str | Path = ".",
    *,
    profile_path: Path | None = None,
    strict: bool | None = None,
) -> dict[str, Any]:
    root = Path(workspace_root).resolve()
    # Prefer workspace .omo next to cwd; fall back to WORKSPACE_ROOT
    if not (root / ".omo").exists() and (WORKSPACE_ROOT / ".omo").exists():
        # still scan the explicit root; missing → info
        pass

    profile = load_profile(profile_path)
    env_strict = os.environ.get("OMO_PATH_ACL_STRICT", "").lower() in (
        "1",
        "true",
        "yes",
    )
    is_strict = (
        bool(strict)
        if strict is not None
        else (env_strict or bool(profile.get("strict")))
    )

    findings: list[dict[str, Any]] = []
    for surface in profile.get("surfaces") or []:
        if not isinstance(surface, dict):
            continue
        findings.extend(inspect_path(root, surface))

    # escalate world_writable / mode_777 to halt when strict
    if is_strict:
        for f in findings:
            if f.get("kind") in ("world_writable", "mode_777"):
                f["severity"] = "halt"

    halt_n = sum(1 for f in findings if f.get("severity") == "halt")
    warn_n = sum(1 for f in findings if f.get("severity") == "warn")
    ok = halt_n == 0
    # In non-strict mode, warnings do not fail exit
    if not is_strict:
        ok = True

    return {
        "ok": ok,
        "strict": is_strict,
        "workspace_root": str(root),
        "profile_source": profile.get("source"),
        "surface_count": len(profile.get("surfaces") or []),
        "halt_count": halt_n,
        "warn_count": warn_n,
        "findings": findings,
        "mutation": False,
        "adr": "0187",
    }


def cmd_lint_path_acl(
    workspace_root: str = ".",
    *,
    json_output: bool = False,
    strict: bool = False,
    profile: str | None = None,
) -> int:
    report = run_path_acl_doctor(
        workspace_root,
        profile_path=Path(profile) if profile else None,
        strict=strict or None,
    )
    if json_output:
        json.dump(report, sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
    else:
        status = "OK" if report["ok"] else "FAIL"
        print(
            f"[{status}] path-acl: surfaces={report['surface_count']} "
            f"halt={report['halt_count']} warn={report['warn_count']} "
            f"strict={report['strict']} (no host mutation)"
        )
        for f in report["findings"]:
            if f.get("kind") == "ok" and not os.environ.get("OMO_PATH_ACL_VERBOSE"):
                continue
            print(
                f"  [{f.get('severity')}] {f.get('kind')}: "
                f"{f.get('path')} {f.get('detail', '')}"
            )
            if f.get("recommend"):
                print(f"    recommend: {f['recommend']}")
    return 0 if report["ok"] else 1
