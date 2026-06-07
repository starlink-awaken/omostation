"""Agora CLI — command-line interface for the service convergence hub."""

from __future__ import annotations

import os
import sys

from agora.cli.parser import build_parser  # type: ignore[import-not-found]


def main():
    """Main entry point — build parser, parse args, dispatch."""
    parser = build_parser()
    args = parser.parse_args()

    if getattr(args, 'version', False):
        from agora import __version__
        print(f"agora v{__version__}")
        return 0

    if args.command is None:
        parser.print_help()
        return 0

    # Commands wired via set_defaults(func=...) in parser
    if hasattr(args, "func"):
        return args.func(args)

    # Dispatch to command modules
    if args.command == "discover":
        from agora.cli.commands_discover import cmd_discover  # type: ignore[import-not-found]

        return cmd_discover(args)

    if args.command == "sync":
        from agora.cli.commands_discover import cmd_sync

        return cmd_sync(args)

    if args.command == "converge":
        from agora.cli.commands_discover import cmd_sync

        return cmd_sync(args)

    if args.command == "search":
        from agora.cli.commands_registry import cmd_search  # type: ignore[import-not-found]

        return cmd_search(args)

    if args.command == "info":
        from agora.cli.commands_registry import cmd_info

        return cmd_info(args)

    if args.command == "stats":
        from agora.cli.commands_registry import cmd_stats

        return cmd_stats(args)

    if args.command == "register":
        from agora.cli.commands_registry import cmd_register

        return cmd_register(args)

    elif args.command == "unregister":
        from agora.cli.commands_registry import cmd_unregister

        return cmd_unregister(args)

    elif args.command == "list":
        from agora.cli.commands_registry import cmd_list

        return cmd_list(args)

    elif args.command == "health":
        from agora.cli.commands_registry import cmd_health

        return cmd_health(args)

    elif args.command == "config":
        from agora.cli.commands_registry import cmd_config

        return cmd_config(args)

    elif args.command == "route":
        from agora.cli.commands_routes import cmd_route  # type: ignore[import-not-found]

        return cmd_route(args)

    elif args.command == "routes":
        from agora.cli.commands_routes import cmd_routes

        return cmd_routes(args)

    elif args.command == "instance":
        if args.instance_cmd == "add":
            from agora.cli.commands_routes import cmd_instance

            return cmd_instance(args)
        else:
            from agora.cli.commands_instance import cmd_instance  # type: ignore[import-not-found]

            return cmd_instance(args)

    elif args.command == "mcp":
        from agora.cli.commands_mcp import cmd_mcp  # type: ignore[import-not-found]

        return cmd_mcp(args)

    elif args.command == "web":
        from agora.cli.commands_mcp import cmd_web

        return cmd_web(args)

    elif args.command == "init":
        from agora.cli.commands_mcp import cmd_init

        return cmd_init(args)

    elif args.command == "completion":
        from agora.cli.commands_mcp import cmd_completion

        return cmd_completion(args)

    elif args.command == "pipeline":
        from agora.cli.commands_pipeline import cmd_pipeline  # type: ignore[import-not-found]

        return cmd_pipeline(args)

    elif args.command == "pipelines":
        from agora.cli.commands_pipeline import cmd_pipelines

        return cmd_pipelines(args)

    elif args.command == "pipeline-define":
        from agora.cli.commands_pipeline import cmd_pipeline_define

        return cmd_pipeline_define(args)

    elif args.command == "key":
        from agora.cli.commands_governance import cmd_key  # type: ignore[import-not-found]

        return cmd_key(args)

    elif args.command == "audit":
        from agora.cli.commands_governance import cmd_audit

        return cmd_audit(args)

    elif args.command == "tenant":
        from agora.cli.commands_governance import cmd_tenant

        return cmd_tenant(args)

    elif args.command == "market":
        from agora.cli.commands_governance import cmd_market

        return cmd_market(args)

    elif args.command == "repo":
        from agora.cli.commands_repo import cmd_repo  # type: ignore[import-not-found]

        return cmd_repo(args)

    elif args.command == "proto":
        from agora.cli.commands_governance import cmd_proto

        return cmd_proto(args)

    elif args.command == "transitions":
        from agora.cli.commands_a2a import cmd_transitions  # type: ignore[import-not-found]

        return cmd_transitions(args)

    elif args.command == "a2a":
        from agora.cli.commands_a2a import cmd_a2a

        cmd_a2a(args)

    elif args.command == "agent-card":
        from agora.cli.commands_a2a import cmd_agent_card

        cmd_agent_card(args)

    elif args.command == "event":
        from agora.cli.commands_a2a import cmd_event

        cmd_event(args)

    elif args.command == "enforce":
        from agora.cli.commands_authorizer import cmd_enforce  # type: ignore[import-not-found]

        return cmd_enforce(args)

    elif args.command == "accounting":
        from agora.cli.commands_accounting import (  # type: ignore[import-not-found]
            cmd_accounting_quota,
            cmd_accounting_report,
            cmd_accounting_top,
        )

        if args.accounting_cmd == "top":
            return cmd_accounting_top(args)
        elif args.accounting_cmd == "report":
            return cmd_accounting_report(args)
        elif args.accounting_cmd == "quota":
            return cmd_accounting_quota(args)
        else:
            print("Usage: agora accounting {top|report|quota} [options]")
            print("  top      --period day|week|month|all  --limit N")
            print("  report   --period day|week|month|all")
            print("  quota    --caller <name> [--quota USD]")
            return 0

    elif args.command == "pallas":
        from agora.cli.commands_pallas import dispatch_pallas  # type: ignore[import-not-found]

        return dispatch_pallas(args)

    elif args.command == "identity":
        from agora.cli.commands_identity import cmd_identity  # type: ignore[import-not-found]

        return cmd_identity(args)

    elif args.command == "grant":
        from agora.cli.commands_grant import cmd_grant  # type: ignore[import-not-found]

        return cmd_grant(args)

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nInterrupted.")
        sys.exit(130)
    except Exception as e:
        from agora.cli.errors import CLIError
        import traceback
        print(f"\nError: {e}", file=sys.stderr)
        print("  Hint: Run 'agora config' to check setup, or 'agora init' to re-run setup.", file=sys.stderr)
        if os.environ.get("AGORA_DEBUG"):
            traceback.print_exc()
        sys.exit(1)
