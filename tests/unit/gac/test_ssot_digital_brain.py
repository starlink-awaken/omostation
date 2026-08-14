"""Unit tests for the digital-brain modules added in PR #1465 (bin/ssot/).

Covers pure logic paths that do NOT require LLM/network or user mailboxes:
  - risk_engine:   domain overrides, _risk_to_level boundaries, trust dynamics
  - health_agent:  analyze_trends empty-data degradation, briefing stats
  - mail_agent:    classify_mail fallback, generate_briefing layout
  - admin_scenes:  ADMIN_SCENES registry, inbox empty path
  - deadline_tracker: register_task round-trip with tmp TASKS_FILE
  - doc_generator: generate_doc fallback, save_draft to tmp DRAFTS_DIR
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

WORKSPACE = Path(__file__).resolve().parents[3]
SSOT_DIR = WORKSPACE / "bin" / "ssot"


def _load(name: str, filename: str):
    """Load a bin/ssot module by path (sibling imports resolved via sys.path)."""
    path = SSOT_DIR / filename
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


# ── risk_engine ────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def risk_engine():
    return _load("ssot_risk_engine", "risk_engine.py")


def test_risk_domain_overrides(risk_engine):
    engine = risk_engine.RiskEngine()
    cases = [
        # (domain, type, target, expected_level)
        ("work", "read", "self", "L0"),
        ("work", "generate", "self", "L0"),
        ("work", "send_email", "leader", "L3"),
        ("work", "send_email", "external", "L4"),
        ("work", "submit", "superior", "L3"),
        ("work", "forward", "subordinate", "L2"),
        ("family", "send_email", "spouse", "L0"),
        ("health", "generate", "report", "L0"),
    ]
    for domain, atype, target, expected in cases:
        d = engine.evaluate(risk_engine.Action(type=atype, target=target, domain=domain))
        assert d.level == expected, f"{atype}:{target}@{domain} → {d.level}, want {expected}"


def test_risk_to_level_boundaries(risk_engine):
    engine = risk_engine.RiskEngine()
    assert engine._risk_to_level(2.0) == "L0"
    assert engine._risk_to_level(2.1) == "L1"
    assert engine._risk_to_level(4.0) == "L1"
    assert engine._risk_to_level(4.1) == "L2"
    assert engine._risk_to_level(6.0) == "L2"
    assert engine._risk_to_level(6.1) == "L3"
    assert engine._risk_to_level(8.0) == "L3"
    assert engine._risk_to_level(8.1) == "L4"
    assert engine._risk_to_level(99.0) == "L4"


def test_risk_high_risk_score_without_override(risk_engine):
    engine = risk_engine.RiskEngine()
    d = engine.evaluate(risk_engine.Action(
        type="delete", target="public", sensitivity="secret",
        reversibility="permanent", confidence=1.0, domain="personal",
    ))
    assert d.level == "L4"
    assert d.risk_score > 8


def test_decision_helpers(risk_engine):
    assert risk_engine.Decision(level="L0").can_auto_execute() is True
    assert risk_engine.Decision(level="L1").can_auto_execute() is True
    assert risk_engine.Decision(level="L2").can_auto_execute() is False
    assert risk_engine.Decision(level="L2").needs_confirmation() is True
    assert risk_engine.Decision(level="L3").needs_confirmation() is True
    assert risk_engine.Decision(level="L4").is_forbidden() is True
    assert risk_engine.Decision(level="L0").is_forbidden() is False


def test_trust_success_lowers_level(risk_engine, tmp_path, monkeypatch):
    """success>=10 & score>0.8 → level drops one notch."""
    monkeypatch.setattr(risk_engine, "TRUST_FILE", tmp_path / "trust.json")
    engine = risk_engine.RiskEngine()
    action = risk_engine.Action(type="send_email", target="leader")  # base L3
    # prime trust to a high-score history
    trust = {"send_email:leader": {"score": 0.9, "success": 12, "fail": 0}}
    risk_engine.TRUST_FILE.write_text(json.dumps(trust), encoding="utf-8")
    d = engine.evaluate(action)
    assert d.level == "L2"
    assert d.trust_adjusted is True


def test_trust_failure_raises_level(risk_engine, tmp_path, monkeypatch):
    """fail>0 & score<0.3 → level rises one notch."""
    monkeypatch.setattr(risk_engine, "TRUST_FILE", tmp_path / "trust.json")
    engine = risk_engine.RiskEngine()
    action = risk_engine.Action(type="read", target="self")  # base L0 via override
    trust = {"read:self": {"score": 0.2, "success": 0, "fail": 3}}
    risk_engine.TRUST_FILE.write_text(json.dumps(trust), encoding="utf-8")
    d = engine.evaluate(action)
    assert d.level == "L1"
    assert d.trust_adjusted is True


def test_record_outcome_updates_trust(risk_engine, tmp_path, monkeypatch):
    monkeypatch.setattr(risk_engine, "TRUST_FILE", tmp_path / "trust.json")
    engine = risk_engine.RiskEngine()
    action = risk_engine.Action(type="read", target="self")
    engine.record_outcome(action, success=True)
    data = json.loads(risk_engine.TRUST_FILE.read_text(encoding="utf-8"))
    assert data["read:self"]["success"] == 1
    assert data["read:self"]["score"] == pytest.approx(0.6)
    engine.record_outcome(action, success=False)
    data = json.loads(risk_engine.TRUST_FILE.read_text(encoding="utf-8"))
    assert data["read:self"]["fail"] == 1
    assert data["read:self"]["score"] == pytest.approx(0.1)


def test_risk_engine_cli_json(risk_engine):
    proc = subprocess.run(
        [sys.executable, str(SSOT_DIR / "risk_engine.py"), "--type", "read", "--target", "self", "--json"],
        cwd=WORKSPACE, capture_output=True, text=True, timeout=60, check=False,
    )
    assert proc.returncode == 0
    out = json.loads(proc.stdout)
    assert out["level"] == "L0"
    assert out["action"] == "read"


# ── health_agent ──────────────────────────────────────────────────


@pytest.fixture(scope="module")
def health_agent():
    return _load("ssot_health_agent", "health_agent.py")


def test_analyze_trends_no_data(health_agent):
    result = health_agent.analyze_trends([])
    assert result["trend"] == "no_data"
    assert "无健康报告数据" in result["analysis"]


def test_analyze_trends_llm_down(health_agent, monkeypatch):
    monkeypatch.setattr(health_agent, "llm_ask", lambda *a, **k: None)
    reports = [{"date": "2026-08-14", "status": "🟢", "warnings": 0, "ok": 3}]
    result = health_agent.analyze_trends(reports)
    assert result["trend"] == "unknown"
    assert result["analysis"] == "LLM 无响应"


def test_generate_health_briefing_stats(health_agent):
    reports = [
        {"date": "2026-08-13", "status": "🟢", "warnings": 0, "ok": 3},
        {"date": "2026-08-14", "status": "🟡", "warnings": 1, "ok": 2},
        {"date": "2026-08-15", "status": "🟢", "warnings": 0, "ok": 3},
    ]
    md = health_agent.generate_health_briefing(reports, {"trend": "stable"})
    assert "🟢: 2天" in md
    assert "🟡: 1天" in md
    assert "报告数: 3" in md
    assert "2026-08-15" in md


# ── mail_agent ────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def mail_agent():
    return _load("ssot_mail_agent", "mail_agent.py")


def test_classify_mail_llm_down_fallback(mail_agent, monkeypatch):
    monkeypatch.setattr(mail_agent, "llm_ask", lambda *a, **k: None)
    mail = mail_agent.Mail(subject="测试邮件", sender="ws-xxk@bjfsh.gov.cn", body="正文")
    result = mail_agent.classify_mail(mail)
    assert result["category"] == "未分类"
    assert result["summary"] == "测试邮件"


def test_extract_task_non_task_returns_none(mail_agent, monkeypatch):
    monkeypatch.setattr(mail_agent, "llm_ask", lambda *a, **k: None)
    mail = mail_agent.Mail(subject="通知", sender="a@b.c", body="")
    assert mail_agent.extract_task(mail, {"category": "通知"}) is None


def test_generate_briefing_sections(mail_agent, monkeypatch):
    monkeypatch.setattr(mail_agent, "llm_ask", lambda *a, **k: None)
    mail = mail_agent.Mail(subject="交数据", sender="leader@x.cn", body="本周五前提交数据")
    briefing = mail_agent.generate_briefing(
        [mail],
        [{"category": "任务", "priority": "high", "summary": "提交数据", "action_needed": "收集并提交"}],
    )
    assert "##" in briefing
    assert "交数据" in briefing


# ── admin_scenes ──────────────────────────────────────────────────


@pytest.fixture(scope="module")
def admin_scenes():
    return _load("ssot_admin_scenes", "admin_scenes.py")


def test_admin_scenes_registry(admin_scenes):
    assert set(admin_scenes.ADMIN_SCENES.keys()) == {
        "admin-inbox", "admin-classify", "admin-forward", "admin-collect",
        "admin-compile", "admin-review", "admin-submit",
    }
    for handler in admin_scenes.ADMIN_SCENES.values():
        assert callable(handler)


def test_admin_inbox_empty(admin_scenes, monkeypatch):
    """No mails → has_task False, no crash."""
    monkeypatch.setattr(
        sys.modules["mail_reader"], "read_netease_mail",
        lambda *a, **k: [],
    )
    result = admin_scenes.dispatch_admin_inbox({}, {"user": "test"})
    assert result["status"] == "succeeded"
    assert result["has_task"] is False
    assert result["mails"] == []


# ── deadline_tracker ──────────────────────────────────────────────


@pytest.fixture(scope="module")
def deadline_tracker():
    return _load("ssot_deadline_tracker", "deadline_tracker.py")


def test_register_task_roundtrip(deadline_tracker, tmp_path, monkeypatch):
    monkeypatch.setattr(deadline_tracker, "TASKS_FILE", tmp_path / "tasks.json")
    deadline_tracker.register_task("交数据", "2026-08-20", "卫健委", "收集数据")
    tasks = deadline_tracker.load_tasks()
    assert len(tasks) == 1
    assert tasks[0]["subject"] == "交数据"
    assert tasks[0]["target"] == "卫健委"
    assert tasks[0]["status"] == "pending"
    assert tasks[0]["replies"] == []


def test_check_deadlines_empty(deadline_tracker, tmp_path, monkeypatch):
    monkeypatch.setattr(deadline_tracker, "TASKS_FILE", tmp_path / "tasks.json")
    result = deadline_tracker.check_deadlines()
    assert result["checked"] == 0
    assert result["alerts"] == []


# ── doc_generator ─────────────────────────────────────────────────


@pytest.fixture(scope="module")
def doc_generator():
    return _load("ssot_doc_generator", "doc_generator.py")


def test_generate_doc_llm_down_fallback(doc_generator, monkeypatch):
    monkeypatch.setattr(doc_generator, "llm_ask", lambda *a, **k: None)
    content = doc_generator.generate_doc("forward_notice", {"title": "转发通知"})
    assert "(生成失败)" in content


def test_save_draft_to_tmp(doc_generator, tmp_path, monkeypatch):
    monkeypatch.setattr(doc_generator, "DRAFTS_DIR", tmp_path)
    path = doc_generator.save_draft("forward_notice", "# 转发通知\n\n正文")
    assert path.exists()
    assert "forward_notice" in path.name
    assert "# 转发通知" in path.read_text(encoding="utf-8")
