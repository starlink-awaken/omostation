#!/usr/bin/env python3
"""Predictive Governance Engine — 治理推荐引擎 (GOV-01).

读 predictive-governance.yaml 配置 + metrics-store.jsonl 指标,
聚合特征 → 匹配 trigger → 产出推荐动作.

守 KISS: 用简单移动平均/moving_average (配置 fallback), 不做复杂ML.
Usage:
  python3 bin/ssot/predictive-governance.py            # 产出推荐
  python3 bin/ssot/predictive-governance.py --json     # JSON
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from _shared import ROOT, load_yaml, read_jsonl, utc_now

CONFIG_PATH = (
    ROOT / ".omo" / "_truth" / "registry" / "predictive-governance.yaml"
)
METRICS_PATH = ROOT / ".omo" / "state" / "metrics-store.jsonl"


def _load_config() -> dict[str, Any]:
    return load_yaml(CONFIG_PATH)


def _load_metrics() -> list[dict[str, Any]]:
    return read_jsonl(METRICS_PATH)


def _aggregate(entries: list[dict[str, Any]], window: int) -> dict[str, float]:
    """Aggregate recent metrics into daily features (moving average)."""
    from collections import defaultdict

    # Bucket by day
    daily: dict[str, dict[str, list]] = defaultdict(
        lambda: {"ok": [], "durations": []}
    )
    for e in entries[-max(window * 10, 100):]:
        day = str(e.get("timestamp", ""))[:10]
        daily[day]["ok"].append(bool(e.get("ok", False)))
        daily[day]["durations"].append(float(e.get("duration_ms", 0)))

    days = sorted(daily.keys())[-window:]
    if not days:
        return {}

    gate_pass = []
    durations = []
    for d in days:
        oks = daily[d]["ok"]
        if oks:
            gate_pass.append(sum(1 for o in oks if o) / len(oks))
        durs = daily[d]["durations"]
        if durs:
            durations.append(sum(durs) / len(durs))

    out: dict[str, float] = {}
    if gate_pass:
        out["gate_pass_rate"] = sum(gate_pass) / len(gate_pass)
    if durations:
        out["check_duration_trend"] = sum(durations) / len(durations)
    return out


def _match_recommendations(
    features: dict[str, float], config: dict
) -> list[dict[str, Any]]:
    """Match aggregated features to configured recommendation triggers."""
    recs = config.get("recommendations", [])
    out: list[dict[str, Any]] = []
    for rec in recs:
        trigger = rec.get("trigger", "")
        threshold = float(
            config.get("model", {}).get("confidence_threshold", 0.7)
        )
        matched = False

        if (
            trigger == "gate_pass_rate_declining"
            and features.get("gate_pass_rate", 1.0) < threshold
        ):
            matched = True
        elif (
            trigger == "check_duration_increasing"
            and features.get("check_duration_trend", 0) > 500
        ):
            matched = True
        elif (
            trigger == "stable_healthy"
            and features.get("gate_pass_rate", 1.0) >= threshold
        ):
            matched = True
        # Future: debt_volume_increasing, anomaly_spike
        # require external data sources

        if matched:
            out.append({
                "trigger": trigger,
                "priority": rec.get("priority", "P3"),
                "action": rec.get("action", ""),
                "template": (
                    rec.get("template", "")[:150]
                    if rec.get("template") else ""
                ),
                "matched_features": {
                    k: round(v, 3) for k, v in features.items()
                },
            })
    return out


def generate_recommendations(root: Path | None = None) -> dict[str, Any]:
    root = root or ROOT
    config = _load_config()
    entries = _load_metrics()
    features = _aggregate(
        entries, int(config.get("model", {}).get("window", 7) or 7)
    )
    recs = _match_recommendations(features, config)

    return {
        "schema": "predictive-governance/v1",
        "generated_at": utc_now(),
        "metrics_loaded": len(entries),
        "features": {k: round(v, 3) for k, v in features.items()},
        "recommendations": recs,
        "total_recommendations": len(recs),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args(argv)

    result = generate_recommendations(args.root)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(
            f"Predictive Governance: {result['total_recommendations']} "
            f"recommendations (metrics: {result['metrics_loaded']})"
        )
        print(f"  features: {result['features']}")
        for r in result["recommendations"]:
            print(
                f"  [{r['priority']}] {r['action']} "
                f"— trigger: {r['trigger']}"
            )
        if not result["recommendations"]:
            print("  ✅ No recommendations needed (system healthy).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
