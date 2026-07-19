"""Latency percentile / histogram helpers with min-sample floors (measure honesty).

p99 requires n ≥ 1000 before it is treated as a definitive KPI value.
Insufficient samples → ``insufficient_samples`` flags; raw order-stats may still
be reported under ``raw_*`` for diagnostics but must not drive gate pass.
"""
from __future__ import annotations

from typing import Any

# Minimum sample counts before a percentile is "trusted" for gate decisions.
MIN_N_FOR_PERCENTILE: dict[str, int] = {
    "p50": 20,
    "p90": 100,
    "p95": 200,
    "p99": 1000,
    "p999": 10000,
}

# Default histogram edges in ms (log-ish for RTT tails)
DEFAULT_HIST_EDGES_MS = (
    0.0,
    1.0,
    2.0,
    5.0,
    10.0,
    15.0,
    20.0,
    30.0,
    50.0,
    75.0,
    100.0,
    150.0,
    200.0,
    500.0,
    1000.0,
    float("inf"),
)


def percentile_index(n: int, p: float) -> int:
    """Nearest-rank style index into a sorted list of length n (p in 0..100)."""
    if n <= 0:
        return 0
    if n == 1:
        return 0
    return min(n - 1, max(0, int(round((p / 100.0) * (n - 1)))))


def raw_percentile(sorted_samples: list[float], p: float) -> float | None:
    if not sorted_samples:
        return None
    return float(sorted_samples[percentile_index(len(sorted_samples), p)])


def trusted_percentile(
    sorted_samples: list[float],
    name: str,
    p: float,
    *,
    min_n_table: dict[str, int] | None = None,
) -> dict[str, Any]:
    """Return trusted percentile or insufficient_samples.

    Structure::
        {name: float|None, f"{name}_trusted": bool, f"{name}_status": "ok"|"insufficient_samples",
         f"{name}_min_n": int, f"{name}_raw": float|None}
    """
    table = min_n_table or MIN_N_FOR_PERCENTILE
    min_n = int(table.get(name, 1))
    n = len(sorted_samples)
    raw = raw_percentile(sorted_samples, p)
    key = name
    if n < min_n:
        return {
            key: None,
            f"{key}_trusted": False,
            f"{key}_status": "insufficient_samples",
            f"{key}_min_n": min_n,
            f"{key}_n": n,
            f"{key}_raw": round(raw, 4) if raw is not None else None,
        }
    return {
        key: round(raw, 4) if raw is not None else None,
        f"{key}_trusted": True,
        f"{key}_status": "ok",
        f"{key}_min_n": min_n,
        f"{key}_n": n,
        f"{key}_raw": round(raw, 4) if raw is not None else None,
    }


def build_histogram(
    samples: list[float],
    edges: tuple[float, ...] | list[float] = DEFAULT_HIST_EDGES_MS,
) -> dict[str, Any]:
    """Count samples into half-open bins [edges[i], edges[i+1]); last bin is [lo, +inf)."""
    edge_list = list(edges)
    if len(edge_list) < 2:
        return {"edges_ms": edge_list, "counts": [], "bins": []}
    counts = [0] * (len(edge_list) - 1)
    for v in samples:
        for i in range(len(edge_list) - 1):
            lo, hi = edge_list[i], edge_list[i + 1]
            if hi == float("inf"):
                if v >= lo:
                    counts[i] += 1
                    break
            elif lo <= v < hi:
                counts[i] += 1
                break
    bins = []
    for i, c in enumerate(counts):
        lo, hi = edge_list[i], edge_list[i + 1]
        label = f"[{lo},{hi})" if hi != float("inf") else f"[{lo},+inf)"
        bins.append(
            {
                "lo_ms": lo,
                "hi_ms": None if hi == float("inf") else hi,
                "label": label,
                "count": c,
            }
        )
    return {
        "unit": "ms",
        "n": len(samples),
        "edges_ms": [None if e == float("inf") else e for e in edge_list],
        "counts": counts,
        "bins": bins,
    }


def summarize_latencies(
    samples: list[float],
    *,
    min_n_table: dict[str, int] | None = None,
) -> dict[str, Any]:
    """Full tail summary: p50/p90/p95/p99/p999/max + histogram + sufficiency."""
    sorted_s = sorted(float(x) for x in samples)
    n = len(sorted_s)
    out: dict[str, Any] = {
        "n": n,
        "max_ms": round(sorted_s[-1], 4) if sorted_s else None,
        "min_ms": round(sorted_s[0], 4) if sorted_s else None,
        "histogram": build_histogram(sorted_s),
    }
    specs = (
        ("p50_ms", "p50", 50.0),
        ("p90_ms", "p90", 90.0),
        ("p95_ms", "p95", 95.0),
        ("p99_ms", "p99", 99.0),
        ("p999_ms", "p999", 99.9),
    )
    table = min_n_table or MIN_N_FOR_PERCENTILE
    # map display key prefix to table key
    table_alias = {
        "p50_ms": "p50",
        "p90_ms": "p90",
        "p95_ms": "p95",
        "p99_ms": "p99",
        "p999_ms": "p999",
    }
    for display, short, p in specs:
        # trusted_percentile uses short name for min table
        tp = trusted_percentile(sorted_s, short, p, min_n_table=table)
        # re-key to display names
        out[display] = tp[short]
        out[f"{display}_trusted"] = tp[f"{short}_trusted"]
        out[f"{display}_status"] = tp[f"{short}_status"]
        out[f"{display}_min_n"] = tp[f"{short}_min_n"]
        out[f"{display}_raw"] = tp[f"{short}_raw"]
        _ = table_alias  # silence lint

    # Gate helper: definitive p99 KPI only when trusted
    p99_trusted = bool(out.get("p99_ms_trusted"))
    p99_val = out.get("p99_ms")
    out["p99_definitive"] = p99_trusted and p99_val is not None
    if not p99_trusted:
        out["p99_gate_status"] = "insufficient_samples"
        out["p99_meets_kpi"] = None  # unknown
    else:
        out["p99_gate_status"] = "ok"
        out["p99_meets_kpi"] = bool(p99_val is not None and p99_val < 100.0)
    return out


def g_del_3_sim_ok_from_summary(summary: dict[str, Any], *, successes: int, measured: int) -> bool:
    """Whether G-DEL.3 KPI can pass given honest summary (needs definitive p99)."""
    if measured <= 0 or successes != measured:
        return False
    if not summary.get("p99_definitive"):
        return False
    return bool(summary.get("p99_meets_kpi"))
