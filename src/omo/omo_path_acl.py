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


# ── L2: plan / apply (ADR-0189) ───────────────────────────────────


def os_acl_enabled() -> bool:
    """Host mutation requires explicit opt-in env (ADR-0186 L2)."""
    return os.environ.get("OMO_OS_ACL", "").lower() in ("1", "true", "yes")


def plan_acl_actions(
    workspace_root: str | Path = ".",
    *,
    profile_path: Path | None = None,
) -> dict[str, Any]:
    """Build a dry-run plan of safe chmod fixes (strip other-write / 0777).

    Never executes. Actions are limited to mode bits; no chown/setfacl.
    """
    doctor = run_path_acl_doctor(
        workspace_root, profile_path=profile_path, strict=False
    )
    root = Path(doctor["workspace_root"])
    actions: list[dict[str, Any]] = []

    for f in doctor.get("findings") or []:
        kind = f.get("kind")
        if kind not in ("world_writable", "mode_777"):
            continue
        rel = str(f.get("path") or "")
        target = root / rel
        if not target.exists():
            continue
        try:
            current = stat.S_IMODE(target.stat().st_mode)
        except OSError as e:
            actions.append(
                {
                    "path": rel,
                    "op": "chmod",
                    "error": str(e),
                    "skipped": True,
                }
            )
            continue
        # Drop other-write; if 0777, also drop other-exec noise → 0775 for dirs
        if target.is_dir():
            desired = current & ~stat.S_IWOTH
            if current == 0o777:
                desired = 0o775
        else:
            desired = current & ~stat.S_IWOTH
            if current == 0o777:
                desired = 0o664
        if desired == current:
            continue
        actions.append(
            {
                "path": rel,
                "op": "chmod",
                "from_mode": oct(current),
                "to_mode": oct(desired),
                "to_mode_int": desired,
                "reason": kind,
                "shell": f"chmod {oct(desired)[2:]} {rel}",
            }
        )

    return {
        "adr": "0189",
        "layer": "L2",
        "dry_run": True,
        "mutation": False,
        "omo_os_acl_enabled": os_acl_enabled(),
        "workspace_root": str(root),
        "action_count": len(actions),
        "actions": actions,
        "doctor_warn_count": doctor.get("warn_count"),
        "note": "apply requires OMO_OS_ACL=1 and explicit --apply; never setfacl/chown",
    }


