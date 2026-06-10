"""Tests for omo event emit (Round 5 P3 — AppendOnlyLog 第 5 个 consumer)."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

OMO_SRC = Path(__file__).resolve().parents[1] / "src"
if str(OMO_SRC) not in sys.path:
    sys.path.insert(0, str(OMO_SRC))


def test_omo_event_emit_subprocess_writes_jsonl(tmp_path):
    """omo event emit 走 AppendOnlyLog 写 .jsonl, 含 4 字段 (ts, kind, source, payload)."""
    log_path = tmp_path / "omo-events.jsonl"
    r = subprocess.run(
        [
            sys.executable, "-m", "omo.omo_event", "emit",
            "--type", "test_event",
            "--source", "pytest",
            "--payload", '{"hello": "world"}',
            "--log", str(log_path),
        ],
        capture_output=True, text=True, timeout=15,
        cwd=str(OMO_SRC.parent.parent),
    )
    assert r.returncode == 0, f"stderr: {r.stderr}"
    assert "✅ event emitted" in r.stdout

    # 验证 log 写 1 条结构化 event
    lines = [l for l in log_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(lines) == 1
    event = json.loads(lines[0])
    assert event["kind"] == "test_event"
    assert event["source"] == "pytest"
    assert event["payload"] == '{"hello": "world"}'
    assert "ts" in event
    assert event["ts"].endswith("Z"), "ts must end with Z (omo_audit convention)"


def test_omo_event_emit_help_renders():
    """omo event --help 应列出 emit 子命令."""
    r = subprocess.run(
        [sys.executable, "-m", "omo.omo_event", "--help"],
        capture_output=True, text=True, timeout=10,
        cwd=str(OMO_SRC.parent.parent),
    )
    assert r.returncode == 0
    assert "emit" in r.stdout
    assert "list" in r.stdout


def test_omo_event_emit_default_log_path():
    """不传 --log 时落 .omo/_knowledge/omo-events.jsonl (默认)."""
    from omo.omo_event import DEFAULT_EVENT_LOG_PATH
    assert ".omo" in str(DEFAULT_EVENT_LOG_PATH)
    assert "knowledge" in str(DEFAULT_EVENT_LOG_PATH)
    assert DEFAULT_EVENT_LOG_PATH.name == "omo-events.jsonl"


def test_omo_event_emit_uses_append_only_log():
    """验证 emit 内部用 AppendOnlyLog (而非直接 open+write)."""
    from omo.omo_event import cmd_event_emit
    from omo.omo_io import AppendOnlyLog
    import inspect

    src = inspect.getsource(cmd_event_emit)
    assert "AppendOnlyLog" in src, "cmd_event_emit should use AppendOnlyLog abstraction"
