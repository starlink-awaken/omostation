"""omo acl — Scheme C 5c L2 host ACL plan/apply (ADR-0189 / ADR-0196 / ADR-0198).

  omo acl plan   [--workspace-root PATH] [--json] [--acl]
  omo acl apply  [--workspace-root PATH] [--json] [--yes] [--acl]
  omo acl status [--workspace-root PATH] [--json]

Default plan is dry-run. Apply requires OMO_OS_ACL=1 and --yes.
``apply --acl`` runs named ACE (setfacl / chmod +a) + chmod o-w (ADR-0198).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .omo_path_acl import (
    apply_acl_actions,
    apply_named_acl_actions,
    cmd_lint_path_acl,
    os_acl_enabled,
    plan_acl_actions,
    plan_named_acl_script,
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
        if name == "plan":
            p.add_argument(
                "--acl",
                action="store_true",
                help="Also emit named ACE script (setfacl/chmod+a) dry-run (ADR-0196)",
            )
        if name == "apply":
            p.add_argument(
                "--yes",
                action="store_true",
                help="Confirm apply (still requires OMO_OS_ACL=1)",
            )
            p.add_argument(
                "--acl",
                action="store_true",
                help="Also apply named ACE (setfacl/chmod+a) after chmod plan (ADR-0198)",
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
        if getattr(args, "acl", False):
            named = plan_named_acl_script(root, profile_path=profile_path)
            report["named_acl"] = named
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
            if report.get("named_acl"):
                na = report["named_acl"]
                print(
                    f"\n[PLAN --acl] platform={na.get('platform')} "
                    f"commands={na.get('command_count')} (script dry-run)"
                )
                print(na.get("script") or "")
        return 0

    if args.command == "apply":
        want_acl = getattr(args, "acl", False)
        if not os_acl_enabled():
            msg = {
                "error": "OMO_OS_ACL not set",
                "hint": "export OMO_OS_ACL=1 && omo acl apply --yes"
                + (" --acl" if want_acl else ""),
                "mutation": False,
            }
            if args.json:
                json.dump(msg, sys.stdout, indent=2)
                sys.stdout.write("\n")
            else:
                print("❌ apply refused: set OMO_OS_ACL=1 (opt-in host mutation)")
                print(
                    "   preview: omo acl plan --json" + (" --acl" if want_acl else "")
                )
            return 2
        if not getattr(args, "yes", False):
            plan = plan_acl_actions(root, profile_path=profile_path)
            if want_acl:
                plan["named_acl"] = plan_named_acl_script(
                    root, profile_path=profile_path
                )
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
                print(f"   chmod actions queued: {plan['action_count']}")
                if want_acl and plan.get("named_acl"):
                    print(
                        f"   named ACE commands: {plan['named_acl'].get('command_count')}"
                    )
                print("   omo acl plan --json" + (" --acl" if want_acl else ""))
            return 2

        report = apply_acl_actions(root, profile_path=profile_path, force=False)
        if want_acl:
            named = apply_named_acl_actions(
                root, profile_path=profile_path, force=False
            )
            report["named_acl_apply"] = named
            # roll up fail counts
            report["applied_fail"] = int(report.get("applied_fail") or 0) + int(
                named.get("applied_fail") or 0
            )
            report["applied_ok"] = int(report.get("applied_ok") or 0) + int(
                named.get("applied_ok") or 0
            )
            if named.get("mutation"):
                report["mutation"] = True

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
                print(
                    f"  {mark} {r.get('path')} → "
                    f"{r.get('applied_mode', r.get('error', r.get('op', '')))}"
                )
            if want_acl and report.get("named_acl_apply"):
                na = report["named_acl_apply"]
                print(
                    f"[APPLY --acl] platform={na.get('platform')} "
                    f"ok={na.get('applied_ok')} fail={na.get('applied_fail')}"
                )
                for r in na.get("results") or []:
                    if r.get("skipped") and r.get("ok"):
                        continue
                    mark = "✓" if r.get("ok") else "✗"
                    print(
                        f"  {mark} {r.get('op')} {r.get('path')} "
                        f"{r.get('subject', '')} {r.get('error') or r.get('reason') or ''}"
                    )
        fail = int(report.get("applied_fail") or 0)
        return 0 if report.get("applied") and fail == 0 else 1

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
