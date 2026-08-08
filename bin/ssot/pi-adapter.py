#!/usr/bin/env python3
"""PI Adapter — PI框架深判引擎适配器 (ADR-0403 P5).

omo agent规则判断confidence不足时, 调PI做LLM深判.
如果PI不可用, 退化为纯规则判断(当前状态).

Usage:
  python3 bin/ssot/pi-adapter.py --evaluate '{"question":"...", "context":{}}'  # 深判
  python3 bin/ssot/pi-adapter.py --check                                         # PI可用性
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path

from _shared import ROOT, utc_now


def is_pi_available() -> bool:
    """Check if PI CLI is installed and accessible."""
    return shutil.which("pi") is not None


def deep_evaluate(question: str, context: dict) -> dict:
    """Call PI for deep evaluation when rule confidence is insufficient.

    If PI unavailable → return rule-fallback verdict.
    """
    if not is_pi_available():
        return {
            "status": "fallback",
            "verdict": "needs_human",
            "confidence": 0.5,
            "reasoning": "PI not available, falling back to rule-based judgment",
            "ts": utc_now(),
        }

    # Build PI prompt from question + context
    prompt = f"""You are an advisor agent in a self-governing system.
Question: {question}
Context: {json.dumps(context, ensure_ascii=False)[:500]}

Evaluate and respond with JSON: {{"verdict": "approve|reject|needs_human", "confidence": 0.0-1.0, "reasoning": "..."}}"""

    try:
        result = subprocess.run(
            ["pi", "--no-color", "-p", prompt],
            capture_output=True, text=True, timeout=30, check=False,
        )
        if result.returncode == 0 and result.stdout:
            # Try to parse PI output as JSON
            for line in result.stdout.strip().split("\n"):
                try:
                    return json.loads(line)
                except json.JSONDecodeError:
                    continue
            # If no JSON found, return raw output
            return {"status": "evaluated", "verdict": "needs_human", "confidence": 0.6, "reasoning": result.stdout[-200:], "ts": utc_now()}
    except Exception as exc:
        pass

    return {"status": "error", "verdict": "needs_human", "confidence": 0.3, "reasoning": "PI evaluation failed", "ts": utc_now()}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="check PI availability")
    parser.add_argument("--evaluate", default=None, help="JSON with question+context for deep evaluation")
    args = parser.parse_args(argv)

    if args.check:
        available = is_pi_available()
        print(json.dumps({"pi_available": available, "status": "ready" if available else "not_installed"}, ensure_ascii=False, indent=2))
        return 0 if available else 1

    if args.evaluate:
        data = json.loads(args.evaluate)
        result = deep_evaluate(data.get("question", ""), data.get("context", {}))
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
