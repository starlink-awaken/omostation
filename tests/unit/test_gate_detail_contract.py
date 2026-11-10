"""PANORAMA-GATE-DETAIL-UNRELIABLE ③ 的门禁单测。

平面一律注入 (published= / revision= 或临时文件)，不依赖宿主是否装了发布面 ——
CI 检出里没有 ~/.local/share/zhixing-dashboard，宿主相关的断言在 CI 上必须是
"读不出也不误判" 的形状，而不是恒真。每条绿色都配一条正控制 (positive control)。
"""

from __future__ import annotations

import importlib
import json
import sys
from datetime import date
from pathlib import Path

import yaml

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / "bin" / "gac"))

gdc = importlib.import_module("check-gate-detail-contract")

WARN_ONLY = date(2026, 11, 10)
AFTER = date(2026, 12, 2)


def _plane(items: list[tuple[str, str, str]]) -> dict:
    return {
        "generated_at": "2026-11-10T06:24:13+00:00",
        "gates": [{"id": i, "verdict": v, "detail": d} for i, v, d in items],
    }


def _kinds(result: dict, plane: str | None = None) -> list[str]:
    return sorted(v["kind"] for v in result["violations"] if plane is None or v["plane"] == plane)


# --- shape: A1 的单字符 '}' 死法 ------------------------------------------------


def test_bracket_only_detail_is_a_shape_violation():
    res = gdc.evaluate(
        published=_plane([("A1", "PASS", "}")]),
        revision=_plane([("A1", "PASS", "}")]),
        now=WARN_ONLY,
    )
    assert _kinds(res, "published") == ["shape"]
    assert res["verdict"] == "WARN"  # warn 期内不翻退出码，但必须可见
    assert res["blocking_violations"] == 2  # 两平面各一条：计数单位是「平面 × 门」，不是门数


def test_healthy_detail_is_clean_positive_control():
    plane = _plane([("A1", "PASS", "ok warnings=3"), ("A9", "PARTIAL", "A9 evidence incomplete: cockpit_sources, strategy=PARTIAL")])
    res = gdc.evaluate(published=plane, revision=plane, now=WARN_ONLY)
    assert res["violations"] == []
    assert res["skew_count"] == 0
    assert res["verdict"] == "OK"
    assert res["planes"]["published"]["gates_scanned"] == 2


def test_empty_detail_is_a_shape_violation():
    res = gdc.evaluate(
        published=_plane([("A4", "PASS", "   ")]),
        revision=_plane([("A4", "PASS", "   ")]),
        now=WARN_ONLY,
    )
    assert _kinds(res, "published") == ["shape"]


# --- reason_missing: A9 丢原因串的死法 ------------------------------------------


def test_cockpit_sources_without_reason_is_flagged():
    res = gdc.evaluate(
        published=_plane([("A9", "PARTIAL", "A9 evidence incomplete: cockpit_sources")]),
        revision=_plane([("A9", "PARTIAL", "A9 evidence incomplete: cockpit_sources")]),
        now=WARN_ONLY,
    )
    assert _kinds(res) == ["reason_missing", "reason_missing"]


def test_cockpit_sources_with_reason_is_clean_positive_control():
    res = gdc.evaluate(
        published=_plane([("A9", "PARTIAL", "A9 evidence incomplete: cockpit_sources, strategy=PARTIAL")]),
        revision=_plane([("A9", "PARTIAL", "A9 evidence incomplete: cockpit_sources, strategy=PARTIAL")]),
        now=WARN_ONLY,
    )
    assert res["violations"] == []


# --- verdict 同源 --------------------------------------------------------------


def test_pass_detail_with_failure_marker_is_incoherent():
    res = gdc.evaluate(
        published=_plane([("A9", "PASS", "A9 evidence incomplete: cockpit_sources, strategy=PARTIAL")]),
        revision=_plane([("A9", "PASS", "A9 evidence incomplete: cockpit_sources, strategy=PARTIAL")]),
        now=WARN_ONLY,
    )
    assert "coherence" in _kinds(res, "published")


# --- 顺序固定：set 迭代 causes 假漂移 -------------------------------------------


def test_unsorted_reason_tokens_are_flagged():
    res = gdc.evaluate(
        published=_plane([("A9", "PARTIAL", "A9 evidence incomplete: cockpit_sources, strategy=PARTIAL, catalog=FAIL")]),
        revision=_plane([("A9", "PARTIAL", "A9 evidence incomplete: cockpit_sources, strategy=PARTIAL, catalog=FAIL")]),
        now=WARN_ONLY,
    )
    assert "order" in _kinds(res, "published")
    assert res["order_violations"] == 2


def test_sorted_reason_tokens_are_clean_positive_control():
    res = gdc.evaluate(
        published=_plane([("A9", "PARTIAL", "A9 evidence incomplete: cockpit_sources, catalog=FAIL, strategy=PARTIAL")]),
        revision=_plane([("A9", "PARTIAL", "A9 evidence incomplete: cockpit_sources, catalog=FAIL, strategy=PARTIAL")]),
        now=WARN_ONLY,
    )
    assert res["violations"] == []


# --- 平面三态 ------------------------------------------------------------------


