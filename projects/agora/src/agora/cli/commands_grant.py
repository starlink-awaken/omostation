"""Agora grant CLI — 签发/吊销/查询 CapabilityGrant (Phase 9 / T127).

集成: agora grant create/revoke/list/check
"""

import json

from agora.cli.errors import CLIError
from agora.cli.output import OutputFormatter


def cmd_grant(args):
    """Grant 子命令分发：create / revoke / list / check。"""
    from agora.auth.authorizer import Authorizer  # type: ignore[import-not-found]

    out = OutputFormatter(json_mode=getattr(args, 'json', False))
    try:
        az = Authorizer()
        if args.grant_cmd == "create":
            constraints = {}
            if hasattr(args, "constraints") and args.constraints:
                constraints = json.loads(args.constraints) if isinstance(args.constraints, str) else args.constraints
            r = az.create_grant(
                subject=args.subject,
                capability=args.capability,
                resource_scope=getattr(args, "scope", ""),
                constraints=constraints,
            )
            print(f"Grant created: {r.get('grant_id', '?')}")
            print(f"  {r.get('subject', '?')} -> {r.get('capability', '?')}")
        elif args.grant_cmd == "revoke":
            az.revoke_grant(args.grant_id)
            out.print_success(f"Revoked: {args.grant_id}")
        elif args.grant_cmd == "list":
            subject = getattr(args, "subject", "")
            grants = az.list_grants(subject)
            if not grants:
                out.print_info("没有找到授权记录。")
                return 0
            for g in grants:
                status = "REVOKED" if g.get("revoked") else "active"
                print(f"  {g.get('grant_id', '?'):25s} {g.get('subject', '?'):20s} {g.get('capability', '?'):20s} {status}")
            return 0
        elif args.grant_cmd == "check":
            subject = getattr(args, "subject", "")
            tool = getattr(args, "tool", "")
            cost = getattr(args, "cost", 0.0)
            r = az.check_call(subject, tool, cost)
            label = "ALLOWED" if r.get("allowed") else "DENIED"
            print(f"{label}: {r.get('reason', '')}")
        return 0
    except CLIError as e:
        out.print_error(e.message, e.suggestion)
        return e.exit_code
    except Exception as e:
        out.print_error(str(e), "使用 'agora --help' 获取帮助")
        return 1
