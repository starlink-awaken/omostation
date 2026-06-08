#!/usr/bin/env python3
"""llm-gateway CLI — unified LLM access from the command line.

Usage:
    llm-gateway list                     List available models
    llm-gateway generate <prompt>        Generate from prompt
    llm-gateway generate -m deepseek "Explain..."
    llm-gateway mcp                      Start MCP server
    llm-gateway serve --port 9090        Start HTTP server
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .detection import create_provider, detect_backends
from .provider import LLMRequest
from .registry import ModelRegistry
from .scheduler import ModelScheduler
from .ssot_loader import load_ssot_models


def cmd_list(use_ssot: bool = False, show_quota: bool = False, show_cost: bool = False) -> int:
    if show_quota:
        return _cmd_list_quota()
    if show_cost:
        return _cmd_list_cost()
    if use_ssot:
        m1_dir = Path.home() / "Workspace" / "projects" / "ecos" / "src" / "ecos" / "ssot" / "mof" / "m1" / "compute_engine"
        if m1_dir.exists():
            import asyncio
            reg = ModelRegistry()
            load_ssot_models(reg, str(m1_dir))
            asyncio.run(reg.refresh())
            sched = ModelScheduler(reg)
            loaded = sched.load_quota_rates()
            models = reg.list_models()
            print(f"L0 M1 compute_engine ({len(models)} models, {loaded} with real prices):")
            for m in models:
                cost = m.cost_per_1k_tokens
                c_in = cost.get("input", "?")
                c_out = cost.get("output", "?")
                print(f"  🟢 {m.id:50s} in=${c_in} out=${c_out}")
            return 0

    providers = detect_backends()
    if not providers:
        print("No LLM backends available.")
        return 1
    print(f"Found {len(providers)} provider(s):")
    for p in providers:
        models = p.available_models()
        status = "🟢" if p.is_available() else "🔴"
        print(f"  {status} {p.provider_name}: {', '.join(models[:3])}")
    return 0


def cmd_generate(prompt: str, model: str | None, provider_name: str | None) -> int:
    if provider_name:
        providers = [create_provider(provider_name)]
    else:
        providers = detect_backends()
    if not providers:
        print("No LLM backends available.", file=sys.stderr)
        return 1
    provider = providers[0]
    if not provider.is_available():
        print(f"Provider {provider.provider_name} not available.", file=sys.stderr)
        return 1
    req = LLMRequest(prompt=prompt, model=model or provider.default_model)
    try:
        resp = provider.complete(req)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    print(resp.content)
    if resp.input_tokens:
        print(f"\n[{resp.model}] {resp.input_tokens} in / {resp.output_tokens} out", file=sys.stderr)
    return 0


def cmd_mcp() -> int:
    from .mcp_server import main as mcp_main

    mcp_main()
    return 0


def _cmd_list_quota() -> int:
    """显示所有 Provider 的配额状态。"""
    from .quota_engine import QuotaEngine
    qe = QuotaEngine()
    qe.start()
    qe.wait_ready(timeout=10)
    summary = qe.get_summary()
    print(f"{'Provider':18s} {'Key':6s} {'Online':7s} {'Quota':10s} {'Source':8s}")
    print("-" * 55)
    for p in summary["providers"]:
        key = "✅" if p["has_key"] else "—"
        online = "✅" if p.get("online") else ("—" if p["has_key"] else "  ")
        q = f"{p['quota_pct']:.0f}%" if p["quota_pct"] is not None else "—"
        src = p["quota_source"] if p["quota_source"] else "—"
        print(f"  {p['provider']:16s} {key:6s} {online:7s} {q:10s} {src:8s}")
    print(f"\ncodexbar: {'✅' if summary['codexbar_available'] else '❌'}")
    print(f"{summary['available']}/{summary['total']} available")
    qe.stop()
    return 0


def _cmd_list_cost() -> int:
    """显示所有模型的定价。"""
    from .pricing import PricingRegistry
    pricing = PricingRegistry()
    all_prices = pricing.list_all()
    print(f"{'Model':30s} {'Provider':12s} {'Cost In':10s} {'Cost Out':10s} {'Context':8s}")
    print("-" * 70)
    for mp in all_prices:
        ci = f"${mp.cost_per_1k_input:.4f}" if mp.cost_per_1k_input >= 0 else "?"
        co = f"${mp.cost_per_1k_output:.4f}" if mp.cost_per_1k_output >= 0 else "?"
        print(f"{mp.model_id:30s} {mp.provider:12s} {ci:10s} {co:10s} {mp.context_window:>8d}")
    print(f"\nTotal: {len(all_prices)} models")
    return 0


def cmd_serve(port: int) -> int:
    """Start a simple HTTP server for LLM generation."""
    from .http_server import serve

    serve(port)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="llm-gateway", description="Unified LLM Gateway CLI")
    sub = parser.add_subparsers(dest="cmd")

    list_p = sub.add_parser("list", help="List available models")
    list_p.add_argument("--ssot", action="store_true", help="从 L0 M1 节点加载")
    list_p.add_argument("--quota", "-q", action="store_true", help="显示配额大盘")
    list_p.add_argument("--cost", "-c", action="store_true", help="显示模型定价")

    gen = sub.add_parser("generate", help="Generate LLM response")
    gen.add_argument("prompt")
    gen.add_argument("--model", "-m", help="Model name")
    gen.add_argument("--provider", "-p", help="Provider name (ollama, openai, ...)")
    gen.add_argument("--strategy", "-s", default="balanced",
                    choices=["balanced", "cost_first", "speed_first", "quota_first"],
                    help="Routing strategy")

    mcp_p = sub.add_parser("mcp", help="Start MCP server (stdio)")
    mcp_p.add_argument("--ssot", action="store_true", help="从 L0 M1 节点加载模型")

    srv = sub.add_parser("serve", help="Start HTTP server")
    srv.add_argument("--port", "-p", type=int, default=9290)

    args = parser.parse_args(argv)
    if args.cmd == "list":
        return cmd_list(use_ssot=getattr(args, "ssot", False),
                       show_quota=getattr(args, "quota", False),
                       show_cost=getattr(args, "cost", False))
    elif args.cmd == "generate":
        return cmd_generate(args.prompt, args.model, args.provider,
                           strategy=getattr(args, "strategy", "balanced"))
    elif args.cmd == "mcp":
        return cmd_mcp()
    elif args.cmd == "serve":
        return cmd_serve(args.port)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
