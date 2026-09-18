"""panel-collect — 驾驶舱三板块真实数据采集层单测.

重点验证契约而非实现细节:
* 缺失源显式 MISSING, 不静默当 0
* 事件归一化 / 分桶 / 稳定排序(确定性)
* 时序派生自真实日志
* 价值证据严格 NOT_PROVEN, 比率指标受样本基础门槛约束
"""

from __future__ import annotations

import importlib.util
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _load():
    spec = importlib.util.spec_from_file_location(
        "panel_collect", ROOT / "bin/panorama/panel-collect.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["panel_collect"] = module
    spec.loader.exec_module(module)
    return module


def _write(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in records) + "\n",
                    encoding="utf-8")


NOW = datetime(2026, 9, 18, 12, 0, 0, tzinfo=UTC).timestamp()


def _iso_hours_ago(h: float) -> str:
    return datetime.fromtimestamp(NOW - h * 3600, tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _seed_events(root: Path) -> None:
    mod = _load()
    _write(root / mod.EVENT_SOURCES["resident-heartbeat"]["path"], [
        {"ts": _iso_hours_ago(1), "health": "ok", "source": "resident-heartbeat"},
        {"ts": _iso_hours_ago(2), "health": "degraded", "degraded_components": ["x"]},
        {"ts": _iso_hours_ago(50), "health": "ok"},          # 24h 窗口外
    ])
    _write(root / mod.EVENT_SOURCES["agent-workflows"]["path"], [
        {"ts": _iso_hours_ago(3), "event": "agent_workflow_verify", "actor": "a1",
         "ok": False, "status": "blocked", "run_id": "r1",
         "checks": [{"id": "c1", "ok": True, "duration_s": 1.5},
                    {"id": "c2", "ok": False, "duration_s": 2.5}],
         "changed_files": ["x.py"]},
    ])


# ── 事件流 ─────────────────────────────────────────────────────────────

def test_missing_sources_are_flagged_not_zeroed(tmp_path):
    """声明但无文件的源必须标 MISSING, 且计数为 None（不能是 0 混入统计）。"""
    mod = _load()
    result = mod.collect_event_stream(root=tmp_path, now=NOW)
    states = {s["name"]: s for s in result["sources"]}
    assert states["signal-poller"]["state"] == "MISSING"
    assert states["signal-poller"]["window_count"] is None
    assert states["swarm-conflicts"]["state"] == "MISSING"
    assert result["summary"]["sources_missing"] == len(mod.EVENT_SOURCES)
    assert result["summary"]["sources_live"] == 0


def test_normalizes_events_and_derives_facets(tmp_path):
    mod = _load()
    _seed_events(tmp_path)
    result = mod.collect_event_stream(root=tmp_path, now=NOW)

    assert result["summary"]["events_24h"] == 3     # 50h 前那条被 24h 窗口排除
    assert result["facets"]["by_source"]["resident-heartbeat"] == 2

    verify = next(e for e in result["events"] if e["type"] == "agent_workflow_verify")
    assert verify["agent"] == "a1"
    assert verify["status"] == "blocked"           # ok=False → failed 语义由 status 承载
    assert verify["duration_s"] == 4.0             # checks 耗时求和
    assert verify["failed_check_count"] == 1
    assert verify["changed_file_count"] == 1

    hb = next(e for e in result["events"] if e["type"] == "resident-heartbeat")
    assert hb["status"] == "ok"


def test_hourly_series_buckets_are_real(tmp_path):
    mod = _load()
    _seed_events(tmp_path)
    result = mod.collect_event_stream(root=tmp_path, now=NOW)
    points = result["series"]["hourly_24h"]
    assert len(points) == 24
    assert sum(v for _, v in points) == 3
    assert points[-1][0].endswith(":00:00Z")       # 桶对齐到小时


def test_events_are_deterministically_ordered(tmp_path):
    """同输入 → 同输出顺序（可 diff）。"""
    mod = _load()
    _seed_events(tmp_path)
    first = mod.collect_event_stream(root=tmp_path, now=NOW)
    second = mod.collect_event_stream(root=tmp_path, now=NOW)
    assert [e["ts"] for e in first["events"]] == [e["ts"] for e in second["events"]]
    assert first == second


def test_bad_json_lines_are_skipped(tmp_path):
    mod = _load()
    path = tmp_path / mod.EVENT_SOURCES["workflow-mesh"]["path"]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"ts": _iso_hours_ago(1), "event": "ok_event"}) + "\n"
        + "{ this is not json\n"
        + "\n"
        + json.dumps({"ts": _iso_hours_ago(2), "event": "another"}) + "\n",
        encoding="utf-8")
    result = mod.collect_event_stream(root=tmp_path, now=NOW)
    assert result["summary"]["events_24h"] == 2


