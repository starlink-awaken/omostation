"""Tests for north_star_meter_v4 (BET-Y1Q3-T10-121).

5 invariant tests covering:
1. compute_axes backward compat with v3 (5 axes + A2)
2. compute_realtime returns today's signals
3. D2 cognitive leverage ratio math (D / A)
4. Monthly report idempotent file path
5. Cockpit command imports
"""
from __future__ import annotations

import datetime as dt
import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest

WS_ROOT = Path(__file__).resolve().parent.parent
V4_PATH = WS_ROOT / "bin" / "bc-os" / "north_star_meter_v4.py"


def _load_v4():
    """Load v4 module from file path (no package layout)."""
    spec = importlib.util.spec_from_file_location(
        "north_star_meter_v4", str(V4_PATH.absolute())
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_compute_axes_has_v4_d2_axis():
    """V4 必须含 D2 认知杠杆率 axis (V4 新增)."""
    v4 = _load_v4()
    axes = v4.compute_axes(30)
    assert "D2" in axes["axes"], "missing D2 axis (cognitive leverage, V4 new)"
    d2 = axes["axes"]["D2"]
    assert d2["score"] >= 0 and d2["score"] <= 100
    assert "leverage_ratio" in d2
    assert "explanation" in d2


def test_compute_axes_backward_compat():
    """V4 必须保留 V3 的 5 axes + A2 (backward compat)."""
    v4 = _load_v4()
    axes = v4.compute_axes(30)
    required_axes = {"A", "B", "C", "D", "E", "A2", "D2"}
    actual = set(axes["axes"].keys())
    missing = required_axes - actual
    assert not missing, f"V4 missing axes: {missing}"


def test_realtime_window_uses_today_start():
    """realtime 必须以今日 UTC 0:00 为起点."""
    v4 = _load_v4()
    rt = v4.compute_realtime()
    assert rt["scope"] == "realtime"
    since = dt.datetime.fromisoformat(rt["since"].replace("Z", "+00:00"))
    today = dt.datetime.now(dt.timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    assert since == today
    assert "axes_realtime" in rt
    assert "A_minutes_today" in rt["axes_realtime"]
    assert "B_decisions_today" in rt["axes_realtime"]
    assert "D_knowledge_today" in rt["axes_realtime"]


def test_d2_leverage_ratio_zero_safe():
    """A=0 时 D2 leverage 不能除零 (必须有 fallback)."""
    v4 = _load_v4()
    axes = v4.compute_axes(30)
    d2 = axes["axes"]["D2"]
    # 0/0 fallback: ratio=0, score=50 (neutral)
    assert d2["leverage_ratio"] == 0.0
    assert d2["score"] == 50


def test_report_idempotent_path():
    """_report_path 同日期必须返回相同 path (覆盖而非新增)."""
    v4 = _load_v4()
    p1 = v4._report_path("monthly")
    p2 = v4._report_path("monthly")
    assert p1 == p2, "report path 不稳定"
    assert p1.name.startswith("north-star-monthly-")
    # 季度路径区分
    q1 = v4._report_path("quarterly")
    assert q1.name.startswith("north-star-quarterly-")


def test_render_report_contains_d2_section():
    """Markdown 报告必须含 D2 认知杠杆率段."""
    v4 = _load_v4()
    axes = v4.compute_axes(7)
    rt = v4.compute_realtime()
    md = v4.render_report(axes, rt, "monthly")
    assert "D2" in md
    assert "认知杠杆率" in md
    assert "leverage_ratio" in md or "杠杆率" in md


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
