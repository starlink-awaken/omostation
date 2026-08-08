#!/usr/bin/env python3
"""Cross-Domain Trend Fusion — analyze governance metrics across domains.

Usage:
    python3 bin/gac/cross-domain-trend.py
    python3 bin/gac/cross-domain-trend.py --registry .omo/_truth/registry/trend-fusion.yaml
    python3 bin/gac/cross-domain-trend.py --domain governance --window 7
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
DEFAULT_REGISTRY = WORKSPACE / ".omo/_truth/registry/trend-fusion.yaml"
DEFAULT_OUTPUT = WORKSPACE / ".omo/state/runtime/cross-domain-trend.json"


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


def _aggregate_by_day(entries: list[dict]) -> dict[str, dict]:
    by_day: dict[str, dict] = {}
    for e in entries:
        ts = str(e.get("timestamp", ""))
        day = ts[:10] if len(ts) >= 10 else "unknown"
        if day not in by_day:
            by_day[day] = {"count": 0, "ok_count": 0, "fail_count": 0, "durations": []}
        by_day[day]["count"] += 1
        if e.get("ok") is True:
            by_day[day]["ok_count"] += 1
        elif e.get("ok") is False:
            by_day[day]["fail_count"] += 1
        dur = e.get("duration_ms")
        if isinstance(dur, (int, float)):
            by_day[day]["durations"].append(float(dur))
    return by_day


def _compute_trend(by_day: dict[str, dict], metric_key: str = "pass_rate") -> dict:
    days = sorted(by_day.keys())
    if len(days) < 2:
        return {"trend": "insufficient_data", "slope": 0.0, "values": []}

    values = []
    for d in days:
        day = by_day[d]
        if metric_key == "pass_rate" and day["count"] > 0:
            values.append(day["ok_count"] / day["count"])
        elif metric_key == "duration_trend" and day["durations"]:
            values.append(sum(day["durations"]) / len(day["durations"]))
        else:
            values.append(0.0)

    n = len(values)
    x_mean = sum(range(n)) / n
    y_mean = sum(values) / n
    numerator = sum((i - x_mean) * (values[i] - y_mean) for i in range(n))
    denominator = sum((i - x_mean) ** 2 for i in range(n))
    if denominator == 0:
        return {"trend": "stable", "slope": 0.0, "values": values}

    slope = numerator / denominator
    if abs(slope) < 0.01:
        trend = "stable"
    elif slope > 0:
        trend = "improving"
    else:
        trend = "declining"

    return {
        "trend": trend,
        "slope": round(slope, 4),
        "values": [round(v, 3) for v in values],
        "days": days,
    }


def _compute_ewma(values: list[float], alpha: float = 0.3) -> list[float]:
    if not values:
        return []
    smoothed = [values[0]]
    for v in values[1:]:
        smoothed.append(alpha * v + (1 - alpha) * smoothed[-1])
    return smoothed


def _fuse_domains(domain_trends: dict[str, dict], weights: dict[str, float]) -> dict:
    trend_scores: dict[str, float] = {}
    for domain, trend in domain_trends.items():
        w = weights.get(domain, 0.0)
        direction = trend.get("trend", "stable")
        slope = trend.get("slope", 0.0)
        latest_values = trend.get("values", [])
        latest = latest_values[-1] if latest_values else 0.5
        if latest >= 0.95 and direction == "stable":
            score = 1.0
        elif direction == "improving":
            score = 1.0 + abs(slope)
        elif direction == "declining":
            score = max(0.0, 1.0 - abs(slope) * 10)
        else:
            score = 0.5 + latest * 0.5
        trend_scores[domain] = score * w

    total_weight = sum(weights.get(d, 0.0) for d in domain_trends)
    if total_weight == 0:
        return {"fused_score": 0.5, "trend": "unknown", "domains": {}}

    fused_score = sum(trend_scores.values()) / total_weight
    if fused_score >= 0.85:
        fused_trend = "healthy"
    elif fused_score >= 0.5:
        fused_trend = "stable"
    else:
        fused_trend = "at_risk"

    return {
        "fused_score": round(fused_score, 3),
        "trend": fused_trend,
        "domains": {
            d: {"score": round(trend_scores.get(d, 0.0), 3), "trend": domain_trends.get(d, {}).get("trend", "unknown")}
            for d in domain_trends
        },
    }


def analyze_cross_domain_trend(registry: dict, window: int = 30) -> dict:
    fusion_cfg = registry.get("fusion", {})
    weights = fusion_cfg.get("weights", {})
    domains_cfg = registry.get("domains", {})

    domain_trends: dict[str, dict] = {}
    for domain_name, domain_cfg in domains_cfg.items():
        if not domain_cfg.get("enabled", False):
            continue
        source = domain_cfg.get("source", "")
        if not source:
            continue
        source_path = WORKSPACE / source
        entries = _load_metrics(source_path, window=window)
        if not entries:
            continue
        by_day = _aggregate_by_day(entries)
        trend = _compute_trend(by_day, metric_key="pass_rate")
        domain_trends[domain_name] = trend

    fused = _fuse_domains(domain_trends, weights)
    return {
        "generated_at": _now_iso(),
        "window": window,
        "fusion": fused,
        "domains": domain_trends,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Cross-Domain Trend Fusion")
    parser.add_argument("--registry", default=str(DEFAULT_REGISTRY), help="Trend fusion registry YAML path")
    parser.add_argument("--window", type=int, default=30, help="Metrics window (days)")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Output JSON path")
    parser.add_argument("--domain", help="Filter to single domain")
    args = parser.parse_args()

    registry = _load_registry(Path(args.registry))
    if not registry:
        print(json.dumps({"error": "registry not found or empty"}, ensure_ascii=False))
        return 1

    if args.domain:
        domains_cfg = registry.get("domains", {})
        domain_cfg = domains_cfg.get(args.domain)
        if not domain_cfg:
            print(json.dumps({"error": f"domain '{args.domain}' not found"}, ensure_ascii=False))
            return 1
        source = domain_cfg.get("source", "")
        if source:
            source_path = WORKSPACE / source
            entries = _load_metrics(source_path, window=args.window)
            by_day = _aggregate_by_day(entries)
            trend = _compute_trend(by_day)
            output = {"domain": args.domain, "generated_at": _now_iso(), "trend": trend}
        else:
            output = {"domain": args.domain, "error": "no source configured"}
    else:
        output = analyze_cross_domain_trend(registry, window=args.window)

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(output, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
