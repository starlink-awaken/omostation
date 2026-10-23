"""Cockpit 源的降级原因必须可观测, 而不只是状态。

2026-10-23: A9 转 PARTIAL 时只报 `cockpit_sources`, 要看为什么得人工去翻
cockpit 的 current.json (25MB)。A9 的 detail 与 source_health 投影现在原样
带出 status + error。
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


def _load(monkeypatch, tmp_path):
    spec = importlib.util.spec_from_file_location("pc_source_health", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    home = tmp_path / "home"
    (home / ".local/share/zhixing-dashboard").mkdir(parents=True)
    monkeypatch.setattr(Path, "home", staticmethod(lambda: home))
    return module, home


def _stamp(age_seconds: float) -> str:
    return (datetime.now(timezone.utc) - timedelta(seconds=age_seconds)).isoformat()


def _cockpit(states: dict) -> dict:
    """states 可含 `<name>:status` / `<name>:error` / `<name>:age`（小时）。"""
    out = {}
    for name in REQUIRED:
        entry = {
            "status": states.get(name, "OK"),
            "error": states.get(name + ":error"),
            "last_success_at": _stamp(float(states.get(name + ":age", 1)) * 3600),
            "last_attempt_at": _stamp(30),
        }
        extra = states.get(name + ":error_class")
        if extra:
            entry["error_class"] = extra
        out[name] = entry
    return {"generated_at": _stamp(60), "source_states": out}


def _write(home: Path, payload: dict) -> None:
    (home / ".local/share/zhixing-dashboard/current.json").write_text(
        json.dumps(payload), encoding="utf-8"
    )


def test_a9_detail_carries_degradation_reasons(monkeypatch, tmp_path):
    module, home = _load(monkeypatch, tmp_path)
    _write(home, _cockpit({
        "compute": "UNAVAILABLE",
        "compute:error": "Collector deadline exceeded",
        "documents": "STALE_UNAVAILABLE",
        "documents:age": 48,
        "documents:error": "source command returned 2",
    }))
    report = module.collect_a9_gate(payload={"asd": _asd()}, dashboard_live=True)
    assert report["verdict"] == "PARTIAL"
    # 只报名字等于没报 —— 原因必须在 detail 里
    assert "compute=UNAVAILABLE(Collector deadline exceeded)" in report["detail"]
    assert "documents=STALE_UNAVAILABLE(source command returned 2)" in report["detail"]


def test_a9_detail_omits_reason_when_absent(monkeypatch, tmp_path):
    module, home = _load(monkeypatch, tmp_path)
    _write(home, _cockpit({"compute": "UNAVAILABLE"}))
    report = module.collect_a9_gate(payload={"asd": _asd()}, dashboard_live=True)
    # 原因缺失时只给状态 —— 宁可少说, 不要编
    assert "compute=UNAVAILABLE" in report["detail"]
    assert "compute=UNAVAILABLE(None)" not in report["detail"]


def test_source_health_projection_lists_reasons(monkeypatch, tmp_path):
    module, home = _load(monkeypatch, tmp_path)
    _write(home, _cockpit({
        "documents": "STALE_UNAVAILABLE",
        "documents:age": 48,
        "documents:error": "Collector deadline exceeded",
        "scheduler": "DEGRADED",
        "scheduler:error_class": "SchedulerPartial",
    }))
    health = module.collect_cockpit_source_health()
    assert health["schema"] == "panorama-source-health/v1"
    assert health["available"] is True
    assert health["degraded_count"] >= 2
    assert health["sources"]["documents"]["error"] == "Collector deadline exceeded"
    assert health["sources"]["scheduler"]["error_class"] == "SchedulerPartial"


def test_source_health_reports_absent_projection(monkeypatch, tmp_path):
    module, home = _load(monkeypatch, tmp_path)
    health = module.collect_cockpit_source_health()
    assert health["available"] is False
    assert health["reason"].startswith("cockpit projection unreadable")
    assert health["sources"] == {}


def test_nested_error_reason_is_flattened(monkeypatch, tmp_path):
    """portfolio 的 error 是嵌套 dict (remote_error.phase/…), 要能读出原因。"""
    module, home = _load(monkeypatch, tmp_path)
    nested = {"remote_error": {"phase": "remote_main_oid", "reason": "source command timed out"}}
    states = {name: "OK" for name in REQUIRED}
    states["portfolio"] = "UNAVAILABLE"
    states["portfolio:error"] = nested  # type: ignore[dict-item]
    _write(home, _cockpit(states))
    report = module.collect_a9_gate(payload={"asd": _asd()}, dashboard_live=True)
    assert "portfolio=UNAVAILABLE" in report["detail"]
    assert "source command timed out" in report["detail"]


def _asd() -> dict:
    return {
        "schema": "asd-snapshot/v1", "verdict": "COMPLETE",
        "panels": {"overview": {}, "spine": {}, "agents": {}, "milestones": {}, "degradation": {}},
        "degraded_panels": [],
    }
