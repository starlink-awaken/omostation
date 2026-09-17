"""公文审查能力腿 — 检查器 + 引擎 action 接线回归测试.

背景: journey-document-review 声明 5 个能力腿但引擎未实现 (返回空壳 succeeded).
本测试锁死"能力腿真实执行 + 置信度由检查结果驱动"这两条不变量.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


drc = _load("doc_review_checks", "bin/ssot/doc-review-checks.py")

GOOD_DOC = """---
type: ssot
owner: governance-team
last-reviewed: 2099-01-01
---

# 合规文档

正文若干行。
见 [相关](./other.md)。
"""

BAD_DOC = """# 无 frontmatter

sk-abcdefghijklmnopqrstuv
password: hunter2
/Users/example/.ssh/id_rsa
[坏链](nope.md)
"""


def _write(root: Path, name: str, text: str) -> str:
    p = root / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    # 文档中被引用的相对链接目标需与其同级存在
    (p.parent / "other.md").write_text("# other\n", encoding="utf-8")
    return name


# ── 检查器 ─────────────────────────────────────────────────────────────


def test_clean_document_scores_full_confidence(tmp_path):
    name = _write(tmp_path, "docs/good.md", GOOD_DOC)
    result = drc.review(name, tmp_path)
    assert result["loaded"] is True
    assert result["confidence"] == 1.0
    assert result["issues"] == []


def test_dirty_document_flags_every_leg(tmp_path):
    name = _write(tmp_path, "docs/bad.md", BAD_DOC)
    result = drc.review(name, tmp_path)
    kinds = {i["kind"] for i in result["issues"]}
    assert {"missing_frontmatter", "credential", "assignment_secret",
            "private_path", "broken_relative_link"} <= kinds
    assert result["confidence"] < 0.5


def test_path_outside_workspace_rejected(tmp_path):
    outside = tmp_path.parent / "outside.md"
    outside.write_text("# x\n", encoding="utf-8")
    result = drc.load_document(outside, tmp_path)
    assert result["ok"] is False
    assert result["reason"] == "path_outside_workspace"


def test_missing_file_is_not_success(tmp_path):
    result = drc.load_document("docs/nope.md", tmp_path)
    assert result["ok"] is False and result["reason"] == "file_missing"


def test_confidence_falls_back_without_checks():
    assert drc.confidence_of() == 0.85


# ── 引擎接线 ───────────────────────────────────────────────────────────


def _load_engine():
    return _load("je_legs", "bin/ssot/journey-engine.py")


JOURNEY_YAML = """schema: journey-spec/v3
journey_id: journey-document-review
name: 公文审查旅程
initial_state: detected
states:
  - {name: detected, type: initial}
  - {name: load_document, type: task, action: load_document}
  - {name: format_check, type: task, action: check_format}
  - {name: sensitivity_check, type: task, action: check_sensitivity}
  - {name: basis_verification, type: task, action: verify_basis}
  - {name: decision_generation, type: task, action: generate_decision}
  - {name: review_gate, type: human_gate, requires_human: true}
  - {name: recorded, type: task, action: record_decision}
  - {name: completed, type: final}
  - {name: escalated, type: final}
transitions:
  - {from: detected, to: load_document}
  - {from: load_document, to: format_check}
  - {from: format_check, to: sensitivity_check}
  - {from: sensitivity_check, to: basis_verification}
  - {from: basis_verification, to: decision_generation}
  - {from: decision_generation, to: review_gate}
  - {from: review_gate, to: recorded, condition: "confidence >= 0.7"}
  - {from: review_gate, to: escalated, condition: "confidence < 0.5"}
  - {from: recorded, to: completed}
"""

CARD_YAML = """schema: scene-card/v3
scene_id: scene-document-review
lifecycle: supervised
activation: active
runtime:
  journey_ref: journey-document-review
"""


def _stage(root: Path, mod) -> None:
    """在 tmp root 搭出真实的卡+旅程文件, 并让引擎从该 root 解析."""
    (root / ".omo/_truth/scenarios/v3").mkdir(parents=True, exist_ok=True)
    (root / ".omo/_truth/journeys/v3").mkdir(parents=True, exist_ok=True)
    (root / ".omo/_truth/scenarios/v3/scene-document-review.yaml").write_text(CARD_YAML)
    (root / ".omo/_truth/journeys/v3/journey-document-review.yaml").write_text(JOURNEY_YAML)
    mod._ROOT = root
    mod._scene_index = None          # 强制重建索引 (指向新 root)
    mod._scene_index_built_at = 0.0


def _silence(mod, monkeypatch) -> None:
    monkeypatch.setattr(mod, "_emit_scene_alert", lambda *a, **k: None)
    monkeypatch.setattr(mod, "_emit_omo_event", lambda *a, **k: None)
    monkeypatch.setattr(mod, "_auto_record_calibration", lambda *a, **k: None)
    monkeypatch.setattr(mod, "_record_auto_outcome", lambda *a, **k: None)


def test_journey_executes_capability_legs(tmp_path, monkeypatch):
    """scene-document-review 必须真实经过 5 个能力腿 state (非空壳)."""
    mod = _load_engine()
    _stage(tmp_path, mod)
    _silence(mod, monkeypatch)
    name = _write(tmp_path, "docs/good.md", GOOD_DOC)

    signal = {"source": "workspace_docs", "signal": "doc.changed",
              "raw_item": {"path": name, "title": "good"}}
    ctx = mod.execute_journey("scene-document-review", signal, dry_run=False)

    states = [s["state"] for s in ctx.trace]
    for required in ("load_document", "format_check", "sensitivity_check",
                     "basis_verification", "decision_generation"):
        assert required in states, f"能力腿 {required} 未执行: {states}"
    # 合规文档 → 置信度 1.0 → 越过 0.7 门 → 继续到 recorded/completed
    assert ctx.confidence >= 0.7, f"合规文档置信度应 >= 0.7, 实际 {ctx.confidence}"
    assert "recorded" in states


def test_journey_escalates_dirty_document(tmp_path, monkeypatch):
    """含敏感项/缺 frontmatter 的文档必须升级人审 (置信度驱动)."""
    mod = _load_engine()
    _stage(tmp_path, mod)
    _silence(mod, monkeypatch)
    name = _write(tmp_path, "docs/bad.md", BAD_DOC)

    signal = {"source": "workspace_docs", "signal": "doc.changed",
              "raw_item": {"path": name, "title": "bad"}}
    ctx = mod.execute_journey("scene-document-review", signal, dry_run=False)
    assert ctx.status == "escalated", f"实际 {ctx.status}: {ctx.output}"
    assert ctx.confidence < 0.5


def test_generate_decision_keeps_stub_fallback(monkeypatch):
    """无能力腿结果的场景仍走 0.85 回退 (不影响其它场景)."""
    mod = _load_engine()
    ctx = mod.ExecutionContext("scene-x", "journey-x", {})
    ctx.scene_card = {"scene_id": "scene-x", "runtime": {}}
    result = mod._execute_action("generate_decision", {}, ctx)
    assert result["confidence"] == 0.85
