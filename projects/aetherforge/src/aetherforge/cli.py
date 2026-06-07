#!/usr/bin/env python3
"""AetherForge 统一 CLI — 算力网格 + LLM 网关 + 群体智能引擎。

Usage:
    aetherforge gateway list              List LLM models
    aetherforge gateway generate <prompt>  Generate text
    aetherforge mesh list                 List compute nodes
    aetherforge mesh status               Node health
    aetherforge mesh health               Run health checks
    aetherforge mesh topology-scan        Discover nodes
    aetherforge mesh generate <prompt>    Generate via best node
    aetherforge mesh cost                 Cost report
    aetherforge swarm ...                 Swarm commands (TODO)
"""

from __future__ import annotations

import argparse
import sys


def cmd_gateway(argv: list[str]) -> int:
    """Delegate to gateway CLI."""
    from llm_gateway.cli import main as gateway_main

    return gateway_main(argv if argv else ["--help"])


def cmd_mesh(argv: list[str]) -> int:
    """Delegate to mesh CLI."""
    from compute_mesh.api.cli import main as mesh_main

    return mesh_main(argv if argv else ["--help"])


def cmd_swarm(argv: list[str]) -> int:
    """Swarm CLI (TBD)."""
    print("⚙️  Swarm CLI: not yet implemented")
    print("   Available modules: auctioneer, lifecycle, economy, event-bus, dag")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="aetherforge",
        description="AetherForge — 算力网格 + LLM 网关 + 群体智能引擎",
    )
    sub = parser.add_subparsers(dest="domain")

    for name, help_text in [("gateway", "LLM Gateway operations"),
                             ("mesh", "Compute Mesh operations"),
                             ("swarm", "Swarm Engine operations (TODO)")]:
        p = sub.add_parser(name, help=help_text)
        p.add_argument("subcommand", nargs="*", help=f"{name} subcommand + args")

    args = parser.parse_args(argv)

    if args.domain == "gateway":
        return cmd_gateway(args.subcommand)
    elif args.domain == "mesh":
        return cmd_mesh(args.subcommand)
    elif args.domain == "swarm":
        return cmd_swarm(args.subcommand or [])
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
