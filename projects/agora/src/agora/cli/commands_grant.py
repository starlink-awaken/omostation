"""Agora grant CLI — 签发/吊销/查询 CapabilityGrant (Phase 9 / T127).

集成: agora grant create/revoke/list/check
"""

import json


def cmd_grant(args):
    """Grant 子命令分发：create / revoke / list / check。"""
    from agora.auth.authorizer import Authorizer  # type: ignore[import-not-found]

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
        print(f"Grant created: {r['grant_id']}")
        print(f"  {r['subject']} -> {r['capability']}")
    elif args.grant_cmd == "revoke":
        az.revoke_grant(args.grant_id)
        print(f"Revoked: {args.grant_id}")
    elif args.grant_cmd == "list":
        subject = getattr(args, "subject", "")
        grants = az.list_grants(subject)
        if not grants:
            print("No grants found.")
            return
        for g in grants:
            status = "REVOKED" if g["revoked"] else "active"
            print(f"  {g['grant_id']:25s} {g['subject']:20s} {g['capability']:20s} {status}")
    elif args.grant_cmd == "check":
        subject = getattr(args, "subject", "")
        tool = getattr(args, "tool", "")
        cost = getattr(args, "cost", 0.0)
        r = az.check_call(subject, tool, cost)
        label = "ALLOWED" if r["allowed"] else "DENIED"
        print(f"{label}: {r.get('reason', '')}")
