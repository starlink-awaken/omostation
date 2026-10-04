"""督办台账(deadline_tracker)的 owner/去重/会议类跳过邮件回复匹配/写面重定向。"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

WORKSPACE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(WORKSPACE / "bin" / "ssot"))

import deadline_tracker  # noqa: E402


@pytest.fixture()
def ledger(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    f = tmp_path / "tracked-tasks.json"
    monkeypatch.setattr(deadline_tracker, "TASKS_FILE", f)
    yield f


def test_register_task_owner_and_dedupe(ledger: Path):
    deadline_tracker.register_task("数据安全自查", "2026-10-12", "张磊", "meeting-supervision", owner="张磊")
    deadline_tracker.register_task("数据安全自查", "2026-10-12", "张磊", "meeting-supervision", owner="张磊")
    tasks = deadline_tracker.load_tasks()
    assert len(tasks) == 1 and tasks[0]["owner"] == "张磊"


def test_meeting_task_skips_reply_matching(ledger: Path, monkeypatch: pytest.MonkeyPatch):
    """会议督办不按邮件标题关键词判「已回复」——否则撞题的任何邮件都会误闭环。"""
    called = []
    monkeypatch.setattr(deadline_tracker, "read_netease_mail", lambda *a, **k: called.append(1) or [])
    t = {"subject": "信创替代推进会", "task_type": "meeting-supervision"}
    assert deadline_tracker.check_replies(t) == []
    assert not called  # 根本不该去读邮箱


def test_env_redirect(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """env 晚于 import 声明也必须生效——不 reload，路径在调用时解析。"""
    monkeypatch.setenv("OMO_TRACKED_TASKS", str(tmp_path / "x.json"))
    assert deadline_tracker.tasks_file() == tmp_path / "x.json"
    assert deadline_tracker.load_tasks() == []  # 缺失文件按空台账，不炸


def test_explicit_override_wins_over_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """既有 monkeypatch.setattr(TASKS_FILE) 用例的语义不变：覆盖位优先于 env。"""
    monkeypatch.setenv("OMO_TRACKED_TASKS", str(tmp_path / "env.json"))
    monkeypatch.setattr(deadline_tracker, "TASKS_FILE", tmp_path / "override.json")
    assert deadline_tracker.tasks_file() == tmp_path / "override.json"
