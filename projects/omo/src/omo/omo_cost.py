#!/usr/bin/env python3
"""OMO cost CLI — LLM token usage and cost estimation.

Reads cost records from ~/.runtime/data/llm_cost.jsonl.
Records written by llm-gateway hook in providers/base.py.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path


COST_FILE = Path(os.environ.get("RUNTIME_HOME", str(Path.home() / "runtime"))) / "data" / "llm_cost.jsonl"

# Approximate cost per 1K tokens (USD), updated 2026-06
MODEL_COST_MAP: dict[str, dict[str, float]] = {
    "gpt-4": {"input": 0.03, "output": 0.06},
    "gpt-4o": {"input": 0.01, "output": 0.03},
    "gpt-4o-mini": {"input": 0.0015, "output": 0.006},
    "claude-3-opus": {"input": 0.015, "output": 0.075},
    "claude-3-sonnet": {"input": 0.003, "output": 0.015},
    "claude-3-haiku": {"input": 0.00025, "output": 0.00125},
    "deepseek-v4": {"input": 0.002, "output": 0.008},
    "deepseek-v4-flash": {"input": 0.0005, "output": 0.002},
    "gemini-1.5-pro": {"input": 0.0035, "output": 0.0105},
    "ollama": {"input": 0.0, "output": 0.0},  # local, free
}


def _estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    from omo.omo_quota import get_cached_rates_and_quota
    
    model_lower = model.lower()
    
    # Try dynamic rates first
    dynamic_data = get_cached_rates_and_quota()
    rates = dynamic_data.get("rates", {}).get(model_lower)
    
    if not rates:
        rates = MODEL_COST_MAP.get(model_lower)
        
    if not rates:
        # Try prefix matching in dynamic rates
        for key, val in dynamic_data.get("rates", {}).items():
            if model_lower.startswith(key):
                rates = val
                break
        
    if not rates:
        # Try prefix matching in static rates
        for key, val in MODEL_COST_MAP.items():
            if model_lower.startswith(key):
                rates = val
                break
                
    if not rates:
        rates = {"input": 0.002, "output": 0.008}  # fallback: ~deepseek rates
        
    input_cost = (input_tokens / 1000) * rates["input"]
    output_cost = (output_tokens / 1000) * rates["output"]
    return round(input_cost + output_cost, 6)


def cmd_cost_estimate(period_days: int, model_filter: str | None) -> int:
    """Estimate LLM costs over a period."""
    if not COST_FILE.exists():
        print("ℹ️  No cost data available. LLM calls are not being logged.")
        print("   To enable: ensure llm-gateway writes to:")
        print(f"   {COST_FILE}")
        return 0

    cutoff = datetime.now(timezone.utc) - timedelta(days=period_days)
    records = []
    for line in COST_FILE.read_text().strip().split("\n"):
        if not line.strip():
            continue
        try:
            r = json.loads(line)
            ts = r.get("timestamp", r.get("ts", ""))
            if ts:
                r_dt = datetime.fromisoformat(ts)
                if r_dt >= cutoff:
                    records.append(r)
        except (json.JSONDecodeError, ValueError):
            pass

    if not records:
        print(f"No cost records in the last {period_days} day(s)")
        return 0

    total_input = sum(r.get("input_tokens", 0) for r in records)
    total_output = sum(r.get("output_tokens", 0) for r in records)
    total_cost = 0.0
    model_stats: dict[str, dict] = {}

    for r in records:
        model = r.get("model", "unknown")
        inp = r.get("input_tokens", 0)
        out = r.get("output_tokens", 0)
        cost = r.get("cost", _estimate_cost(model, inp, out))
        total_cost += cost
        if model not in model_stats:
            model_stats[model] = {"calls": 0, "input": 0, "output": 0, "cost": 0.0}
        model_stats[model]["calls"] += 1
        model_stats[model]["input"] += inp
        model_stats[model]["output"] += out
        model_stats[model]["cost"] += cost

    # Filter by model if requested
    if model_filter:
        model_stats = {k: v for k, v in model_stats.items() if model_filter.lower() in k.lower()}

    if not model_stats:
        print(f"No records matching model filter '{model_filter}'")
        return 0

    total_calls = sum(v["calls"] for v in model_stats.values())

    print(f"LLM Cost Report — Last {period_days} day(s)")
    print(f"Total records: {total_calls}")
    print(f"Total tokens:  {total_input:,} in / {total_output:,} out")
    print(f"Total cost:    ${total_cost:.6f}")
    print()

    print(f"{'MODEL':25s} {'CALLS':>6s} {'INPUT':>8s} {'OUTPUT':>8s} {'COST':>10s}")
    print("-" * 60)
    for model, stats in sorted(model_stats.items(), key=lambda x: -x[1]["cost"]):
        inp_k = f"{stats['input']:,}"
        out_k = f"{stats['output']:,}"
        cost_s = f"${stats['cost']:.4f}"
        print(f"{model[:24]:25s} {stats['calls']:6d} {inp_k:>8s} {out_k:>8s} {cost_s:>10s}")
    print("-" * 60)
    print(f"{'TOTAL':25s} {total_calls:6d} {total_input:>8,} {total_output:>8,} ${total_cost:.4f}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="omo cost", description="OMO LLM cost estimation")
    sub = parser.add_subparsers(dest="command")
    ce = sub.add_parser("estimate", help="Estimate LLM costs")
    ce.add_argument("--period", "-p", type=int, default=7, help="Days to look back (default: 7)")
    ce.add_argument("--model", "-m", help="Filter by model name")
    args = parser.parse_args(argv)
    if args.command == "estimate":
        return cmd_cost_estimate(args.period, args.model)
    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
