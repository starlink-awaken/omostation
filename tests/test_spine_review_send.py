"""Tests for spine review workbench & send gateway (BET-Y1Q3-T10-116)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest

from cockpit.commands.spine import (
    _side_by_side_diff,
    cmd_spine_review,
    cmd_spine_send,
)


def test_side_by_side_diff_marks_changes():
    draft = "第一行\n为进一步推进该项工作。\n最后一行"
    edited = "第一行\n该项工作由各单位落实。\n最后一行\n新增行"
    left, right = _side_by_side_diff(draft, edited)
    assert any(l.startswith("- ") for l in left), "draft deletions unmarked"
    assert any(r.startswith("+ ") for r in right), "edited insertions unmarked"
    assert left[0].startswith("  ") and right[0].startswith("  ")


def test_review_json_payload(tmp_path: Path):
    d = tmp_path / "draft.txt"; d.write_text("甲\n乙\n", encoding="utf-8")
    e = tmp_path / "edited.txt"; e.write_text("甲\n丙\n", encoding="utf-8")
    args = argparse.Namespace(
        spine_command="review", draft="", edited="",
        draft_file=str(d), edited_file=str(e), json=True,
    )
    import io, contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = cmd_spine_review(args)
    assert rc == 0
    data = json.loads(buf.getvalue())
    assert data["draft_lines"] and data["edited_lines"]
    assert any(l.startswith("- ") for l in data["draft_lines"])


def test_send_queue_state_machine(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """queued → sent 状态机 + 价值台账原子追加。"""
    import cockpit.commands.spine as spine

    monkeypatch.setattr(spine, "_ws", lambda: tmp_path)
    body_file = tmp_path / "body.txt"
    body_file.write_text("正式外发内容", encoding="utf-8")

    args = argparse.Namespace(
        spine_command="send", body="", body_file=str(body_file),
        channel="smtp", to="xmx@example.gov", dry_run=False, sender="",
    )
    rc = cmd_spine_send(args)
    assert rc == 0

    spool = tmp_path / ".omo" / "state" / "spine-outbox"
    msg_dirs = [d for d in spool.iterdir() if d.is_dir()]
    assert len(msg_dirs) == 1
    env = json.loads((msg_dirs[0] / "envelope.json").read_text(encoding="utf-8"))
    assert env["status"] == "sent" and env["channel"] == "smtp"

    ledger = tmp_path / ".omo" / "state" / "value-pacing-ledger.jsonl"
    entries = [json.loads(l) for l in ledger.read_text(encoding="utf-8").splitlines() if l]
    assert len(entries) == 1 and entries[0]["msg_id"] == env["msg_id"]
    assert entries[0]["signed_chars"] == len("正式外发内容")


def test_send_dry_run_queues_without_ledger(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    import cockpit.commands.spine as spine

    monkeypatch.setattr(spine, "_ws", lambda: tmp_path)
    args = argparse.Namespace(
        spine_command="send", body="预检内容", body_file=None,
        channel="api", to="x@example", dry_run=True, sender="",
    )
    assert cmd_spine_send(args) == 0
    assert not (tmp_path / ".omo" / "state" / "value-pacing-ledger.jsonl").exists()


def test_send_failed_does_not_write_ledger(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """外发失败: failed 状态落盘、台账零写入（done_when 原子性反面）。"""
    import cockpit.commands.spine as spine

    monkeypatch.setattr(spine, "_ws", lambda: tmp_path)
    sender = tmp_path / "failing-sender.py"
    sender.write_text("import sys; sys.exit(1)\n", encoding="utf-8")
    args = argparse.Namespace(
        spine_command="send", body="会失败的内容", body_file=None,
        channel="api", to="x@example", dry_run=False, sender=str(sender),
    )
    assert cmd_spine_send(args) == 1
    spool = tmp_path / ".omo" / "state" / "spine-outbox"
    msg_dirs = [d for d in spool.iterdir() if d.is_dir()]
    env = json.loads((msg_dirs[0] / "envelope.json").read_text(encoding="utf-8"))
    assert env["status"] == "failed"
    assert not (tmp_path / ".omo" / "state" / "value-pacing-ledger.jsonl").exists()


def test_send_requires_body_and_target(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    import cockpit.commands.spine as spine

    monkeypatch.setattr(spine, "_ws", lambda: tmp_path)
    args = argparse.Namespace(
        spine_command="send", body="", body_file=None,
        channel="api", to="", dry_run=False, sender="",
    )
    assert cmd_spine_send(args) == 1
