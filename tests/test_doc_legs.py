"""Documents 场景能力腿回归测试.

锁死不变量:
- process 真实跑检查 (不静默成功)
- record_result 聚合 process 结果 + 签名
- daily-run 分组覆盖全部 43 个场景, 每类内部按预期
- journey-engine 接线: process/record_result 走 doc_legs
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str, rel: str):
    if name in sys.modules:
        del sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


doc_legs = _load("doc_legs", "bin/ssot/doc_legs.py")

# ── process ─────────────────────────────────────────────


def test_process_real_doc_checks(tmp_path, monkeypatch):
    """process 必须真实跑检查, 不静默成功."""
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "good.md").write_text(
        "---\ntype: ssot\nowner: x\nlast-reviewed: 2099-01-01\n---\n# T\nline\nline\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(doc_legs, "_ROOT", tmp_path)
    sig = {"source": "workspace_docs", "signal": "doc.changed",
           "raw_item": {"path": "docs/good.md"}}
    r = doc_legs.process_document(sig, dry_run=False)
    assert r["status"] == "succeeded"
    assert r["checks"] > 0 and r["passed"] == r["checks"]
    assert r["doc"]["path"] == "docs/good.md"


def test_process_rejects_outside_root(tmp_path):
    """路径越界必须拒绝."""
    outside = tmp_path.parent / "evil.md"
    outside.write_text("# x\n", encoding="utf-8")
    r = doc_legs.process_document({"raw_item": {"path": str(outside)}}, dry_run=False)
    assert r["status"] == "partial"
    assert any("path_rejected" in i.get("kind", "") for i in r["issues"])


def test_process_missing_file_is_partial(tmp_path, monkeypatch):
    """文件不存在 partial, 不静默成功."""
    monkeypatch.setattr(doc_legs, "_ROOT", tmp_path)
    r = doc_legs.process_document(
        {"raw_item": {"path": "docs/nope.md"}}, dry_run=False
    )
    assert r["status"] == "partial"
    assert any("file_missing" in i.get("kind", "") for i in r["issues"])


def test_process_dry_run_annotated(tmp_path, monkeypatch):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "x.md").write_text("# x\n\nline\n", encoding="utf-8")
    monkeypatch.setattr(doc_legs, "_ROOT", tmp_path)
    r = doc_legs.process_document(
        {"raw_item": {"path": "docs/x.md"}}, dry_run=True
    )
    assert r["dry_run"] is True


# ── record_result ────────────────────────────────────────


def test_record_aggregates_process(tmp_path, monkeypatch):
    """record_result 聚合 process 检查结果 + 签名."""
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "bad.md").write_text("# x\n", encoding="utf-8")
    monkeypatch.setattr(doc_legs, "_ROOT", tmp_path)
    proc = doc_legs.process_document(
        {"raw_item": {"path": "docs/bad.md"}}, dry_run=False,
    )
    rec = doc_legs.record_result(
        {"scene_id": "scene-documents-test", "run_id": "run-1",
         "doc_process_result": proc},
        dry_run=False,
    )
    assert rec["status"] == "succeeded"
    record = rec["record"]
    assert record["record_hash"]
    out = tmp_path / ".omo" / "_delivery" / "scene-outcomes" / "scene-documents-test" / "run-1.json"
    assert out.is_file()


def test_record_without_process_returns_partial():
    r = doc_legs.record_result({}, dry_run=False)
    assert r["status"] == "partial" and "no_process_result" in r["error"]


# ── task class grouping ───────────────────────────────────


def test_all_43_scenes_classified():
    all_scenes = set()
    for cls, names in doc_legs.TASK_CLASS_GROUPS.items():
        all_scenes.update(names)
    assert len(all_scenes) == 43, f"expected 43, got {len(all_scenes)}"


def test_daily_run_order_covers_all():
    order = doc_legs.daily_run_order()
    seen = [s.replace("scene-documents-", "") for g in order for s in g]
    assert len(seen) == 43


def test_task_class_consistency():
    """每个 journey 前缀映射到唯一类, 且所有 journey 名可分类."""
    import glob, os
    journals = set(os.path.basename(p).replace('.yaml','').replace('-journey','') for p in
                   glob.glob(str(ROOT / '.omo/_truth/journeys/v3/documents-*.yaml')))
    classified = set()
    for cls, names in doc_legs.TASK_CLASS_GROUPS.items():
        classified.update(names)
    missing = journals - classified
    assert not missing, f"unclassified journeys: {sorted(missing)}"
    extra = classified - journals
    assert not extra, f"extra classes: {sorted(extra)}"


# ── engine bridge ─────────────────────────────────────────


def test_journey_engine_bridges_process_and_record(tmp_path, monkeypatch):
    """journey-engine._execute_action 对 process/record_result 走 doc_legs."""
    monkeypatch.setattr(doc_legs, "_ROOT", tmp_path)
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "good.md").write_text(
        "---\ntype: ssot\nowner: x\nlast-reviewed: 2099-01-01\n---\n# T\nline\nline\n",
        encoding="utf-8",
    )
    mod = _load("je", "bin/ssot/journey-engine.py")
    ctx = mod.ExecutionContext("scene-documents-test", "documents-test-journey",
                               {"source": "workspace_docs", "signal": "doc.changed",
                                "raw_item": {"path": "docs/good.md"}})

    # process → 累积检查结果
    r_proc = mod._execute_doc_legs_action("process", ctx)
    assert r_proc["action"] == "process" and r_proc["checks"] > 0

    # record_result → 聚合 + 签名
    r_rec = mod._execute_doc_legs_action("record_result", ctx)
    assert r_rec["status"] == "succeeded"
    assert r_rec["record"]["record_hash"]


def test_journey_engine_process_without_checks_is_partial(tmp_path, monkeypatch):
    """无检查结果时 record_result 返回 partial."""
    mod = _load("je", "bin/ssot/journey-engine.py")
    ctx = mod.ExecutionContext("scene-x", "journey-x", {})
    r = mod._execute_doc_legs_action("record_result", ctx)
    assert r["status"] == "partial"