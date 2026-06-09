"""Tests for dashboard_monitor.sh Round 14 P0 — 写合规 OmoHistoryRecord.

覆盖:
  1. override env var 注入: bash 脚本写出的 record 通过 OmoHistoryRecord schema 校验
  2. 必填字段全部就位: date/total_score/grade/watchlist_count 4 字段不缺失
  3. exit code 仍正确: launchd_state=down → exit 2, http_code=500 → exit 1, 都 200 → exit 0
  4. 不污染生产: 跑完测试后 unset override env (防止下游 test 误用)

设计: bash 脚本在测试环境无法真起 launchd / dashboard HTTP server.
      所以脚本加 LAUNCHD_STATE_OVERRIDE / HTTP_CODE_OVERRIDE / PID_OVERRIDE 3 个 env var
      让测试可以注入 mock 值, 跳过真 launchd/curl 调用.
      生产环境这些 var 不应被设 (脚本里默认值 = 真 launchd/curl 路径).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

OMO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = OMO_ROOT / "scripts" / "dashboard_monitor.sh"


# ── Fixture: 隔离 workspace + unset 3 个 override (防污染) ──


@pytest.fixture
def fake_workspace(tmp_path, monkeypatch):
    """设 WORKSPACE 指向 tmp_path, 重置 3 个 override env, 起一个空 history."""
    monkeypatch.setenv("WORKSPACE", str(tmp_path))
    monkeypatch.delenv("LAUNCHD_STATE_OVERRIDE", raising=False)
    monkeypatch.delenv("HTTP_CODE_OVERRIDE", raising=False)
    monkeypatch.delenv("PID_OVERRIDE", raising=False)
    history = tmp_path / ".omo" / "_knowledge" / "governance-history.jsonl"
    history.parent.mkdir(parents=True, exist_ok=True)
    history.write_text("", encoding="utf-8")
    return tmp_path


def _run_dashboard_monitor(
    tmp_path: Path,
    *,
    launchd_state: str,
    http_code: str,
    pid: str = "7777",
) -> subprocess.CompletedProcess:
    """跑 dashboard_monitor.sh 一次, 注入 mock launchd/http/pid."""
    env = {
        **os.environ,
        "WORKSPACE": str(tmp_path),
        "LAUNCHD_STATE_OVERRIDE": launchd_state,
        "HTTP_CODE_OVERRIDE": http_code,
        "PID_OVERRIDE": pid,
        "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",  # 限制 PATH 防止意外
    }
    return subprocess.run(
        ["bash", str(SCRIPT)],
        capture_output=True,
        text=True,
        env=env,
        timeout=10,
    )


def _read_last_record(tmp_path: Path) -> dict:
    """读 history 最后一条 JSON record."""
    history = tmp_path / ".omo" / "_knowledge" / "governance-history.jsonl"
    lines = [l for l in history.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(lines) == 1, f"expected 1 record, got {len(lines)}"
    return json.loads(lines[-1])


# ── 1. record 合规 OmoHistoryRecord schema ───────────────


def test_dashboard_monitor_writes_valid_omo_history_record(fake_workspace):
    """脚本写出的 record 必须通过 OmoHistoryRecord.model_validate()."""
    from omo.omo_io_schemas import OmoHistoryRecord

    r = _run_dashboard_monitor(
        fake_workspace,
        launchd_state="running",
        http_code="200",
        pid="12345",
    )
    assert r.returncode == 0, f"stderr: {r.stderr}"

    rec = _read_last_record(fake_workspace)
    # Pydantic 校验: 不抛 = 通过
    validated = OmoHistoryRecord.model_validate(rec)
    assert validated.source == "dashboard_monitor"
    assert validated.date == "2026-06-09" or len(validated.date) == 10  # YYYY-MM-DD
    assert validated.total_score == 0.0
    assert validated.grade.value == "F"  # Enum 自动转
    assert validated.watchlist_count == 0


# ── 2. 必填字段全部就位 (防回归) ────────────────────────


def test_dashboard_monitor_record_has_all_required_fields(fake_workspace):
    """record 含 OmoHistoryRecord 6 必填字段 (date/timestamp/total_score/grade/watchlist_count + Z-suffix ts)."""
    from omo.omo_io_schemas import OmoHistoryRecord

    _run_dashboard_monitor(
        fake_workspace, launchd_state="running", http_code="200", pid="99"
    )
    rec = _read_last_record(fake_workspace)

    required = set(OmoHistoryRecord.model_fields.keys())
    missing = required - set(rec.keys())
    assert not missing, f"record 缺必填字段: {missing} (audit 会报 drift)"

    # 额外字段保留 (extra='allow'): launchd_state/http_code/pid/port
    extra = set(rec.keys()) - required
    assert "launchd_state" in extra
    assert "http_code" in extra
    assert "pid" in extra
    assert "port" in extra

    # ts 必须是 Z 结尾 (ZTimestampModel)
    assert rec["timestamp"].endswith("Z")
    # date 必须是 YYYY-MM-DD
    import re
    assert re.match(r"^\d{4}-\d{2}-\d{2}$", rec["date"])


# ── 3. exit code 仍正确 (3 种状态) ─────────────────────


@pytest.mark.parametrize(
    "launchd_state,http_code,expected_exit",
    [
        ("down", "000", 2),  # launchd 未跑
        ("running", "500", 1),  # launchd 跑但 HTTP 异常
        ("running", "200", 0),  # 全 OK
    ],
)
def test_dashboard_monitor_exit_codes(fake_workspace, launchd_state, http_code, expected_exit):
    """脚本退出码反映健康状态, 不因 schema 改动而破坏."""
    r = _run_dashboard_monitor(
        fake_workspace,
        launchd_state=launchd_state,
        http_code=http_code,
    )
    assert r.returncode == expected_exit, (
        f"launchd={launchd_state} http={http_code}: expected exit {expected_exit}, "
        f"got {r.returncode}, stderr: {r.stderr}"
    )
    # record 仍写入 (无论状态)
    rec = _read_last_record(fake_workspace)
    assert rec["launchd_state"] == launchd_state
    assert rec["http_code"] == http_code
