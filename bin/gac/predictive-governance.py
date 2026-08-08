#!/usr/bin/env python3
"""Predictive Governance — trend prediction + prescriptive recommendations.

Usage:
    python3 bin/gac/predictive-governance.py
    python3 bin/gac/predictive-governance.py --registry .omo/_truth/registry/predictive-governance.yaml
    python3 bin/gac/predictive-governance.py --simulate-threshold 5 --check check-submodule-rewind
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore[assignment]

WORKSPACE = Path(__file__).resolve().parents[2]
DEFAULT_REGISTRY = WORKSPACE / ".omo/_truth/registry/predictive-governance.yaml"
DEFAULT_METRICS = WORKSPACE / ".omo/state/metrics-store.jsonl"
DEFAULT_OUTPUT = WORKSPACE / ".omo/state/runtime/predictive-governance.json"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_registry(registry_path: Path) -> dict:
    if not registry_path.is_file():
        return {}
    if yaml is None:
        return {}
    try:
        docs = [d for d in yaml.safe_load_all(registry_path.read_text(encoding="utf-8")) if d]
        data = docs[-1] if docs else {}
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _load_metrics(metrics_file: Path, window: int = 30) -> list[dict]:
    if not metrics_file.is_file():
        return []
    lines = metrics_file.read_text(encoding="utf-8").splitlines()
    entries = [json.loads(line) for line in lines if line.strip()]
    if window > 0:
        entries = entries[-window:]
    return entries


def _daily_pass_rates(entries: list[dict]) -> dict[str, float]:
    by_day: dict[str, dict] = {}
    for e in entries:
        ts = str(e.get("timestamp", ""))
        day = ts[:10] if len(ts) >= 10 else "unknown"
        if day not in by_day:
            by_day[day] = {"count": 0, "ok_count": 0}
        by_day[day]["count"] += 1
        if e.get("ok") is True:
            by_day[day]["ok_count"] += 1
    return {d: (v["ok_count"] / v["count"] if v["count"] else 0.0) for d, v in by_day.items()}


def _linear_prediction(values: list[float]) -> dict:
    if len(values) < 2:
        return {"error": "insufficient_history", "values": values}
    n = len(values)
    x_mean = sum(range(n)) / n
    y_mean = sum(values) / n
    numerator = sum((i - x_mean) * (values[i] - y_mean) for i in range(n))
    denominator = sum((i - x_mean) ** 2 for i in range(n))
    if denominator == 0:
        return {"trend": "stable", "slope": 0.0, "values": values}
    slope = numerator / denominator
    intercept = y_mean - slope * x_mean
    last_idx = n - 1
    next_value = intercept + slope * (last_idx + 1)
    return {
        "slope": round(slope, 4),
        "intercept": round(intercept, 4),
        "current": round(values[-1], 3),
        "next_predicted": round(next_value, 3),
        "trend": "improving" if slope > 0.01 else "declining" if slope < -0.01 else "stable",
        "values": [round(v, 3) for v in values],
    }


def _generate_recommendations(predictions: dict, registry: dict) -> list[dict]:
    recs: list[dict] = []
    rec_rules = registry.get("recommendations", [])
    trend = predictions.get("trend", "stable")
    slope = predictions.get("slope", 0.0)
    current = predictions.get("current", 0.0)

    if trend == "declining" and current < 0.7:
        recs.append({
            "action": "review_recent_changes",
            "priority": "P0",
            "reason": f"gate pass rate declining (current={current:.1%}, slope={slope:.4f})",
            "confidence": 0.85,
        })
    elif trend == "declining":
        recs.append({
            "action": "review_recent_changes",
            "priority": "P1",
            "reason": f"gate pass rate declining (current={current:.1%})",
            "confidence": 0.7,
        })
    elif trend == "improving":
        recs.append({
            "action": "maintain_current_practices",
            "priority": "P3",
            "reason": "governance metrics improving",
            "confidence": 0.8,
        })
    else:
        recs.append({
            "action": "maintain_current_practices",
            "priority": "P3",
            "reason": "governance metrics stable",
            "confidence": 0.6,
        })

    for rule in rec_rules:
        trigger = rule.get("trigger", "")
        if trigger == "check_duration_increasing" and slope > 0.01:
            recs.append({
                "action": rule.get("action", ""),
                "priority": rule.get("priority", "P2"),
                "reason": rule.get("template", "").format(value=f"{slope * 1000:.1f}ms/day"),
                "confidence": 0.7,
            })

    return recs


def _simulate_threshold(metrics_file: Path, check: str, threshold: int, window: int = 7) -> dict:
    entries = _load_metrics(metrics_file, window=window * 2)
    check_entries = [e for e in entries if e.get("check") == check]
    if not check_entries:
        return {"error": f"no data for check '{check}'", "check": check, "simulated_threshold": threshold}

    recent = check_entries[-window:] if len(check_entries) >= window else check_entries
    fail_count = sum(1 for e in recent if e.get("ok") is False)
    fail_rate = fail_count / len(recent) if recent else 0.0

    projected = {
        "check": check,
        "simulated_threshold": threshold,
        "window": window,
        "recent_fail_rate": round(fail_rate, 3),
        "recent_total": len(recent),
        "recent_fails": fail_count,
        "would_trigger": fail_count > threshold,
        "recommendation": (
            f"threshold={threshold} would trigger {fail_count} failures in last {window} runs"
            if fail_count > threshold
            else f"threshold={threshold} safe for last {window} runs ({fail_count} failures)"
        ),
    }
    return projected


def generate_prediction(registry: dict, metrics_file: Path) -> dict:
    model_cfg = registry.get("model", {})
    min_history = model_cfg.get("min_history", 5)
    metrics = _load_metrics(metrics_file, window=30)
    if not metrics:
        return {"error": "no metrics data", "generated_at": _now_iso()}

    pass_rates = _daily_pass_rates(metrics)
    values = [pass_rates[d] for d in sorted(pass_rates.keys())]
    if len(values) < min_history:
        return {"error": f"insufficient_history: {len(values)} < {min_history}", "values": values}

    prediction = _linear_prediction(values)
    recommendations = _generate_recommendations(prediction, registry)
    return {
        "generated_at": _now_iso(),
        "prediction": prediction,
        "recommendations": recommendations,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Predictive Governance")
    parser.add_argument("--registry", default=str(DEFAULT_REGISTRY), help="Predictive governance registry YAML")
    parser.add_argument("--metrics-file", default=str(DEFAULT_METRICS), help="Metrics JSONL path")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Output JSON path")
    parser.add_argument("--simulate-threshold", type=int, help="Simulate threshold value for a check")
    parser.add_argument("--check", help="Check name for simulation")
    args = parser.parse_args()

    registry = _load_registry(Path(args.registry))
    metrics_file = Path(args.metrics_file)

    if args.simulate_threshold is not None:
        check = args.check or "check-submodule-rewind"
        output = _simulate_threshold(metrics_file, check, args.simulate_threshold)
    else:
        output = generate_prediction(registry, metrics_file)

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(output, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