def plan_named_acl_script(
    workspace_root: str | Path = ".",
    *,
    profile_path: Path | None = None,
    platform: str | None = None,
) -> dict[str, Any]:
    """ADR-0194/0196: dry-run named ACE script (setfacl / chmod +a).

    Never executes. Emits shell lines operators can review.
    """
    import platform as _platform
    import shutil

    root = Path(workspace_root).resolve()
    profile = load_profile(profile_path)
    acl_cfg = profile.get("acl") if isinstance(profile.get("acl"), dict) else {}
    group = str(
        os.environ.get("OMO_ACL_GROUP") or acl_cfg.get("group") or "omo-writers"
    )
    broker_user = str(
        os.environ.get("OMO_BROKER_USER")
        or acl_cfg.get("broker_user")
        or os.environ.get("USER")
        or "omo"
    )
    raw = (platform or os.environ.get("OMO_ACL_PLATFORM") or _platform.system()).lower()
    if raw in ("macos", "darwin") or raw.startswith("darwin"):
        plat = "macos"
    elif raw in ("linux",) or raw.startswith("linux"):
        plat = "linux"
    else:
        plat = "unknown"

    entries = acl_cfg.get("entries")
    if not isinstance(entries, list) or not entries:
        # Default ACE map from ADR-0194
        entries = [
            {
                "path": ".omo/state",
                "users": ["$BROKER_USER"],
                "groups": [],
                "mask": "rwx",
            },
            {
                "path": ".omo/_control",
                "users": ["$BROKER_USER"],
                "groups": [],
                "mask": "rwx",
            },
            {
                "path": ".omo/_delivery",
                "users": ["$BROKER_USER"],
                "groups": ["$OMO_WRITERS"],
                "mask": "rwx",
            },
        ]

    lines: list[str] = [
        "#!/usr/bin/env bash",
        "# Generated by omo acl plan --acl (DRY-RUN — not executed)",
        f"# platform={plat} group={group} broker_user={broker_user}",
        "set -euo pipefail",
        f'BROKER_USER="${{OMO_BROKER_USER:-{broker_user}}}"',
        f'OMO_WRITERS="${{OMO_ACL_GROUP:-{group}}}"',
        f'ROOT="{root}"',
        "",
    ]
    commands: list[dict[str, Any]] = []

    setfacl_ok = shutil.which("setfacl") is not None
    for ent in entries:
        if not isinstance(ent, dict):
            continue
        rel = str(ent.get("path") or "")
        if not rel or rel.startswith(".omo/_truth"):
            continue
        mask = str(ent.get("mask") or "rwx")
        users = [str(u) for u in (ent.get("users") or [])]
        groups = [str(g) for g in (ent.get("groups") or [])]
        target = f'"$ROOT/{rel}"'
        if plat == "linux":
            if not setfacl_ok:
                lines.append(f"# WARN: setfacl not found — skip ACE for {rel}")
                commands.append(
                    {
                        "path": rel,
                        "op": "setfacl",
                        "skipped": True,
                        "reason": "setfacl binary missing",
                    }
                )
                continue
            for u in users:
                u_exp = u.replace("$BROKER_USER", '"$BROKER_USER"')
                cmd = f"setfacl -m u:{u_exp}:{mask} {target}"
                lines.append(cmd)
                commands.append(
                    {"path": rel, "op": "setfacl", "shell": cmd, "subject": u}
                )
            for g in groups:
                g_exp = g.replace("$OMO_WRITERS", '"$OMO_WRITERS"')
                cmd = f"setfacl -m g:{g_exp}:{mask} {target}"
                lines.append(cmd)
                commands.append(
                    {"path": rel, "op": "setfacl", "shell": cmd, "subject": g}
                )
            # default: remove other write via chmod (align L2)
            cmd = f"chmod o-w {target} 2>/dev/null || true"
            lines.append(cmd)
            commands.append({"path": rel, "op": "chmod", "shell": cmd})
        elif plat == "macos":
            for u in users:
                # macOS ACL allow write for broker user
                cmd = f'chmod +a "{u.replace("$BROKER_USER", "$BROKER_USER")} allow read,write,execute,delete,add_file,add_subdirectory,file_inherit,directory_inherit" {target}'
                lines.append(cmd)
                commands.append(
                    {"path": rel, "op": "chmod+a", "shell": cmd, "subject": u}
                )
            for g in groups:
                cmd = f'chmod +a "group:{g.replace("$OMO_WRITERS", "$OMO_WRITERS")} allow read,write,execute,delete,add_file,add_subdirectory,file_inherit,directory_inherit" {target}'
                lines.append(cmd)
                commands.append(
                    {"path": rel, "op": "chmod+a", "shell": cmd, "subject": g}
                )
            cmd = f"chmod o-w {target} 2>/dev/null || true"
            lines.append(cmd)
            commands.append({"path": rel, "op": "chmod", "shell": cmd})
        else:
            lines.append(f"# unsupported platform {plat} for {rel}")
            commands.append({"path": rel, "op": "skip", "reason": f"platform={plat}"})

    script = "\n".join(lines) + "\n"
    return {
        "adr": "0196",
        "layer": "L2-acl",
        "dry_run": True,
        "mutation": False,
        "platform": plat,
        "setfacl_available": setfacl_ok,
        "group": group,
        "broker_user": broker_user,
        "workspace_root": str(root),
        "command_count": len(commands),
        "commands": commands,
        "script": script,
        "note": "review then: OMO_OS_ACL=1 omo acl apply --yes --acl (ADR-0198)",
    }


def _expand_acl_subject(raw: str, broker_user: str, group: str) -> str:
    s = raw.strip()
    s = s.replace("$BROKER_USER", broker_user)
    s = s.replace("$OMO_WRITERS", group)
    s = s.replace('"', "").replace("'", "")
    return s


