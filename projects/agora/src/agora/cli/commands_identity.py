"""Identity CA commands: init, issue, verify, revoke, list."""

from __future__ import annotations


def cmd_identity(args):
    """Identity CA management."""
    from agora.auth.identity_ca import IdentityCA  # type: ignore[import-not-found]

    ca = IdentityCA()
    if args.identity_cmd == "init":
        ref = ca.init_ca()
        print(f"CA initialized: {ref}")
    elif args.identity_cmd == "issue":
        r = ca.issue_identity(
            args.subject_id,
            args.subject_type,
            tenant=args.tenant,
            expires_days=args.expires_days,
        )
        print(f"Issued: {r['subject_id']}")
        print(f"   Type:     {r['subject_type']}")
        print(f"   Issuer:   {r['issuer']}")
        print(f"   Issued:   {r['issued_at']}")
        print(f"   Expires:  {r['expires_at']}")
        print(f"   Proof:    {r['proof_ref']}")
        print(f"   Secret:   {r['proof_secret']}")
        print(f"   Tenant:   {r['tenant']}")
        print("   (SAVE secret - shown once)")
    elif args.identity_cmd == "verify":
        v = ca.verify_identity(args.subject_id)
        if v["valid"]:
            print(f"Subject '{args.subject_id}' is VALID")
            print(f"   Type:     {v['identity']['subject_type']}")
            print(f"   Issuer:   {v['identity']['issuer']}")
        else:
            print(f"Subject '{args.subject_id}' is INVALID: {v['reason']}")
    elif args.identity_cmd == "revoke":
        ca.revoke_identity(args.subject_id)
        print(f"Revoked: {args.subject_id}")
    elif args.identity_cmd == "list":
        idents = ca.list_identities(tenant=args.tenant)
        for i in idents:
            status = "REVOKED" if i["revoked"] else "active"
            print(f"  {i['subject_id']:30s} {i['subject_type']:8s} {status:8s} t:{i['tenant']:15s} {i['expires_at']}")
    return 0
