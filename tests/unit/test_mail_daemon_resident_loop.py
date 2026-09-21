"""Unit tests for Mail Daemon resident loop, event emission, and cockpit inbox projection (BET-Y2Q1-T4-02)."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

WORKSPACE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(WORKSPACE / "bin" / "ssot"))

import mail_daemon


def test_mail_daemon_status_stopped(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """验证守护进程停止状态下的诊断输出。"""
    fake_pid_file = tmp_path / "daemon.pid"
    fake_heartbeat = tmp_path / "heartbeat.jsonl"
    fake_inbox_tasks = tmp_path / "inbox-tasks.json"

    monkeypatch.setattr(mail_daemon, "PID_FILE", fake_pid_file)
    monkeypatch.setattr(mail_daemon, "HEARTBEAT", fake_heartbeat)
    monkeypatch.setattr(mail_daemon, "COCKPIT_INBOX_TASKS", fake_inbox_tasks)

    st = mail_daemon.get_status()
    assert st["daemon"] == "mail_daemon"
    assert st["running"] is False
    assert st["pid"] is None
    assert st["status"] == "stopped"
    assert st["pending_inbox_tasks"] == 0


def test_mail_daemon_status_running(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """验证当 PID 存活时，诊断报告 running 状态。"""
    fake_pid_file = tmp_path / "daemon.pid"
    fake_heartbeat = tmp_path / "heartbeat.jsonl"
    fake_inbox_tasks = tmp_path / "inbox-tasks.json"

    my_pid = os.getpid()
    fake_pid_file.write_text(str(my_pid), encoding="utf-8")
    fake_heartbeat.write_text(json.dumps({"ts": "2026-09-21T07:00:00Z", "mails": 5, "tasks": 1, "drafts": 1}) + "\n", encoding="utf-8")

    monkeypatch.setattr(mail_daemon, "PID_FILE", fake_pid_file)
    monkeypatch.setattr(mail_daemon, "HEARTBEAT", fake_heartbeat)
    monkeypatch.setattr(mail_daemon, "COCKPIT_INBOX_TASKS", fake_inbox_tasks)

    st = mail_daemon.get_status()
    assert st["running"] is True
    assert st["pid"] == my_pid
    assert st["status"] == "healthy"
    assert st["last_heartbeat"]["tasks"] == 1


def test_emit_signal_ingressed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """验证发射 SignalIngressed 事件到事件总线。"""
    fake_events = tmp_path / "events.jsonl"
    monkeypatch.setattr(mail_daemon, "EVENTS_JSONL", fake_events)

    fake_mail = MagicMock()
    fake_mail.subject = "关于市医保结算专网对接的函"
    fake_mail.sender = "yibao@city.gov.cn"

    fake_cls = {"category": "任务", "priority": "high"}
    fake_task = {"task_type": "summary_report", "summary": "跟进专网对接工作"}
    fake_journey = {"subject": fake_mail.subject, "ok": True}

    ev = mail_daemon._emit_signal_ingressed(fake_mail, fake_cls, fake_task, fake_journey)
    assert ev["event_type"] == "SignalIngressed"
    assert ev["topic"] == "mesh:signal:mail"
    assert ev["source"] == "apple_mail"
    assert "市医保结算专网" in ev["subject"]
    assert ev["journey_triggered"] is True

    assert fake_events.exists()
    lines = fake_events.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    recorded = json.loads(lines[0])
    assert recorded["event_type"] == "SignalIngressed"


def test_project_to_cockpit_inbox(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """验证待办与初稿原子投影到 Cockpit inbox-tasks.json 且支持去重。"""
    fake_inbox = tmp_path / "inbox-tasks.json"
    monkeypatch.setattr(mail_daemon, "COCKPIT_INBOX_TASKS", fake_inbox)

    fake_mail = MagicMock()
    fake_mail.subject = "新药审批流程改革征求意见稿"
    fake_mail.sender = "fda-review@gov.cn"
    fake_cls = {"category": "任务", "priority": "normal"}
    fake_task = {"task_type": "forward_notice", "summary": "征求科室意见"}

    # 第一次投影
    mail_daemon._project_to_cockpit_inbox(fake_mail, fake_cls, fake_task, {"ok": True})
    assert fake_inbox.exists()
    data = json.loads(fake_inbox.read_text(encoding="utf-8"))
    assert len(data["tasks"]) == 1
    assert data["tasks"][0]["subject"] == "新药审批流程改革征求意见稿"
    assert data["tasks"][0]["status"] == "pending_review"

    # 第二次重复投影（防重入）
    mail_daemon._project_to_cockpit_inbox(fake_mail, fake_cls, fake_task, {"ok": True})
    data2 = json.loads(fake_inbox.read_text(encoding="utf-8"))
    assert len(data2["tasks"]) == 1


def test_resident_routes_has_signal_ingressed():
    """验证 resident-routes.yaml 包含 SignalIngressed 规则。"""
    routes_file = WORKSPACE / "bin" / "ssot" / "resident-routes.yaml"
    assert routes_file.is_file()
    payload = yaml.safe_load(routes_file.read_text(encoding="utf-8"))
    routes = payload.get("routes", [])
    matches = [r for r in routes if r.get("event_type") == "SignalIngressed" and r.get("topic") == "mesh:signal:mail"]
    assert len(matches) == 1
    assert matches[0]["safe"] is True
