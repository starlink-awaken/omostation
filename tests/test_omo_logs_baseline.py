"""Tests for omo logs audit --baseline-init / --baseline-check (Round 13 P0).

设计: 写一个 fixture fake_workspace 隔离 .omo/_knowledge/ 目录, 通过 monkeypatch
      注入 omo_logs 模块的 _WORKSPACE / KNOWLEDGE_DIR 指向 tmp_path.

覆盖场景:
  1. --baseline-init 创建文件 + JSON 包含 drift_by_consumer / total_drift / total_records
  2. --baseline-check 当前 drift == baseline → exit 0
  3. --baseline-check 新增 drift (回归) → exit 1 + 提示 ❌ 回归
  4. --baseline-check baseline 不存在 → exit 1 + 提示 ❌ baseline 不存在
  5. --baseline-check 改善 (drift 减少) → exit 0 + 提示 ✅ 改善
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

OMO_SRC = Path(__file__).resolve().parents[1] / "src"
if str(OMO_SRC) not in sys.path:
    sys.path.insert(0, str(OMO_SRC))


# ── Fixture: 隔离 workspace + 准备 KNOWLEDGE_DIR ───────────


@pytest.fixture
def fake_workspace(tmp_path, monkeypatch):
    """设 WORKSPACE_ROOT + 准备 .omo/_knowledge/ 目录, 注入 omo_logs 模块.

    Returns:
        tmp_path (workspace 根)
    """
    # 修 omo_logs 模块常量, 让 _list_log_paths() 走 tmp_path
    from omo import omo_logs
    monkeypatch.setattr(omo_logs, "_WORKSPACE", tmp_path)
    monkeypatch.setattr(omo_logs, "KNOWLEDGE_DIR", tmp_path / ".omo" / "_knowledge")
    knowledge = tmp_path / ".omo" / "_knowledge"
    knowledge.mkdir(parents=True, exist_ok=True)
    return tmp_path


def _append_drift_record(jsonl_path: Path, date_str: str) -> None:
    """Append 1 条 schema 不全的 record (drift). 模拟 omo_history 缺字段."""
    from omo.omo_io import AppendOnlyLog
    log = AppendOnlyLog(jsonl_path)
    # 故意缺 timestamp / total_score / grade / watchlist_count 字段
    log.append({"date": date_str})


# ── 1. --baseline-init 创建文件 + 完整 JSON ──────────────


def test_baseline_init_creates_file_with_full_payload(fake_workspace, capsys):
    """--baseline-init 写 baseline 文件, 含 drift_by_consumer / total_drift / total_records."""
    from omo.omo_logs import cmd_logs_audit

    knowledge = fake_workspace / ".omo" / "_knowledge"
    _append_drift_record(knowledge / "omo-history.jsonl", "2026-06-09")

    out_path = fake_workspace / "baseline.json"
    rc = cmd_logs_audit(baseline_init=str(out_path))

    assert rc == 0, "init 模式成功应 exit 0"
    assert out_path.exists(), "baseline 文件应已创建"

    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert "drift_by_consumer" in payload
    assert "total_drift" in payload
    assert "total_records" in payload
    assert "generated_at" in payload
    assert "_comment" in payload
    # 1 条 drift 落在 omo_history
    assert payload["drift_by_consumer"]["omo_history"] == 1
    assert payload["total_drift"] == 1
    assert payload["total_records"] == 1

    # 提示语校验
    captured = capsys.readouterr()
    assert "✅ baseline 写入" in captured.out
    assert "omo_history: 1" in captured.out


# ── 2. --baseline-check 当前 == baseline → exit 0 ────────


def test_baseline_check_passes_when_unchanged(fake_workspace, capsys):
    """当前 drift == baseline, exit 0 + ✅ 不变 提示."""
    from omo.omo_logs import cmd_logs_audit

    knowledge = fake_workspace / ".omo" / "_knowledge"
    _append_drift_record(knowledge / "omo-history.jsonl", "2026-06-09")
    baseline = fake_workspace / "baseline.json"

    # 先 init
    assert cmd_logs_audit(baseline_init=str(baseline)) == 0

    # 再 check: 应 pass
    rc = cmd_logs_audit(baseline_check=str(baseline))
    assert rc == 0, "0 增量应 pass"

    captured = capsys.readouterr()
    assert "✅ baseline check pass" in captured.out
    assert "不变" in captured.out  # 不变 / 改善 / 回归 三选一


# ── 3. --baseline-check 新增 drift → exit 1 ──────────────


def test_baseline_check_fails_on_regression(fake_workspace, capsys):
    """新代码引入 drift (回归), exit 1 + ❌ 回归 提示."""
    from omo.omo_logs import cmd_logs_audit

    knowledge = fake_workspace / ".omo" / "_knowledge"
    _append_drift_record(knowledge / "omo-history.jsonl", "2026-06-09")
    baseline = fake_workspace / "baseline.json"

    assert cmd_logs_audit(baseline_init=str(baseline)) == 0

    # 引入新 drift
    _append_drift_record(knowledge / "omo-history.jsonl", "2026-06-10")

    rc = cmd_logs_audit(baseline_check=str(baseline))
    assert rc == 1, "回归应 fail"

    captured = capsys.readouterr()
    assert "❌" in captured.out
    assert "回归" in captured.out
    assert "baseline check fail" in captured.out


# ── 4. --baseline-check baseline 不存在 → exit 1 ────────


def test_baseline_check_fails_when_baseline_missing(fake_workspace, capsys):
    """baseline 文件不存在, exit 1 + ❌ baseline 不存在 提示."""
    from omo.omo_logs import cmd_logs_audit

    missing = fake_workspace / "nope.json"
    assert not missing.exists()

    rc = cmd_logs_audit(baseline_check=str(missing))
    assert rc == 1

    captured = capsys.readouterr()
    assert captured.err  # stderr 有提示
    assert "❌ baseline 不存在" in captured.err
    assert "--baseline-init" in captured.err  # 提示怎么 init


# ── 5. --baseline-check 改善 (drift 减少) → exit 0 ───────


def test_baseline_check_passes_on_improvement(fake_workspace, capsys):
    """drift 减少 (改善), exit 0 + ✅ 改善 提示.

    模拟方法: baseline 时记 2 drift, 然后重建 workspace 只剩 1 drift, check 1 < 2.
    """
    from omo.omo_logs import cmd_logs_audit

    knowledge = fake_workspace / ".omo" / "_knowledge"
    _append_drift_record(knowledge / "omo-history.jsonl", "2026-06-08")
    _append_drift_record(knowledge / "omo-history.jsonl", "2026-06-09")
    baseline = fake_workspace / "baseline.json"

    # baseline 含 2 drift
    payload = json.loads(Path(baseline).read_text()) if baseline.exists() else None
    assert cmd_logs_audit(baseline_init=str(baseline)) == 0
    init_payload = json.loads(baseline.read_text(encoding="utf-8"))
    assert init_payload["drift_by_consumer"]["omo_history"] == 2

# 删 1 条 (模拟"修好" — 清空 + 重写 1 条)
    from omo.omo_io import AppendOnlyLog
    log = AppendOnlyLog(knowledge / "omo-history.jsonl")
    log.path.write_text("", encoding="utf-8")  # 物理清空
    _append_drift_record(knowledge / "omo-history.jsonl", "2026-06-09")

    # 跑 check: 当前 1 drift, baseline 2 drift, 改善
    rc = cmd_logs_audit(baseline_check=str(baseline))
    assert rc == 0, "改善应 pass (无回归)"

    captured = capsys.readouterr()
    assert "✅" in captured.out
    assert "改善" in captured.out
