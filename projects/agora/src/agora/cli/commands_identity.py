"""Identity CA commands: init, issue, verify, revoke, list."""

from __future__ import annotations

from agora.cli.errors import CLIError
from agora.cli.output import OutputFormatter


def cmd_identity(args):
    """Identity CA management."""
    from agora.auth.identity_ca import IdentityCA  # type: ignore[import-not-found]

    out = OutputFormatter(json_mode=getattr(args, "json", False))
    try:
        ca = IdentityCA()
        if args.identity_cmd == "init":
            ref = ca.init_ca()
            out.print_success(f"CA initialized: {ref}")
        elif args.identity_cmd == "issue":
            r = ca.issue_identity(
                args.subject_id,
                args.subject_type,
                tenant=args.tenant,
                expires_days=args.expires_days,
            )
            print(f"Issued: {r.get('subject_id', '?')}")
            print(f"   Type:     {r.get('subject_type', '?')}")
            print(f"   Issuer:   {r.get('issuer', '?')}")
            print(f"   Issued:   {r.get('issued_at', '?')}")
            print(f"   Expires:  {r.get('expires_at', '?')}")
            print(f"   Proof:    {r.get('proof_ref', '?')}")
            print(f"   Secret:   {r.get('proof_secret', '?')}")
            print(f"   Tenant:   {r.get('tenant', '?')}")
            print("   (SAVE secret - shown once)")
        elif args.identity_cmd == "verify":
            v = ca.verify_identity(args.subject_id)
            if v.get("valid"):
                print(f"Subject '{args.subject_id}' is VALID")
                ident = v.get("identity", {})
                print(f"   Type:     {ident.get('subject_type', '?')}")
                print(f"   Issuer:   {ident.get('issuer', '?')}")
            else:
                print(
                    f"Subject '{args.subject_id}' is INVALID: {v.get('reason', 'unknown')}"
                )
        elif args.identity_cmd == "revoke":
            ca.revoke_identity(args.subject_id)
            out.print_success(f"Revoked: {args.subject_id}")
        elif args.identity_cmd == "list":
            idents = ca.list_identities(tenant=args.tenant)
            for i in idents:
                status = "REVOKED" if i.get("revoked") else "active"
                print(
                    f"  {i.get('subject_id', '?'):30s} {i.get('subject_type', '?'):8s} {status:8s} t:{i.get('tenant', '?'):15s} {i.get('expires_at', '?')}"
                )
        return 0
    except CLIError as e:
        out.print_error(e.message, e.suggestion)
        return e.exit_code
    except Exception as e:
        out.print_error(str(e), "使用 'agora --help' 获取帮助")
        return 1
