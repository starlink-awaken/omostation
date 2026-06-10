"""Tests for dashboard_monitor.sh Round 14 P0 + Round 20 P0.

Round 14 P0: 写合规 OmoHistoryRecord (4 占位字段, 治标)
Round 20 P0: 拆到独立 OmoHealthRecord + 写 omo-health.jsonl (治本)

覆盖:
  1. override env var 注入: bash 脚本写出的 record 通过 OmoHealthRecord schema 校验
  2. 必填字段全部就位: source/launchd_state/http_code/pid/port/timestamp 6 字段
  3. exit code 仍正确: launchd_state=down → exit 2, http_code=500 → exit 1, 都 200 → exit 0
  4. 写到 omo-health.jsonl (新), 不写 governance-history.jsonl (Round 20 P0 拆)
  5. OmoHealthRecord 在 SCHEMA_REGISTRY 第 8 个
  6. 不污染生产: 跑完测试后 unset override env
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
    """设 WORKSPACE 指向 tmp_path, 重置 3 个 override env, 起一个空 omo-health.jsonl."""
    monkeypatch.setenv("WORKSPACE", str(tmp_path))
    monkeypatch.delenv("LAUNCHD_STATE_OVERRIDE", raising=False)
    monkeypatch.delenv("HTTP_CODE_OVERRIDE", raising=False)
    monkeypatch.delenv("PID_OVERRIDE", raising=False)
    monkeypatch.delenv("HISTORY", raising=False)  # Round 20 P0: 不让外部 HISTORY 干扰
    health = tmp_path / ".omo" / "_knowledge" / "omo-health.jsonl"
    health.parent.mkdir(parents=True, exist_ok=True)
    health.write_text("", encoding="utf-8")
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
        "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
    }
    return subprocess.run(
        ["bash", str(SCRIPT)],
        capture_output=True,
        text=True,
        env=env,
        timeout=10,
    )


def _read_last_record(tmp_path: Path) -> dict:
    """读 omo-health.jsonl 最后一条 JSON record (Round 20 P0: 新路径)."""
    health = tmp_path / ".omo" / "_knowledge" / "omo-health.jsonl"
    lines = [l for l in health.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(lines) == 1, f"expected 1 record, got {len(lines)}"
    return json.loads(lines[-1])


# ── 1. record 合规 OmoHealthRecord schema ─────────────────


def test_dashboard_monitor_writes_valid_omo_health_record(fake_workspace):
    """脚本写出的 record 必须通过 OmoHealthRecord.model_validate()."""
    from omo.omo_io_schemas import OmoHealthRecord

    r = _run_dashboard_monitor(
        fake_workspace,
        launchd_state="running",
        http_code="200",
        pid="12345",
    )
    assert r.returncode == 0, f"stderr: {r.stderr}"

    rec = _read_last_record(fake_workspace)
    # Pydantic 校验: 不抛 = 通过
    validated = OmoHealthRecord.model_validate(rec)
    assert validated.source == "dashboard_monitor"
    assert validated.launchd_state.value == "running"
    assert validated.http_code == "200"
    assert validated.pid == "12345"
    assert validated.port == 9090


# ── 2. 必填字段全部就位 (防回归) ──────────────────────────


def test_dashboard_monitor_record_has_all_required_fields(fake_workspace):
    """record 含 OmoHealthRecord 6 必填字段 (source/launchd_state/http_code/pid/port/timestamp + Z-suffix ts)."""
    from omo.omo_io_schemas import OmoHealthRecord

    _run_dashboard_monitor(
        fake_workspace, launchd_state="running", http_code="200", pid="99"
    )
    rec = _read_last_record(fake_workspace)

    required = set(OmoHealthRecord.model_fields.keys())
    missing = required - set(rec.keys())
    assert not missing, f"record 缺必填字段: {missing} (audit 会报 drift)"

    # ts 必须是 Z 结尾 (ZTimestampModel)
    assert rec["timestamp"].endswith("Z")

    # 不含 OmoHistoryRecord 字段 (Round 20 P0: 治理历史不再被污染)
    assert "date" not in rec
    assert "total_score" not in rec
    assert "grade" not in rec
    assert "watchlist_count" not in rec


# ── 3. exit code 仍正确 (3 种状态) ─────────────────────


@pytest.mark.parametrize(
    "launchd_state,http_code,expected_exit",
    [
        ("down", "000", 2),
        ("running", "500", 1),
        ("running", "200", 0),
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
    rec = _read_last_record(fake_workspace)
    assert rec["launchd_state"] == launchd_state
    assert rec["http_code"] == http_code


# ── 4. 写到 omo-health.jsonl, 不写 governance-history.jsonl ─


def test_dashboard_monitor_writes_to_omo_health_not_governance_history(fake_workspace):
    """Round 20 P0: dashboard_monitor 写 .omo/_knowledge/omo-health.jsonl, 不再写 governance-history.jsonl."""
    _run_dashboard_monitor(fake_workspace, launchd_state="running", http_code="200", pid="42")

    knowledge_dir = fake_workspace / ".omo" / "_knowledge"
    health_log = knowledge_dir / "omo-health.jsonl"
    governance_log = knowledge_dir / "governance-history.jsonl"

    # omo-health.jsonl 必须出现 (1 条)
    assert health_log.exists(), "omo-health.jsonl 必须出现 (Round 20 P0)"
    health_lines = [l for l in health_log.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(health_lines) == 1

    # governance-history.jsonl 必须 NOT 出现 (本脚本不再写)
    assert not governance_log.exists(), (
        "governance-history.jsonl 不应被 dashboard_monitor 创建 "
        "(Round 20 P0 拆 — 治理历史不被健康监控污染)"
    )


# ── 5. OmoHealthRecord 在 SCHEMA_REGISTRY 第 8 个 ─────


def test_omo_health_schema_is_eighth_in_registry():
    """OmoHealthRecord 是 SCHEMA_REGISTRY 第 8 个 key (Round 20 P0)."""
    from omo.omo_io_schemas import SCHEMA_REGISTRY, OmoHealthRecord

    assert "omo_health" in SCHEMA_REGISTRY
    assert SCHEMA_REGISTRY["omo_health"] is OmoHealthRecord
    assert len(SCHEMA_REGISTRY) >= 8, f"expected ≥ 8 consumers, got {len(SCHEMA_REGISTRY)}"
    expected_keys = {
        "omo_audit", "omo_bos_metrics", "omo_sync", "omo_alert",
        "omo_event", "omo_history", "omo_trail", "omo_health",
    }
    actual_keys = set(SCHEMA_REGISTRY.keys())
    assert expected_keys.issubset(actual_keys), (
        f"missing: {expected_keys - actual_keys}"
    )
