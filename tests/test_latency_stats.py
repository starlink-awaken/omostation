"""Drive shipped latency_stats (min-sample floors + histogram) — no reimplementation."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DELIVERY = ROOT / "bin" / "delivery"


def _load():
    path = DELIVERY / "latency_stats.py"
    name = "delivery_latency_stats"
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader
    sys.path.insert(0, str(DELIVERY))
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_p99_insufficient_when_n_under_1000():
    mod = _load()
    # 100 samples, most ~10ms, one spike 157ms — classic small-n false p99
    samples = [10.0] * 99 + [157.0]
    s = mod.summarize_latencies(samples)
    assert s["n"] == 100
    assert s["p99_ms"] is None
    assert s["p99_ms_status"] == "insufficient_samples"
    assert s["p99_ms_raw"] is not None  # diagnostic only
    assert s["p99_definitive"] is False
    assert s["p99_meets_kpi"] is None
    assert s["p50_ms"] is not None  # p50 min_n=20 satisfied
    assert not mod.g_del_3_sim_ok_from_summary(s, successes=100, measured=100)


def test_p99_trusted_and_pass_when_n_ge_1000_and_body_fast():
    mod = _load()
    samples = [8.0 + (i % 5) * 0.5 for i in range(1000)]  # all << 100ms
    s = mod.summarize_latencies(samples)
    assert s["n"] == 1000
    assert s["p99_ms_status"] == "ok"
    assert s["p99_ms_trusted"] is True
    assert s["p99_ms"] is not None and s["p99_ms"] < 100.0
    assert s["p99_definitive"] is True
    assert s["p99_meets_kpi"] is True
    assert mod.g_del_3_sim_ok_from_summary(s, successes=1000, measured=1000) is True


def test_p99_trusted_fail_when_tail_real():
    mod = _load()
    # nearest-rank p99 index ≈ 0.99*(n-1); need enough slow tail samples
    samples = [10.0] * 980 + [150.0] * 20
    s = mod.summarize_latencies(samples)
    assert s["p99_definitive"] is True
    assert s["p99_ms"] is not None and s["p99_ms"] >= 100.0
    assert s["p99_meets_kpi"] is False
    assert mod.g_del_3_sim_ok_from_summary(s, successes=1000, measured=1000) is False


def test_histogram_counts_sum_to_n():
    mod = _load()
    samples = [0.5, 3.0, 12.0, 80.0, 120.0, 300.0]
    h = mod.build_histogram(samples)
    assert h["n"] == 6
    assert sum(h["counts"]) == 6
    assert any(b["count"] > 0 for b in h["bins"])


def test_p999_insufficient_at_n_1000():
    mod = _load()
    samples = [10.0] * 1000
    s = mod.summarize_latencies(samples)
    assert s["p99_ms_status"] == "ok"
    assert s["p999_ms_status"] == "insufficient_samples"
    assert s["p999_ms"] is None
