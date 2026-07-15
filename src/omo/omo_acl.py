"""omo acl — Scheme C 5c L2 host ACL plan/apply (ADR-0189).

  omo acl plan   [--workspace-root PATH] [--json]
  omo acl apply  [--workspace-root PATH] [--json]   # requires OMO_OS_ACL=1
  omo acl status [--workspace-root PATH] [--json]   # alias of lint path-acl doctor

Default is always dry-run. Apply only strips other-write / 0777 via chmod.
No setfacl, no chown, no launchd changes.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .omo_path_acl import (
    apply_acl_actions,
    cmd_lint_path_acl,
    os_acl_enabled,
    plan_acl_actions,
    run_path_acl_doctor,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="omo acl",
        description="Scheme C 5c L2: path ACL plan/apply (opt-in host mutation)",
    )
    sub = parser.add_subparsers(dest="command")

    for name, help_ in (
        ("plan", "Dry-run chmod plan for world-writable / 0777 surfaces"),
        ("apply", "Apply plan (requires OMO_OS_ACL=1)"),
        ("status", "L1 doctor report (same as omo lint path-acl)"),
    ):
        p = sub.add_parser(name, help=help_)
        p.add_argument("--workspace-root", default=".", help="Workspace root")
        p.add_argument("--json", action="store_true", help="JSON output")
        p.add_argument(
            "--profile",
            default=None,
            help="Override omo-path-acl.yaml (or OMO_PATH_ACL_PROFILE)",
        )
        if name == "apply":
            p.add_argument(
                "--yes",
                action="store_true",
                help="Confirm apply (still requires OMO_OS_ACL=1)",
            )

    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return 1

    root = args.workspace_root
    profile = getattr(args, "profile", None)
    profile_path = Path(profile) if profile else None

    if args.command == "status":
        return cmd_lint_path_acl(
            root, json_output=args.json, strict=False, profile=profile
        )

    if args.command == "plan":
        report = plan_acl_actions(root, profile_path=profile_path)
        if args.json:
            json.dump(report, sys.stdout, indent=2, ensure_ascii=False)
            sys.stdout.write("\n")
        else:
            print(
                f"[PLAN] actions={report['action_count']} "
                f"OMO_OS_ACL={report['omo_os_acl_enabled']} (dry-run only)"
            )
            for a in report["actions"]:
                print(
                    f"  {a['shell']}  # {a.get('from_mode')} → {a.get('to_mode')} "
                    f"({a.get('reason')})"
                )
            if not report["actions"]:
                print("  (no chmod actions needed)")
        return 0

    if args.command == "apply":
        if not os_acl_enabled():
            msg = {
                "error": "OMO_OS_ACL not set",
                "hint": "export OMO_OS_ACL=1 && omo acl apply --yes",
                "mutation": False,
            }
            if args.json:
                json.dump(msg, sys.stdout, indent=2)
                sys.stdout.write("\n")
            else:
                print("❌ apply refused: set OMO_OS_ACL=1 (opt-in host mutation)")
                print("   preview: omo acl plan --json")
            return 2
        if not getattr(args, "yes", False):
            plan = plan_acl_actions(root, profile_path=profile_path)
            if args.json:
                json.dump(
                    {
                        "error": "missing --yes",
                        "plan": plan,
                        "mutation": False,
                    },
                    sys.stdout,
                    indent=2,
                    ensure_ascii=False,
                )
                sys.stdout.write("\n")
            else:
                print("❌ apply requires --yes after reviewing plan")
                print(f"   actions queued: {plan['action_count']}")
                print("   omo acl plan --json")
            return 2
        report = apply_acl_actions(root, profile_path=profile_path, force=False)
        if args.json:
            json.dump(report, sys.stdout, indent=2, ensure_ascii=False)
            sys.stdout.write("\n")
        else:
            if report.get("error"):
                print(f"❌ {report['error']}")
                return 2
            print(
                f"[APPLY] ok={report.get('applied_ok', 0)} "
                f"fail={report.get('applied_fail', 0)} mutation={report.get('mutation')}"
            )
            for r in report.get("results") or []:
                mark = "✓" if r.get("ok") else "✗"
                print(f"  {mark} {r.get('path')} → {r.get('applied_mode', r.get('error'))}")
        return 0 if report.get("applied") and not report.get("applied_fail") else 1

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
