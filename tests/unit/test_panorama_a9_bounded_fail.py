"""A9 的判据应当看**年龄**, 不是状态标签。

2026-10-23 实测: A9 把 `STALE_UNAVAILABLE` 且 last_success 在 6h 界内的源判成
「可接受」, 却把同样界内的 `FAIL` 判成「阻断」—— 而这两个标签在采集器侧语义相同
(orchestrator 对 error 路径报 STALE_UNAVAILABLE, 采集器对非零退出报 FAIL)。当时
documents/strategy/strategy-projection 都报 STALE_UNAVAILABLE、compute 报
UNAVAILABLE, A9 因此转 PARTIAL, 尽管这些源的上次成功观测都在界内。
"""

from __future__ import annotations

import importlib.util
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "bin/panorama/panorama-collect.py"

REQUIRED = {
    "catalog", "strategy", "strategy-projection", "environment_evidence",
    "portfolio", "workflow", "resident", "scheduler", "references",
    "orca", "multica", "ruflo", "documents", "compute",
}


def _stamp(age_hours: float) -> str:
    return (datetime.now(timezone.utc) - timedelta(hours=age_hours)).isoformat()


def _asd() -> dict:
    return {
        "schema": "asd-snapshot/v1", "verdict": "COMPLETE",
        "panels": {"overview": {}, "spine": {}, "agents": {}, "milestones": {}, "degradation": {}},
        "degraded_panels": [],
    }


def _cockpit(states: dict) -> dict:
    # A9 要求 cockpit 投影 ≤600s 新鲜; 源年龄另由 last_success_at 表达。
    return {
        "generated_at": _stamp(0),
        "source_states": {
            name: {
                "status": states.get(name, "OK"),
                "last_success_at": _stamp(float(states.get(name + ":age", 1))),
                "last_attempt_at": _stamp(0.5),
            }
            for name in REQUIRED
        },
    }


@pytest.fixture
def module(monkeypatch, tmp_path):
    spec = importlib.util.spec_from_file_location("pc_a9_bf", SCRIPT)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    home = tmp_path / "home"
    (home / ".local/share/zhixing-dashboard").mkdir(parents=True)
    monkeypatch.setattr(Path, "home", staticmethod(lambda: home))
    (home / ".local/share/zhixing-dashboard/current.json").write_text(
        json.dumps(_cockpit({})), encoding="utf-8")
    return m, home


def _set(home: Path, states: dict) -> None:
    (home / ".local/share/zhixing-dashboard/current.json").write_text(
        json.dumps(_cockpit(states)), encoding="utf-8")


def test_bounded_fail_is_accepted(module):
    m, home = module
    _set(home, {"documents": "FAIL", "documents:age": 4.77})
    report = m.collect_a9_gate(payload={"asd": _asd()}, dashboard_live=True)
    assert report["verdict"] == "PASS", report["detail"]


def test_beyond_bound_fail_still_blocks(module):
    m, home = module
    _set(home, {"documents": "FAIL", "documents:age": 48})
    report = m.collect_a9_gate(payload={"asd": _asd()}, dashboard_live=True)
    assert report["verdict"] == "PARTIAL"
    assert "documents=FAIL" in report["detail"]


def test_bounded_stale_unavailable_still_accepted(module):
    m, home = module
    _set(home, {"documents": "STALE_UNAVAILABLE", "documents:age": 5})
    report = m.collect_a9_gate(payload={"asd": _asd()}, dashboard_live=True)
    assert report["verdict"] == "PASS", report["detail"]


def test_unbounded_failure_still_blocks(module):
    m, home = module
    _set(home, {"compute": "UNAVAILABLE"})
    report = m.collect_a9_gate(payload={"asd": _asd()}, dashboard_live=True)
    assert report["verdict"] == "PARTIAL"
