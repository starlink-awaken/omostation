"""Models CLI — 模型定价与能力查询。

Usage:
    models list                 List all known models
    models list --cost          Show with pricing
    models cost <model_id>      Query specific model cost
    models search <capability>  Search by capability
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    from aetherforge.config import get_m1_dir
    M1_ENGINE_DIR = get_m1_dir("compute_engine")
except ImportError:
    M1_ENGINE_DIR = Path.home() / "Workspace" / "projects" / "ecos" / "src" / "ecos" / "ssot" / "mof" / "m1" / "compute_engine"


def cmd_list(show_cost: bool = False) -> int:
    """List models from pricing registry + gateway detection."""
    from llm_gateway.pricing import PricingRegistry
    from llm_gateway.detection import detect_backends

    pricing = PricingRegistry()

    if show_cost:
        # Detailed view with pricing
        all_models = pricing.list_all()
        if not all_models:
            print("No pricing data available.")
            return 0

        print(f"{'Model':30s} {'Provider':12s} {'Cost In':10s} {'Cost Out':10s} {'Context':8s} {'Capabilities'}")
        print("-" * 90)
        for mp in all_models:
            cost_in = f"${mp.cost_per_1k_input:.4f}" if mp.cost_per_1k_input >= 0 else "?"
            cost_out = f"${mp.cost_per_1k_output:.4f}" if mp.cost_per_1k_output >= 0 else "?"
            caps = ", ".join(mp.capabilities[:3])
            print(f"{mp.model_id:30s} {mp.provider:12s} {cost_in:10s} {cost_out:10s} {mp.context_window:>8d} {caps}")
        print(f"\nTotal: {len(all_models)} models across {len(pricing.get_stats()['providers'])} providers")
        return 0

    # Compact: show what's available via gateway + pricing
    providers = detect_backends()
    if not providers:
        print("No LLM providers available.")
        return 0

    print(f"{'Model':30s} {'Provider':12s} {'Cost':10s} {'Context':8s}")
    print("-" * 60)
    for p in providers:
        for model_name in p.available_models():
            cost = pricing.get_cost(model_name, p.provider_name)
            if cost.get("input") is not None:
                cost_str = f"${cost['input']:.4f}/${cost['output']:.4f}"
            else:
                cost_str = "?"
            mp = pricing.get_price(model_name, p.provider_name)
            ctx = str(mp.context_window) if mp else "?"
            print(f"{model_name:30s} {p.provider_name:12s} {cost_str:10s} {ctx:8s}")

    total_providers = len(providers)
    total_models = sum(len(p.available_models()) for p in providers)
    print(f"\nAvailable: {total_models} models from {total_providers} providers")
    return 0


def cmd_cost(model_id: str) -> int:
    """Query cost for a specific model."""
    from llm_gateway.detection import detect_backends, create_provider

    for p in detect_backends():
        if model_id in p.available_models():
            cost_in = cost_out = "unknown"
            if hasattr(p, "get_model_cost"):
                cost = p.get_model_cost(model_id)
                if cost:
                    cost_in = f"${cost.get('input', 0):.4f}"
                    cost_out = f"${cost.get('output', 0):.4f}"
            print(f"Model:     {model_id}")
            print(f"Provider:  {p.provider_name}")
            print(f"Cost In:   {cost_in}/1K tokens")
            print(f"Cost Out:  {cost_out}/1K tokens")
            return 0

    print(f"Model '{model_id}' not found.")
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="models", description="Model pricing & capability query")
    sub = parser.add_subparsers(dest="cmd")

    list_p = sub.add_parser("list", help="List models")
    list_p.add_argument("--cost", action="store_true", help="Show pricing")

    cost_p = sub.add_parser("cost", help="Query model cost")
    cost_p.add_argument("model_id", help="Model ID (e.g. gpt-4o)")

    args = parser.parse_args(argv)
    if args.cmd == "list":
        return cmd_list(show_cost=getattr(args, "cost", False))
    elif args.cmd == "cost":
        return cmd_cost(args.model_id)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
