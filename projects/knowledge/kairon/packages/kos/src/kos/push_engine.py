"""Push Engine — 从 Pattern 自动生成推送规则

读取 pattern_learner 的输出 → 生成 hermes-ops 告警规则 → 触发推送
"""

import json
import os
import subprocess
import textwrap
from pathlib import Path

PUSH_SCRIPT = Path.home() / ".hermes" / "scripts" / "ops-push"


def pattern_to_rule(pattern: dict) -> dict:
    """Convert a Pattern to a hermes-ops alert rule"""
    rule = {
        "name": f"auto_{pattern['type']}_{abs(hash(pattern['description'])) % 10000}",
        "condition": f"pattern match: {pattern['description']}",
        "severity": "INFO" if pattern.get("confidence", 0) < 0.5 else "WARN",
        "active": True,
    }
    return rule


def apply_rule(rule: dict) -> None:
    """Register rule in hermes-ops config via MCP"""
    try:
        script = textwrap.dedent("""\
            import sys, json, os
            sys.path.insert(0, os.environ["HERMES_SRC"])
            from hermes_ops.events import emit
            emit("RULE_GENERATED", json.loads(os.environ["RULE_PAYLOAD"]))
        """)
        subprocess.run(
            ["python3", "-c", script],
            env={
                **os.environ,
                "HERMES_SRC": os.path.expanduser("~/Workspace/ops/src"),
                "RULE_PAYLOAD": json.dumps(rule),
            },
            capture_output=True,
            timeout=5,
        )
    except Exception:
        pass


def push_notification(title: str, message: str) -> None:
    """Trigger desktop push notification"""
    try:
        data = json.dumps({"title": title, "message": message})
        subprocess.run(["python3", str(PUSH_SCRIPT)], input=data.encode(), timeout=5, capture_output=True)
    except Exception:
        pass


def process_patterns(patterns: list[dict]) -> list[dict]:
    """Main: patterns in → rules out → push triggered"""
    if not patterns:
        push_notification("Pattern Learner", "No patterns detected yet. Need more data.")
        return []
    rules = [pattern_to_rule(p) for p in patterns]
    for r in rules:
        apply_rule(r)
    title = f"{len(rules)} Pattern{'s' if len(rules) > 1 else ''} Detected"
    details = "; ".join(f"{p['description']}" for p in patterns)
    push_notification(title, details)
    return rules


def simulate() -> list[dict]:
    from kos.pattern_learner import PatternLearner  # type: ignore[import-not-found]

    pl = PatternLearner()
    patterns = pl.simulate()
    return process_patterns(patterns)
