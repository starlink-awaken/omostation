#!/usr/bin/env python3
"""CLI for G-CONV.7 / ADR-0220 swarm discipline gates.

Usage:
  swarm-discipline-cli.py adr-claim --session S [--number N]
  swarm-discipline-cli.py adr-check --file PATH [--session S]
  swarm-discipline-cli.py branch-claim --session S
  swarm-discipline-cli.py branch-check --branch work/S --session S
  swarm-discipline-cli.py claim-check --staged
  swarm-discipline-cli.py escape-check --flag ci_local_skip --escape-id ID
  swarm-discipline-cli.py window-start
  swarm-discipline-cli.py window-status
  swarm-discipline-cli.py inventory
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

# allow running as script
sys.path.insert(0, str(Path(__file__).resolve().parent))
import swarm_discipline as sd  # noqa: E402


def root_from_cwd() -> Path:
    try:
        r = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=False,
        )
        if r.returncode == 0 and r.stdout.strip():
            return Path(r.stdout.strip())
    except OSError:
        pass
    return Path(__file__).resolve().parents[2]


def cmd_adr_claim(args: argparse.Namespace) -> int:
    root = root_from_cwd()
    ok, result = sd.acquire_adr_claim(
        root, args.session, number=args.number
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if ok else 1


def cmd_adr_check(args: argparse.Namespace) -> int:
    root = root_from_cwd()
    ok, reason = sd.check_adr_write_authorized(root, args.file, args.session)
    print(json.dumps({"ok": ok, "reason": reason, "file": args.file}, indent=2))
    return 0 if ok else 1


def cmd_branch_claim(args: argparse.Namespace) -> int:
    root = root_from_cwd()
    ok, result = sd.acquire_branch_lock(root, args.session, args.branch)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if ok else 1


def cmd_branch_check(args: argparse.Namespace) -> int:
    root = root_from_cwd()
    ok, reason = sd.check_branch_available(root, args.branch, args.session)
    print(json.dumps({"ok": ok, "reason": reason, "branch": args.branch}, indent=2))
    return 0 if ok else 1


def cmd_branch_release(args: argparse.Namespace) -> int:
    root = root_from_cwd()
    done = sd.release_branch_lock(root, args.session)
    print(json.dumps({"released": done, "session": args.session}, indent=2))
    return 0


def cmd_claim_check(args: argparse.Namespace) -> int:
    root = root_from_cwd()
    if args.staged:
        r = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )
        paths = [ln.strip() for ln in r.stdout.splitlines() if ln.strip()]
    else:
        paths = list(args.paths or [])
    if not paths:
        print(json.dumps({"ok": True, "reason": "no_paths", "violations": []}, indent=2))
        return 0
    ok, violations = sd.check_shared_worktree_writes(root, paths)
    print(
        json.dumps(
            {"ok": ok, "violations": violations, "paths": paths},
            ensure_ascii=False,
            indent=2,
        )
    )
    if not ok:
        print(
            "❌ D3 shared-worktree claim check failed. "
            "Use worktree (gac-worktree claim) or agent-workflow claim <run> --path <p>.",
            file=sys.stderr,
        )
    return 0 if ok else 1


def cmd_escape_check(args: argparse.Namespace) -> int:
    root = root_from_cwd()
    escape_id = args.escape_id or __import__("os").environ.get("SWARM_ESCAPE_ID")
    ok, reason = sd.check_escape_hatch(root, flag=args.flag, escape_id=escape_id)
    print(json.dumps({"ok": ok, "reason": reason, "flag": args.flag}, indent=2))
    return 0 if ok else 1


def cmd_git_argv_check(args: argparse.Namespace) -> int:
    """D4: validate git argv for --no-verify (used by bin/gac/swarm-git)."""
    root = root_from_cwd()
    escape_id = args.escape_id or __import__("os").environ.get("SWARM_ESCAPE_ID")
    argv = list(args.argv or [])
    ok, reason = sd.check_git_argv_escape(root, argv, escape_id)
    print(
        json.dumps(
            {
                "ok": ok,
                "reason": reason,
                "has_no_verify": sd.argv_has_no_verify(argv),
                "flag": sd.no_verify_flag_for_argv(argv)
                if sd.argv_has_no_verify(argv)
                else None,
            },
            indent=2,
        )
    )
    return 0 if ok else 1


def cmd_window_start(_args: argparse.Namespace) -> int:
    root = root_from_cwd()
    payload = sd.start_conflict_window(root)
    print(json.dumps(payload, indent=2))
    return 0


def cmd_window_status(args: argparse.Namespace) -> int:
    root = root_from_cwd()
    status = sd.conflict_window_status(
        root,
        scan_orphans=not args.no_orphan_scan,
        emit_orphans=bool(args.emit_orphans),
    )
    print(json.dumps(status, indent=2, ensure_ascii=False))
    return 0


def cmd_inventory(_args: argparse.Namespace) -> int:
    root = root_from_cwd()
    reg = sd.load_registry(root)
    inv = {
        "registry": str(root / sd.DEFAULT_REGISTRY),
        "version": reg.get("version"),
        "gates": {
            k: {
                "id": (v or {}).get("id"),
                "name": (v or {}).get("name"),
                "entry": (v or {}).get("entry"),
                "check": (v or {}).get("check"),
            }
            for k, v in (reg.get("gates") or {}).items()
        },
        "escape_exemptions": [
            x.get("id") for x in (reg.get("escape_hatch_exemptions") or [])
        ],
        "cli": "bin/gac/swarm-discipline-cli.py",
        "core": "bin/gac/swarm_discipline.py",
    }
    print(json.dumps(inv, indent=2, ensure_ascii=False))
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("adr-claim")
    s.add_argument("--session", required=True)
    s.add_argument("--number", type=int, default=None)
    s.set_defaults(func=cmd_adr_claim)

    s = sub.add_parser("adr-check")
    s.add_argument("--file", required=True)
    s.add_argument("--session", default="")
    s.set_defaults(func=cmd_adr_check)

    s = sub.add_parser("branch-claim")
    s.add_argument("--session", required=True)
    s.add_argument("--branch", default=None)
    s.set_defaults(func=cmd_branch_claim)

    s = sub.add_parser("branch-check")
    s.add_argument("--branch", required=True)
    s.add_argument("--session", required=True)
    s.set_defaults(func=cmd_branch_check)

    s = sub.add_parser("branch-release")
    s.add_argument("--session", required=True)
    s.set_defaults(func=cmd_branch_release)

    s = sub.add_parser("claim-check")
    s.add_argument("--staged", action="store_true")
    s.add_argument("--paths", nargs="*", default=[])
    s.set_defaults(func=cmd_claim_check)

    s = sub.add_parser("escape-check")
    s.add_argument(
        "--flag",
        required=True,
        choices=["ci_local_skip", "no_verify_push", "no_verify_commit"],
    )
    s.add_argument("--escape-id", default=None)
    s.set_defaults(func=cmd_escape_check)

    s = sub.add_parser("git-argv-check", help="D4: check git argv for --no-verify")
    s.add_argument("--escape-id", default=None)
    s.add_argument("argv", nargs=argparse.REMAINDER, help="git argv after --")
    s.set_defaults(func=cmd_git_argv_check)

    s = sub.add_parser("window-start")
    s.set_defaults(func=cmd_window_start)

    s = sub.add_parser("window-status")
    s.add_argument(
        "--no-orphan-scan",
        action="store_true",
        help="skip advisory orphan_commit git scan",
    )
    s.add_argument(
        "--emit-orphans",
        action="store_true",
        help="record orphan hits into conflict events (affects M1 count)",
    )
    s.set_defaults(func=cmd_window_status)

    s = sub.add_parser("inventory")
    s.set_defaults(func=cmd_inventory)

    args = p.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