def apply_named_acl_actions(
    workspace_root: str | Path = ".",
    *,
    profile_path: Path | None = None,
    platform: str | None = None,
    force: bool = False,
) -> dict[str, Any]:
    """Execute named ACE + chmod o-w from plan (ADR-0198).

    Requires OMO_OS_ACL=1 unless force=True (tests only).
    Uses argv lists (no shell=True). Missing paths are skipped.
    """
    import shutil
    import subprocess

    plan = plan_named_acl_script(
        workspace_root, profile_path=profile_path, platform=platform
    )
    root = Path(plan["workspace_root"])
    enabled = os_acl_enabled() or force
    if not enabled:
        return {
            **plan,
            "applied": False,
            "mutation": False,
            "dry_run": True,
            "error": "OMO_OS_ACL not set — refusing named ACE apply",
            "results": [],
            "adr": "0198",
        }

    broker_user = str(plan.get("broker_user") or "omo")
    group = str(plan.get("group") or "omo-writers")
    plat = str(plan.get("platform") or "unknown")
    results: list[dict[str, Any]] = []

    # Rebuild executable steps from profile (structured, not shell parse)
    profile = load_profile(profile_path)
    acl_cfg = profile.get("acl") if isinstance(profile.get("acl"), dict) else {}
    entries = acl_cfg.get("entries")
    if not isinstance(entries, list) or not entries:
        entries = [
            {
                "path": ".omo/state",
                "users": ["$BROKER_USER"],
                "groups": [],
                "mask": "rwx",
            },
            {
                "path": ".omo/_control",
                "users": ["$BROKER_USER"],
                "groups": [],
                "mask": "rwx",
            },
            {
                "path": ".omo/_delivery",
                "users": ["$BROKER_USER"],
                "groups": ["$OMO_WRITERS"],
                "mask": "rwx",
            },
        ]

    setfacl_bin = shutil.which("setfacl")

    for ent in entries:
        if not isinstance(ent, dict):
            continue
        rel = str(ent.get("path") or "")
        if not rel or rel.startswith(".omo/_truth"):
            continue
        target = root / rel
        if not target.exists():
            results.append(
                {
                    "path": rel,
                    "ok": True,
                    "skipped": True,
                    "reason": "path missing",
                }
            )
            continue

        mask = str(ent.get("mask") or "rwx")
        users = [
            _expand_acl_subject(str(u), broker_user, group)
            for u in (ent.get("users") or [])
        ]
        groups = [
            _expand_acl_subject(str(g), broker_user, group)
            for g in (ent.get("groups") or [])
        ]

        # 1) named ACE
        if plat == "linux":
            if not setfacl_bin:
                results.append(
                    {
                        "path": rel,
                        "op": "setfacl",
                        "ok": False,
                        "skipped": True,
                        "reason": "setfacl binary missing",
                    }
                )
            else:
                for u in users:
                    if not u:
                        continue
                    argv = [setfacl_bin, "-m", f"u:{u}:{mask}", str(target)]
                    try:
                        r = subprocess.run(
                            argv,
                            capture_output=True,
                            text=True,
                            timeout=10,
                            check=False,
                        )
                        results.append(
                            {
                                "path": rel,
                                "op": "setfacl",
                                "subject": u,
                                "ok": r.returncode == 0,
                                "argv": argv,
                                "stderr": (r.stderr or "")[:200],
                            }
                        )
                    except (OSError, subprocess.TimeoutExpired) as e:
                        results.append(
                            {
                                "path": rel,
                                "op": "setfacl",
                                "subject": u,
                                "ok": False,
                                "error": str(e),
                            }
                        )
                for g in groups:
                    if not g:
                        continue
                    argv = [setfacl_bin, "-m", f"g:{g}:{mask}", str(target)]
                    try:
                        r = subprocess.run(
                            argv,
                            capture_output=True,
                            text=True,
                            timeout=10,
                            check=False,
                        )
                        results.append(
                            {
                                "path": rel,
                                "op": "setfacl",
                                "subject": g,
                                "ok": r.returncode == 0,
                                "argv": argv,
                                "stderr": (r.stderr or "")[:200],
                            }
                        )
                    except (OSError, subprocess.TimeoutExpired) as e:
                        results.append(
                            {
                                "path": rel,
                                "op": "setfacl",
                                "subject": g,
                                "ok": False,
                                "error": str(e),
                            }
                        )
        elif plat == "macos":
            rights = (
                "allow read,write,execute,delete,add_file,"
                "add_subdirectory,file_inherit,directory_inherit"
            )
            for u in users:
                if not u:
                    continue
                # chmod +a "user allow …" path
                argv = ["chmod", "+a", f"{u} {rights}", str(target)]
                try:
                    r = subprocess.run(
                        argv, capture_output=True, text=True, timeout=10, check=False
                    )
                    results.append(
                        {
                            "path": rel,
                            "op": "chmod+a",
                            "subject": u,
                            "ok": r.returncode == 0,
                            "argv": argv,
                            "stderr": (r.stderr or "")[:200],
                        }
                    )
                except (OSError, subprocess.TimeoutExpired) as e:
                    results.append(
                        {
                            "path": rel,
                            "op": "chmod+a",
                            "subject": u,
                            "ok": False,
                            "error": str(e),
                        }
                    )
            for g in groups:
                if not g:
                    continue
                argv = ["chmod", "+a", f"group:{g} {rights}", str(target)]
                try:
                    r = subprocess.run(
                        argv, capture_output=True, text=True, timeout=10, check=False
                    )
                    results.append(
                        {
                            "path": rel,
                            "op": "chmod+a",
                            "subject": g,
                            "ok": r.returncode == 0,
                            "argv": argv,
                            "stderr": (r.stderr or "")[:200],
                        }
                    )
                except (OSError, subprocess.TimeoutExpired) as e:
                    results.append(
                        {
                            "path": rel,
                            "op": "chmod+a",
                            "subject": g,
                            "ok": False,
                            "error": str(e),
                        }
                    )
        else:
            results.append(
                {
                    "path": rel,
                    "ok": False,
                    "skipped": True,
                    "reason": f"unsupported platform {plat}",
                }
            )

        # 2) always strip other-write (Python, no shell)
        try:
            mode = stat.S_IMODE(target.stat().st_mode)
            new_mode = mode & ~stat.S_IWOTH
            if new_mode != mode:
                os.chmod(target, new_mode)
            results.append(
                {
                    "path": rel,
                    "op": "chmod_o-w",
                    "ok": True,
                    "from_mode": oct(mode),
                    "to_mode": oct(stat.S_IMODE(target.stat().st_mode)),
                }
            )
        except OSError as e:
            results.append(
                {
                    "path": rel,
                    "op": "chmod_o-w",
                    "ok": False,
                    "error": str(e),
                }
            )

    ok_n = sum(1 for r in results if r.get("ok") and not r.get("skipped"))
    fail_n = sum(1 for r in results if r.get("ok") is False and not r.get("skipped"))
    return {
        "adr": "0198",
        "layer": "L2-acl",
        "dry_run": False,
        "mutation": True,
        "applied": True,
        "omo_os_acl_enabled": True,
        "platform": plat,
        "workspace_root": str(root),
        "broker_user": broker_user,
        "group": group,
        "result_count": len(results),
        "applied_ok": ok_n,
        "applied_fail": fail_n,
        "results": results,
        "plan_preview": {
            "command_count": plan.get("command_count"),
            "script_head": (plan.get("script") or "")[:400],
        },
    }


