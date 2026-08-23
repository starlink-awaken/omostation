#!/usr/bin/env python3
"""health-trend-chart — render health.jsonl as an ASCII line chart.

Reads .omo/state/history/health.jsonl (one record per radar run) and
prints an ASCII line chart of health_score over time. Designed to be
scriptable: --json emits raw aggregated data, --days truncates to a
window, --field picks which metric to chart.

Why this exists:
  radar writes per-run snapshots to history/health.jsonl (PR #1990).
  Operators asking "how is health trending?" previously had to manually
  read JSONL and visualize. This script makes the trend legible in a
  terminal: one chart, one decimal per bucket, one summary line.

Usage:
  python3 bin/gac/health-trend-chart.py                    # 7d default, health_score
  python3 bin/gac/health-trend-chart.py --days 30
  python3 bin/gac/health-trend-chart.py --field governance_anomaly_score
  python3 bin/gac/health-trend-chart.py --json
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

WORKSPACE = Path(__file__).resolve().parents[2]
DEFAULT_HISTORY = WORKSPACE / ".omo" / "state" / "history" / "health.jsonl"

VALID_FIELDS = {
    "health_score",
    "governance_anomaly_score",
    "freshness_score",
}

# Block characters at varying densities (Braille-like ASCII art).
BAR_CHARS = " ▁▂▃▄▅▆▇█"


def _load_records(path: Path) -> list[dict[str, Any]]:
    """Parse JSONL into records sorted by ts ascending."""
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if "ts" in rec:
            records.append(rec)
    records.sort(key=lambda r: r.get("ts", ""))
    return records


def _filter_window(
    records: list[dict[str, Any]], days: int, now: datetime
) -> list[dict[str, Any]]:
    cutoff = (now - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%S")
    return [r for r in records if r.get("ts", "") >= cutoff]


def _bucket_by_day(
    records: list[dict[str, Any]], field: str
) -> list[tuple[str, float, int]]:
    """Group by YYYY-MM-DD, take the LAST value of the day as the bucket."""
    by_day: dict[str, list[float]] = {}
    for r in records:
        ts = r.get("ts", "")
        if len(ts) < 10:
            continue
        day = ts[:10]
        val = r.get(field)
        if isinstance(val, (int, float)):
            by_day.setdefault(day, []).append(float(val))
    out: list[tuple[str, float, int]] = []
    for day in sorted(by_day):
        values = by_day[day]
        out.append((day, values[-1], len(values)))
    return out


def _sparkline(values: list[float], width: int = 40, lo: float = 0, hi: float = 100) -> str:
    """Render values as a sparkline using block characters."""
    if not values:
        return ""
    chars = []
    span = max(hi - lo, 1e-9)
    # Resample to `width` cells (downsample / upsample)
    n = len(values)
    for i in range(width):
        # average a window of values around i
        start = int(i * n / width)
        end = int((i + 1) * n / width)
        if end <= start:
            end = start + 1
        v = sum(values[start:end]) / max(end - start, 1)
        idx = int((v - lo) / span * (len(BAR_CHARS) - 1))
        idx = max(0, min(len(BAR_CHARS) - 1, idx))
        chars.append(BAR_CHARS[idx])
    return "".join(chars)


def _format_table(field: str, buckets: list[tuple[str, float, int]]) -> str:
    if not buckets:
        return f"(no data for field={field})"
    lines: list[str] = []
    lines.append(f"{'date':<12} {'value':>6}  {'n':>3}  chart")
    lines.append("-" * 12 + " " + "-" * 6 + "  " + "-" * 3 + "  " + "-" * 40)
    for day, val, n in buckets:
        lines.append(f"{day:<12} {val:>6.1f}  {n:>3}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--path", type=Path, default=DEFAULT_HISTORY, help="history JSONL path")
    parser.add_argument("--days", type=int, default=7, help="window in days")
    parser.add_argument("--field", choices=sorted(VALID_FIELDS), default="health_score")
    parser.add_argument("--json", action="store_true", help="emit aggregated JSON instead of chart")
    parser.add_argument(
        "--width", type=int, default=40, help="sparkline width in cells (default 40)"
    )
    args = parser.parse_args(argv)

    records = _load_records(args.path)
    windowed = _filter_window(records, args.days, datetime.now(UTC))
    buckets = _bucket_by_day(windowed, args.field)

    if args.json:
        summary = {
            "field": args.field,
            "days": args.days,
            "buckets": [
                {"date": d, "value": v, "samples": n} for d, v, n in buckets
            ],
            "min": min((v for _, v, _ in buckets), default=None),
            "max": max((v for _, v, _ in buckets), default=None),
            "latest": buckets[-1][1] if buckets else None,
            "delta": (
                (buckets[-1][1] - buckets[0][1]) if len(buckets) >= 2 else None
            ),
        }
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0

    print(f"=== {args.field} trend (last {args.days}d) ===")
    print(f"records in window: {len(windowed)}")
    print(f"buckets: {len(buckets)}")
    if not buckets:
        print("(no data)")
        return 0
    print(_format_table(args.field, buckets))
    spark = _sparkline([v for _, v, _ in buckets], width=args.width)
    print()
    print(f"  sparkline: |{spark}|")
    print()
    if len(buckets) >= 2:
        delta = buckets[-1][1] - buckets[0][1]
        direction = "+" if delta >= 0 else ""
        print(f"  trend: {direction}{delta:.1f} from {buckets[0][0]} to {buckets[-1][0]}")
    print(f"  latest: {buckets[-1][1]:.1f}  range: [{min(v for _, v, _ in buckets):.0f}, {max(v for _, v, _ in buckets):.0f}]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())