def test_events_without_timestamp_are_dropped(tmp_path):
    mod = _load()
    _write(tmp_path / mod.EVENT_SOURCES["workflow-mesh"]["path"], [
        {"event": "no_ts"}, {"ts": "not-a-date", "event": "bad_ts"},
        {"ts": _iso_hours_ago(1), "event": "good"},
    ])
    result = mod.collect_event_stream(root=tmp_path, now=NOW)
    assert result["summary"]["events_24h"] == 1


def test_empty_root_does_not_crash(tmp_path):
    mod = _load()
    result = mod.collect_event_stream(root=tmp_path, now=NOW)
    assert result["summary"]["events_24h"] == 0
    assert result["summary"]["failure_rate"] is None   # 无样本 → 未知, 不是 0%
    assert result["events"] == []


# ── 指标时序 ───────────────────────────────────────────────────────────

def test_history_series_from_refresh_and_heartbeat(tmp_path):
    mod = _load()
    _write(tmp_path / mod.EVENT_SOURCES["resident-heartbeat"]["path"], [
        {"ts": _iso_hours_ago(1), "health": "ok"},
        {"ts": _iso_hours_ago(1.5), "health": "ok"},
        {"ts": _iso_hours_ago(2), "health": "degraded", "degraded_components": ["y"]},
    ])
    dashboard = tmp_path / "dashboard"
    _write(dashboard / "refresh.jsonl", [
        {"published_at": _iso_hours_ago(5), "failed_sources": [],
         "strategic": {"counts": {"nodes": 3400, "edges": 6400}}},
        {"published_at": _iso_hours_ago(6), "failed_sources": ["orca"],
         "strategic": {"counts": {"nodes": 3399, "edges": 6398}}},
    ])
    result = mod.collect_metrics_history(root=tmp_path, now=NOW, dashboard_dir=dashboard)
    series = result["series"]
    assert len(series["heartbeat_ok_hourly"]["points"]) == 24
    assert sum(v for _, v in series["heartbeat_ok_hourly"]["points"]) == 2
    assert sum(v for _, v in series["heartbeat_degraded_hourly"]["points"]) == 1
    assert sum(v for _, v in series["refresh_ok_daily"]["points"]) == 1
    assert sum(v for _, v in series["refresh_failed_daily"]["points"]) == 1
    assert series["graph_nodes_daily"]["points"][-1][1] == 3400
    assert result["coverage"]["refresh_jsonl"]["lines"] == 2


def test_history_marks_coverage_when_sources_absent(tmp_path):
    mod = _load()
    result = mod.collect_metrics_history(root=tmp_path, now=NOW,
                                         dashboard_dir=tmp_path / "dashboard")
    assert result["coverage"] == {}
    assert all(len(v["points"]) in (7, 24, 30) for v in result["series"].values())


# ── 价值证据 ───────────────────────────────────────────────────────────

def _seed_value(root: Path, records: list[dict]) -> None:
    _write(root / ".omo/_delivery/ingress/value-evidence.jsonl", records)


def test_value_is_not_proven_with_no_evidence(tmp_path):
    mod = _load()
    result = mod.collect_value_evidence(root=tmp_path, now=NOW)
    assert result["state"] == "not_proven"
    assert result["samples"]["records"] == 0
    assert any("尚无任何价值证据" in r for r in result["state_reason"])


def test_ratio_thresholds_gated_when_sample_basis_insufficient(tmp_path):
    """2 条记录 100% 采纳不得判达标 —— 绿色必须留给真实达标。"""
    mod = _load()
    _seed_value(tmp_path, [
        {"timestamp": _iso_hours_ago(1), "scene_id": "s1", "verdict": "accept",
         "qualifying": True, "net_saved_seconds": 60, "run_id": "r1"},
        {"timestamp": _iso_hours_ago(2), "scene_id": "s2", "verdict": "accept",
         "qualifying": True, "net_saved_seconds": 30, "run_id": "r2"},
    ])
    result = mod.collect_value_evidence(root=tmp_path, now=NOW)
    acceptance = next(t for t in result["thresholds"] if t["key"] == "acceptance")
    assert acceptance["current"] == 100.0
    assert acceptance["met"] is None                     # 不可判定, 不是 True
    assert "不足" in acceptance["gate"]
    samples = next(t for t in result["thresholds"] if t["key"] == "samples")
    assert samples["current"] == 2 and samples["met"] is False