def apply_acl_actions(
    workspace_root: str | Path = ".",
    *,
    profile_path: Path | None = None,
    force: bool = False,
) -> dict[str, Any]:
    """Apply planned chmod fixes when OMO_OS_ACL=1 (or force for tests only).

    Production CLI never passes force=True without the env gate.
    """
    plan = plan_acl_actions(workspace_root, profile_path=profile_path)
    root = Path(plan["workspace_root"])
    enabled = os_acl_enabled() or force
    results: list[dict[str, Any]] = []

    if not enabled:
        return {
            **plan,
            "applied": False,
            "mutation": False,
            "error": "OMO_OS_ACL not set — refusing host mutation (dry-run only)",
            "results": [],
        }

    if not plan["actions"]:
        return {
            **plan,
            "applied": True,
            "mutation": False,
            "results": [],
            "note": "nothing to apply",
        }

    for action in plan["actions"]:
        rel = action["path"]
        target = root / rel
        entry = dict(action)
        try:
            os.chmod(target, int(action["to_mode_int"]))
            entry["ok"] = True
            entry["applied_mode"] = oct(stat.S_IMODE(target.stat().st_mode))
        except OSError as e:
            entry["ok"] = False
            entry["error"] = str(e)
        results.append(entry)

    ok_n = sum(1 for r in results if r.get("ok"))
    return {
        "adr": "0189",
        "layer": "L2",
        "dry_run": False,
        "mutation": True,
        "omo_os_acl_enabled": True,
        "workspace_root": str(root),
        "action_count": len(plan["actions"]),
        "applied_ok": ok_n,
        "applied_fail": len(results) - ok_n,
        "results": results,
        "applied": True,
    }