def test_absent_planes_are_not_judged(tmp_path):
    res = gdc.evaluate(
        published_path=tmp_path / "nope.json",
        revisions_dir=tmp_path / "nope-dir",
        now=WARN_ONLY,
    )
    assert res["planes"]["published"]["state"] == "absent"
    assert res["planes"]["revision"]["state"] == "absent"
    assert res["verdict"] == "OK"
    assert res["planes"]["published"]["gates_scanned"] == 0


def test_unreadable_plane_is_reported_not_silently_green(tmp_path):
    bad = tmp_path / "current.json"
    bad.write_text("{not json", encoding="utf-8")
    res = gdc.evaluate(published_path=bad, revisions_dir=tmp_path / "none", now=WARN_ONLY)
    assert res["planes"]["published"]["state"] == "unreadable"
    # 读不出 = 没有任何一条 detail 被证明合格；这条读数必须是「判不出」而不是「绿」
    assert res["planes"]["published"]["gates_scanned"] == 0


def test_present_plane_with_gates_but_no_a_series_self_attests(tmp_path):
    plane = tmp_path / "current.json"
    plane.write_text(
        json.dumps({"generated_at": "2026-11-10T06:24:13+00:00", "gates": [{"id": "G7", "verdict": "PASS", "detail": "ok"}]}),
        encoding="utf-8",
    )
    res = gdc.evaluate(published_path=plane, revisions_dir=tmp_path / "none", now=WARN_ONLY)
    assert res["planes"]["published"].get("parse_suspicious") == 1


# --- 跨平面偏斜：advisory，永不翻退出码 ----------------------------------------


def test_skew_is_reported_but_never_blocks_even_after_deadline():
    res = gdc.evaluate(
        published=_plane([("A1", "PASS", "ok warnings=3")]),
        revision=_plane([("A1", "PASS", "ok warnings=1")]),
        now=AFTER,
    )
    assert res["skew_count"] == 1
    assert res["skew"][0]["id"] == "A1"
    assert res["skew_same_window"] is True  # 两份 payload 的 generated_at 相同 ⇒ 差异只能是代码不同
    assert res["violations"] == []
    assert res["verdict"] == "WARN"  # 偏斜只降一等，限期过后也不阻断：清它要一次部署面写操作


def test_skew_window_is_the_two_payloads_own_gap():
    stale = _plane([("A1", "PASS", "ok warnings=1")])
    stale["generated_at"] = "2026-11-10T03:24:13+00:00"  # 比发布面早 3 小时：差值属正常演进
    res = gdc.evaluate(published=_plane([("A1", "PASS", "ok warnings=3")]), revision=stale, now=WARN_ONLY)
    assert res["skew_count"] == 1
    assert res["skew_same_window"] is False
    assert res["skew"][0]["same_window"] is False


def test_deadline_flips_shape_violation_to_blocking():
    res = gdc.evaluate(
        published=_plane([("A1", "PASS", "}")]),
        revision=_plane([("A1", "PASS", "}")]),
        now=AFTER,
    )
    assert res["verdict"] == "FAIL"
    assert res["enforcement"] == "blocking"


# --- 限期与 registry 同源、六字段记录 ------------------------------------------


def test_enforce_after_matches_governance_rule():
    ws = Path(__file__).resolve().parents[2]
    doc = yaml.safe_load((ws / ".omo/_truth/registry/governance-checks.yaml").read_text(encoding="utf-8"))

    def find(node):
        if isinstance(node, dict):
            if node.get("id") == gdc.RULE_ID:
                return node
            return next((r for v in node.values() if (r := find(v)) is not None), None)
        if isinstance(node, list):
            for v in node:
                if (r := find(v)) is not None:
                    return r
        return None

    rule = find(doc)
    assert rule is not None, f"{gdc.RULE_ID} 未登记进 governance-checks.yaml"
    assert rule["review_before"] == gdc.ENFORCE_AFTER
    assert rule["source_ref"] == "bin/gac/check-gate-detail-contract.py"


def test_six_field_record_has_no_omitted_keys():
    res = gdc.evaluate(published=_plane([("A1", "PASS", "ok")]), revision=_plane([("A1", "PASS", "ok")]), now=WARN_ONLY)
    rec = gdc._six_field_record(res, started=0.0, inputs=["x"], basis=["y"])
    assert set(rec) == {"inputs", "basis", "approver", "result", "duration_ms", "model_usage"}
    assert rec["model_usage"] is None  # 无模型调用写 null，不省略键


def test_main_writes_json_and_exits_zero_in_warn_period(tmp_path, capsys):
    pub = tmp_path / "current.json"
    pub.write_text(json.dumps(_plane([("A1", "PASS", "}")])), encoding="utf-8")
    rc = gdc.main(["--published", str(pub), "--revisions-dir", str(tmp_path / "none"), "--json", "--now", "2026-11-10"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["verdict"] == "WARN"
    assert set(payload["run_record"]) == {"inputs", "basis", "approver", "result", "duration_ms", "model_usage"}


def test_main_blocks_after_deadline(tmp_path, capsys):
    pub = tmp_path / "current.json"
    pub.write_text(json.dumps(_plane([("A1", "PASS", "}")])), encoding="utf-8")
    rc = gdc.main(["--published", str(pub), "--revisions-dir", str(tmp_path / "none"), "--json", "--now", "2026-12-02"])
    assert rc == 1
    assert json.loads(capsys.readouterr().out)["verdict"] == "FAIL"