def test_ratio_threshold_judged_once_sample_basis_sufficient(tmp_path):
    mod = _load()
    _seed_value(tmp_path, [
        {"timestamp": _iso_hours_ago(i), "scene_id": f"s{i}", "verdict": "accept",
         "qualifying": True, "net_saved_seconds": 10, "run_id": f"r{i}"}
        for i in range(1, 31)
    ])
    result = mod.collect_value_evidence(root=tmp_path, now=NOW)
    acceptance = next(t for t in result["thresholds"] if t["key"] == "acceptance")
    assert acceptance["met"] is True
    samples = next(t for t in result["thresholds"] if t["key"] == "samples")
    assert samples["current"] == 30 and samples["met"] is True
    assert result["state"] == "not_proven"               # 单条门槛达标 ≠ 整体已证明


def test_non_qualifying_samples_excluded_from_value_gate(tmp_path):
    mod = _load()
    _seed_value(tmp_path, [
        {"timestamp": _iso_hours_ago(1), "scene_id": "s1", "verdict": "accept",
         "qualifying": False, "net_saved_seconds": 0, "run_id": "r1"},
    ])
    result = mod.collect_value_evidence(root=tmp_path, now=NOW)
    assert result["samples"]["records"] == 1
    assert result["samples"]["qualifying"] == 0
    assert any("qualifying=false" in r for r in result["state_reason"])


def test_journey_stage_reads_real_export_without_context(tmp_path):
    mod = _load()
    _write(tmp_path / ".omo/_knowledge/scene-history/execution-daily.json",
           []) if False else None
    path = tmp_path / ".omo/_knowledge/scene-history"
    path.mkdir(parents=True, exist_ok=True)
    (path / "execution-daily.json").write_text(json.dumps({
        "schema": "scene-history-export/v1",
        "rows": [{"day": "2026-09-17", "scene_id": "s", "runs": 3, "successes": 3}],
    }), encoding="utf-8")
    result = mod.collect_value_evidence(root=tmp_path, now=NOW)
    journey = next(s for s in result["stages"] if s["key"] == "journey")
    assert journey["count"] == 3 and journey["state"] == "OK"


def test_context_overrides_stage_counts(tmp_path):
    mod = _load()
    result = mod.collect_value_evidence(
        root=tmp_path, now=NOW,
        context={"scene_cards": {"active_total": 24}})
    intent = next(s for s in result["stages"] if s["key"] == "intent")
    assert intent["count"] == 24 and intent["state"] == "OK"


def test_value_schema_and_stage_shape(tmp_path):
    mod = _load()
    result = mod.collect_value_evidence(root=tmp_path, now=NOW)
    assert result["schema"] == "panel-value/v1"
    assert [s["key"] for s in result["stages"]] == ["signal", "intent", "journey", "record", "feedback"]
    assert len(result["vision_thresholds"]) == 5


def test_value_state_survives_deployment_not_proven_filter(tmp_path):
    """部署侧 refresh.render() 的 clean_not_proven() 会删除**值恰为 'NOT_PROVEN' 的键**。

    该规则本意是清理历史占位文本, 却会把合法的价值状态整键删掉, 使页面退化为
    UNKNOWN。因此采集器必须输出能穿过该规则的值（小写）, 视图层负责大写展示。
    """

    def clean_not_proven(obj):
        if isinstance(obj, dict):
            return {k: clean_not_proven(v) for k, v in obj.items() if v != "NOT_PROVEN"}
        if isinstance(obj, list):
            return [clean_not_proven(i) for i in obj if i != "NOT_PROVEN"]
        if isinstance(obj, str) and obj == "NOT_PROVEN":
            return "—"
        return obj

    mod = _load()
    result = mod.collect_value_evidence(root=tmp_path, now=NOW)
    assert result["state"] != "NOT_PROVEN", "状态值会被部署侧规则整键删除"
    survived = clean_not_proven(result)
    assert "state" in survived, "state 键未能穿过 clean_not_proven()"
    assert survived["state"] == "not_proven"
    # 且不得存在任何会被该规则吞掉的字符串值
    def walk(obj, path=""):
        if isinstance(obj, dict):
            for k, v in obj.items():
                walk(v, f"{path}.{k}")
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                walk(v, f"{path}[{i}]")
        else:
            assert not (isinstance(obj, str) and obj == "NOT_PROVEN"), f"{path} 会被删除"

    walk(result)
