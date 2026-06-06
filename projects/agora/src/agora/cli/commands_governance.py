"""Governance commands: key, audit, tenant, market, proto."""

from __future__ import annotations

import os
from pathlib import Path


def cmd_tenant(args):
    """Multi-tenant management."""
    from agora.auth.tenant import TenantManager  # type: ignore[import-not-found]

    tm = TenantManager()
    if args.tenant_cmd == "list":
        print("Tenants:\n")
        for t in tm.list_tenants():
            svcs = ", ".join(t["services"]) if t["services"] else "(all)"
            print(f"  {t['name']:20s}  rate: {t['rate_limit']:4d} req/min  services: {svcs}")
    elif args.tenant_cmd == "add":
        services = [s.strip() for s in args.services.split(",") if s.strip()]
        token = tm.add_tenant(args.name, services, args.rate_limit)
        print(f"Tenant '{args.name}' created")
        print(f"   Token: {token}")
    elif args.tenant_cmd == "remove":
        ok = tm.remove_tenant(args.name)
        print(f"{'OK' if ok else 'FAILED'} Tenant '{args.name}' {'removed' if ok else 'not found'}")
    return 0


def cmd_market(args):
    """MCP tool marketplace."""
    from agora.market import Market  # type: ignore[import-not-found]

    mkt = Market()
    if args.market_cmd == "list":
        print("MCP Tool Market\n")
        for s in mkt.list_all():
            print(f"  {s['name']:20s}  {s['description'][:60]}")
            print(f"  {'':20s}  repo: {s['repo']:30s}  type: {s['type']}")
            print()
    elif args.market_cmd == "search":
        results = mkt.search(args.keyword)
        print(f"'{args.keyword}' -> {len(results)} results:\n")
        for s in results:
            print(f"  {s['name']:20s}  {s['description']}")
            print(f"  {'':20s}  repo: {s['repo']}  tags: {', '.join(s['tags'])}")
            print()
    elif args.market_cmd == "install":
        print(f"Installing {args.name}...")
        result = mkt.install(args.name)
        print(f"{result['name']} installed")
        print(f"   Entry: {result['entry']}")
        print(f"   Type:  {result['type']}")
        if result.get("port"):
            print(f"   Port:  {result['port']}")
    elif args.market_cmd == "publish":
        result = mkt.publish(
            args.name,
            repo=args.repo,
            description=args.description,
            entry=args.entry,
            svc_type=args.type,
        )
        print(f"Published: {result['name']} (repo: {result.get('repo', 'N/A')})")
    return 0


def cmd_key(args):
    """API Key management."""
    from agora.governance import KeyManager  # type: ignore[import-not-found]

    km = KeyManager()
    if args.key_cmd == "create":
        scopes = [s.strip() for s in args.scopes.split(",") if s.strip()]
        kid, secret = km.create_key(args.name, scopes, args.tenant, args.expires)
        print(f"Created: {kid}")
        print(f"Secret: {secret}")
        print("Save this secret - it won't be shown again.")
    elif args.key_cmd == "list":
        keys = km.list_keys(args.tenant if hasattr(args, "tenant") else "")
        for k in keys:
            status = "REVOKED" if k["revoked"] else "active"
            print(f"  {k['key_id']:20s} {k['name']:20s} {status:8s} {', '.join(k['scopes'])}")
    elif args.key_cmd == "revoke":
        km.revoke(args.key_id)
        print(f"Revoked: {args.key_id}")
    elif args.key_cmd == "rotate":
        result = km.rotate(args.key_id)
        if result is None:
            print(f"Error: Key '{args.key_id}' not found")
            return 1
        new_kid, new_secret = result
        print(f"Rotated: {new_kid}")
        print(f"New Secret: {new_secret}")
        print("Save this secret - it won't be shown again.")


def cmd_audit(args):
    """Audit log query."""
    from agora.audit import AuditLogger  # type: ignore[import-not-found]

    al = AuditLogger()
    if args.stats:
        s = al.stats(args.since)
        print(f"Total: {s['total']} | Error rate: {s['error_rate']}")
        for act, cnt in sorted(s["actions"].items()):
            print(f"  {act}: {cnt}")
    else:
        entries = al.query(args.actor, args.action, "", args.since, args.limit)
        for e in entries:
            print(f"  [{e['timestamp']}] {e['actor']:20s} -> {e['action']:25s} | {e['result']}")


def cmd_proto(args):
    """gRPC proto compilation tools."""
    if args.proto_cmd == "compile":
        try:
            from grpc_tools import protoc  # type: ignore[import-not-found]
        except ImportError:
            print("Error: grpcio-tools not installed. Run: pip install grpcio-tools")
            return

        proto_file = Path(args.proto_file).resolve()
        out_dir = Path(args.out).resolve()
        os.makedirs(out_dir, exist_ok=True)
        ret = protoc.main(
            [
                "protoc",
                f"-I{proto_file.parent}",
                f"--python_out={out_dir}",
                f"--grpc_python_out={out_dir}",
                str(proto_file.name),
            ]
        )
        if ret == 0:
            base = proto_file.stem
            print(f"Compiled: {base}_pb2.py, {base}_pb2_grpc.py -> {out_dir}")
        else:
            print(f"protoc failed with exit code {ret}")
