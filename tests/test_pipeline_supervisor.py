"""BET-Y1Q4-T2-05 pipeline supervisor: degrade semantics, state, inbound chain."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

_GUARD_SRC = ROOT / "projects/omo/src/omo/pipeline_supervisor.py"
if not _GUARD_SRC.is_file():
    pytest.skip(
        f"{_GUARD_SRC} 不在（projects/omo 未检出）—— 本模块在**模块级**加载它, "
        "缺席会让整个 tests/ 平面 collection 中断（5 errors, 一条都跑不了）。"
        "属检出形态, 不是回归",
        allow_module_level=True,
    )


spec = importlib.util.spec_from_file_location(
    "pipeline_supervisor", ROOT / "projects/omo/src/omo/pipeline_supervisor.py"
)
assert spec and spec.loader
SUP = importlib.util.module_from_spec(spec)
sys.modules["pipeline_supervisor"] = SUP
spec.loader.exec_module(SUP)


def test_station_degrade_captures_reason():
    states: dict = {}
    result = SUP._station("boom", states, lambda: (_ for _ in ()).throw(RuntimeError("x")))
    assert result is None
    assert states["boom"]["status"] == "degraded"
    assert "RuntimeError" in states["boom"]["reason"]


def test_station_ok_records_latency():
    states: dict = {}
    out = SUP._station("fine", states, lambda: 42)
    assert out == 42 and states["fine"]["status"] == "ok" and "ms" in states["fine"]


def _hermetic_state(tmp_path, monkeypatch):
    """把状态面整体挪进 tmp_path。

    这些用例原来只 patch `_ws`, 但 `_state_path()` 走的是 **state_root()**(ADR-0456 /
    BET-Y2Q4-T10-277 的刻意设计: 代码面与状态面不同源) —— 于是 patch 对状态面无效,
    `test_state_roundtrip` 会把 `morning_runs` 写进**开发机的真实工作区**, 再由
    `test_status_panel_shape` 读出来, 让后一条恒红。判据: 要隔离状态就 patch 状态缝本身。
    """
    monkeypatch.setattr(SUP, "_state_path", lambda: tmp_path / ".omo/state/pipeline-supervisor-state.json")


def test_state_roundtrip(tmp_path, monkeypatch):
    _hermetic_state(tmp_path, monkeypatch)
    SUP._save_state({"schema": SUP.SCHEMA, "morning_runs": [{"ts": "t"}], "inbound_runs": [], "alerts": []})
    loaded = SUP._load_state()
    assert loaded["morning_runs"][0]["ts"] == "t"


def test_status_panel_shape(tmp_path, monkeypatch):
    _hermetic_state(tmp_path, monkeypatch)
    panel = SUP.status()
    assert panel["schema"] == SUP.SCHEMA
    assert panel["today_morning_brief"] is False and panel["morning_runs_total"] == 0


def test_inbound_degrade_on_missing_file(tmp_path, monkeypatch):
    """Bad input → degraded stations, run recorded, no crash (circuit_breaker)."""
    _hermetic_state(tmp_path, monkeypatch)
    result = SUP.process_inbound(Path("/tmp/nonexistent-degrade-test.png"))
    assert result["degraded"], "missing file must degrade, not crash"
    state = json.loads((tmp_path / ".omo/state/pipeline-supervisor-state.json").read_text(encoding="utf-8"))
    assert state["inbound_runs"] and state["alerts"]  # recorded + alerted


def test_routes_registered():
    routes = (ROOT / "projects/omo/src/omo/resident/resident-routes.yaml").read_text(encoding="utf-8")
    assert "PipelineTick" in routes and "pipeline_supervisor" in routes
