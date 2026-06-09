"""Governance commands: key, audit, tenant, market, proto."""

from __future__ import annotations

import os
from pathlib import Path

from agora.cli.errors import CLIError
from agora.cli.output import OutputFormatter


def cmd_tenant(args):
    """Multi-tenant management."""
    from agora.auth.tenant import TenantManager  # type: ignore[import-not-found]

    out = OutputFormatter(json_mode=getattr(args, "json", False))
    try:
        tm = TenantManager()
        if args.tenant_cmd == "list":
            print("Tenants:\n")
            for t in tm.list_tenants():
                svcs = (
                    ", ".join(t.get("services", [])) if t.get("services") else "(all)"
                )
                print(
                    f"  {t.get('name', '?'):20s}  rate: {t.get('rate_limit', 0):4d} req/min  services: {svcs}"
                )
        elif args.tenant_cmd == "add":
            services = [s.strip() for s in args.services.split(",") if s.strip()]
            token = tm.add_tenant(args.name, services, args.rate_limit)
            print(f"Tenant '{args.name}' created")
            print(f"   Token: {token}")
        elif args.tenant_cmd == "remove":
            ok = tm.remove_tenant(args.name)
            print(
                f"{'OK' if ok else 'FAILED'} Tenant '{args.name}' {'removed' if ok else 'not found'}"
            )
        return 0
    except CLIError as e:
        out.print_error(e.message, e.suggestion)
        return e.exit_code
    except Exception as e:
        out.print_error(str(e), "使用 'agora --help' 获取帮助")
        return 1


def cmd_market(args):
    """MCP tool marketplace."""
    from agora.plugins.market.market import Market  # type: ignore[import-not-found]

    out = OutputFormatter(json_mode=getattr(args, "json", False))
    try:
        mkt = Market()
        if args.market_cmd == "list":
            print("MCP Tool Market\n")
            for s in mkt.list_all():
                print(f"  {s.get('name', '?'):20s}  {s.get('description', '')[:60]}")
                print(
                    f"  {'':20s}  repo: {s.get('repo', '?'):30s}  type: {s.get('type', '?')}"
                )
                print()
        elif args.market_cmd == "search":
            results = mkt.search(args.keyword)
            print(f"'{args.keyword}' -> {len(results)} results:\n")
            for s in results:
                print(f"  {s.get('name', '?'):20s}  {s.get('description', '')}")
                print(
                    f"  {'':20s}  repo: {s.get('repo', '?')}  tags: {', '.join(s.get('tags', []))}"
                )
                print()
        elif args.market_cmd == "install":
            print(f"Installing {args.name}...")
            result = mkt.install(args.name)
            print(f"{result.get('name', '?')} installed")
            print(f"   Entry: {result.get('entry', '?')}")
            print(f"   Type:  {result.get('type', '?')}")
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
            print(
                f"Published: {result.get('name', '?')} (repo: {result.get('repo', 'N/A')})"
            )
        return 0
    except CLIError as e:
        out.print_error(e.message, e.suggestion)
        return e.exit_code
    except Exception as e:
        out.print_error(str(e), "使用 'agora --help' 获取帮助")
        return 1


def cmd_key(args):
    """API Key management."""
    from agora.governance import KeyManager  # type: ignore[import-not-found]

    out = OutputFormatter(json_mode=getattr(args, "json", False))
    try:
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
                status = "REVOKED" if k.get("revoked") else "active"
                print(
                    f"  {k.get('key_id', '?'):20s} {k.get('name', '?'):20s} {status:8s} {', '.join(k.get('scopes', []))}"
                )
        elif args.key_cmd == "revoke":
            km.revoke(args.key_id)
            out.print_success(f"Revoked: {args.key_id}")
        elif args.key_cmd == "rotate":
            result = km.rotate(args.key_id)
            if result is None:
                out.print_error(
                    f"Key '{args.key_id}' not found",
                    suggestion="使用 'agora key list' 查看所有 Key",
                )
                return 1
            new_kid, new_secret = result
            print(f"Rotated: {new_kid}")
            print(f"New Secret: {new_secret}")
            print("Save this secret - it won't be shown again.")
        return 0
    except CLIError as e:
        out.print_error(e.message, e.suggestion)
        return e.exit_code
    except Exception as e:
        out.print_error(str(e), "使用 'agora --help' 获取帮助")
        return 1


def cmd_audit(args):
    """Audit log query."""
    from agora.audit import AuditLogger  # type: ignore[import-not-found]

    out = OutputFormatter(json_mode=getattr(args, "json", False))
    try:
        al = AuditLogger()
        if args.stats:
            s = al.stats(args.since)
            print(f"Total: {s.get('total', 0)} | Error rate: {s.get('error_rate', 0)}")
            for act, cnt in sorted(s.get("actions", {}).items()):
                print(f"  {act}: {cnt}")
        else:
            entries = al.query(args.actor, args.action, "", args.since, args.limit)
            for e in entries:
                print(
                    f"  [{e.get('timestamp', '?')}] {e.get('actor', '?'):20s} -> {e.get('action', '?'):25s} | {e.get('result', '?')}"
                )
        return 0
    except CLIError as e:
        out.print_error(e.message, e.suggestion)
        return e.exit_code
    except Exception as e:
        out.print_error(str(e), "使用 'agora --help' 获取帮助")
        return 1


def cmd_proto(args):
    """gRPC proto compilation tools."""
    out = OutputFormatter(json_mode=getattr(args, "json", False))
    try:
        if args.proto_cmd == "compile":
            try:
                from grpc_tools import protoc  # type: ignore[import-not-found]
            except ImportError:
                raise CLIError(
                    "grpcio-tools not installed",
                    suggestion="安装 grpcio-tools: pip install grpcio-tools",
                )

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
                out.print_success(
                    f"Compiled: {base}_pb2.py, {base}_pb2_grpc.py -> {out_dir}"
                )
            else:
                out.print_error(
                    f"protoc failed with exit code {ret}",
                    suggestion="检查 proto 文件语法",
                )
                return 1
        return 0
    except CLIError as e:
        out.print_error(e.message, e.suggestion)
        return e.exit_code
    except Exception as e:
        out.print_error(str(e), "使用 'agora --help' 获取帮助")
        return 1
