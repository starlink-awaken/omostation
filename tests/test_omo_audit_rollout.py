"""Tests for omo audit-rollout (Round 27 P0 — §12.5.1 步骤 1 实质化).

覆盖:
  1. _read_baseline 读真实 baseline 文件, 返回结构化 dict
  2. _read_baseline 缺文件 → FileNotFoundError
  3. aggregate_baselines 多仓聚合 + summary 计算
  4. aggregate_baselines 单仓失败不阻塞其他仓
  5. render_rollout_table 终端汇总表正确
  6. parse_repos_arg 解析 'name:path' 格式
  7. CLI 退出码: 0 漂移 → exit 0, 有漂移 → exit 1, 错误 → exit 2
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

OMO_SRC = Path(__file__).resolve().parents[1] / "src"
if str(OMO_SRC) not in sys.path:
    sys.path.insert(0, str(OMO_SRC))


# ── 1. _read_baseline 基础 ────────────────────────────────


def test_read_baseline_returns_structured_dict(tmp_path):
    """读单仓 baseline, 返回 drift_by_consumer / total_drift / total_records."""
    from omo.omo_audit_rollout import _read_baseline

    # 准备 fake baseline 文件
    knowledge_dir = tmp_path / ".omo" / "_knowledge"
    knowledge_dir.mkdir(parents=True)
    baseline = {
        "_comment": "test",
        "drift_by_consumer": {"omo_audit": 0, "omo_bos_metrics": 5},
        "total_drift": 5,
        "total_records": 100,
    }
    (knowledge_dir / "_audit_baseline.json").write_text(
        json.dumps(baseline), encoding="utf-8"
    )

    data = _read_baseline(tmp_path)
    assert data["drift_by_consumer"] == {"omo_audit": 0, "omo_bos_metrics": 5}
    assert data["total_drift"] == 5
    assert data["total_records"] == 100


# ── 2. _read_baseline 缺文件 → FileNotFoundError ─────────


def test_read_baseline_missing_file_raises(tmp_path):
    """baseline 文件不存在 → FileNotFoundError."""
    import pytest
    from omo.omo_audit_rollout import _read_baseline

    with pytest.raises(FileNotFoundError):
        _read_baseline(tmp_path)


# ── 3. aggregate_baselines 多仓聚合 ──────────────────────


def test_aggregate_baselines_multi_repo(tmp_path):
    """2 仓聚合, summary 字段正确 (total_repos/total_drift/total_records/repos_with_drift)."""
    from omo.omo_audit_rollout import aggregate_baselines

    # 仓 1: omostation-like
    r1 = tmp_path / "r1"
    (r1 / ".omo" / "_knowledge").mkdir(parents=True)
    (r1 / ".omo" / "_knowledge" / "_audit_baseline.json").write_text(
        json.dumps({
            "drift_by_consumer": {"omo_history": 100},
            "total_drift": 100,
            "total_records": 1000,
        }), encoding="utf-8"
    )
    # 仓 2: kairon-like (0 漂移)
    r2 = tmp_path / "r2"
    (r2 / ".omo" / "_knowledge").mkdir(parents=True)
    (r2 / ".omo" / "_knowledge" / "_audit_baseline.json").write_text(
        json.dumps({
            "drift_by_consumer": {"kairon_event": 0},
            "total_drift": 0,
            "total_records": 50,
        }), encoding="utf-8"
    )

    rollout = aggregate_baselines([("omostation", r1), ("kairon", r2)])

    assert rollout["summary"]["total_repos"] == 2
    assert rollout["summary"]["total_drift"] == 100  # 100 + 0
    assert rollout["summary"]["total_records"] == 1050  # 1000 + 50
    assert rollout["summary"]["repos_with_drift"] == 1  # 仅 omostation
    assert "omostation" in rollout["repos"]
    assert "kairon" in rollout["repos"]
    assert rollout["repos"]["kairon"]["total_drift"] == 0


# ── 4. 单仓失败不阻塞其他仓 ─────────────────────────────


def test_aggregate_baselines_one_repo_fails_others_ok(tmp_path):
    """r1 缺 baseline, r2 正常 — rollout 仍聚合 r2, r1 记 error."""
    from omo.omo_audit_rollout import aggregate_baselines

    r1 = tmp_path / "r1"  # 缺 baseline
    r1.mkdir()
    r2 = tmp_path / "r2"
    (r2 / ".omo" / "_knowledge").mkdir(parents=True)
    (r2 / ".omo" / "_knowledge" / "_audit_baseline.json").write_text(
        json.dumps({
            "drift_by_consumer": {"x": 0},
            "total_drift": 0,
            "total_records": 10,
        }), encoding="utf-8"
    )

    rollout = aggregate_baselines([("broken", r1), ("ok", r2)])

    # 2 repos 都出现在 rollout
    assert rollout["summary"]["total_repos"] == 2
    # broken 标 error, ok 正常聚合
    assert "error" in rollout["repos"]["broken"]
    assert rollout["repos"]["ok"]["total_drift"] == 0
    # total_drift 只算成功的 (broken 不算 -1)
    assert rollout["summary"]["total_drift"] == 0


# ── 5. render_rollout_table 终端汇总表 ────────────────────


def test_render_rollout_table_contains_repos_and_total():
    """render_rollout_table 输出含 repo name + TOTAL 行."""
    from omo.omo_audit_rollout import aggregate_baselines, render_rollout_table

    rollout = aggregate_baselines([])  # 空 repos
    table = render_rollout_table(rollout)
    assert "audit-rollout" in table
    assert "TOTAL" in table
    assert "0 repos" in table


# ── 6. parse_repos_arg 解析 ──────────────────────────────


def test_parse_repos_arg_format():
    """'name:path' 格式解析为 [(name, Path), ...]."""
    from omo.omo_audit_rollout import parse_repos_arg

    repos = parse_repos_arg(["omostation:.", "kairon:projects/kairon", "metaos:projects/metaos"])
    assert len(repos) == 3
    assert repos[0][0] == "omostation"
    assert repos[0][1] == Path(".").resolve()
    assert repos[1][0] == "kairon"
    assert "kairon" in str(repos[1][1])


def test_parse_repos_arg_missing_colon_raises():
    """格式错 (无 ':') → ValueError."""
    import pytest
    from omo.omo_audit_rollout import parse_repos_arg

    with pytest.raises(ValueError):
        parse_repos_arg(["invalid_format"])


# ── 7. CLI 退出码 ──────────────────────────────────────


def test_cli_audit_rollout_with_drift_returns_1(tmp_path):
    """baseline 有 drift → CLI 退出码 1."""
    # 准备有 drift 的 baseline
    r1 = tmp_path / "r1"
    (r1 / ".omo" / "_knowledge").mkdir(parents=True)
    (r1 / ".omo" / "_knowledge" / "_audit_baseline.json").write_text(
        json.dumps({
            "drift_by_consumer": {"x": 10},
            "total_drift": 10,
            "total_records": 100,
        }), encoding="utf-8"
    )

    OMO_PROJ = Path(__file__).resolve().parents[1]
    r = subprocess.run(
        [
            sys.executable, "-m", "omo.cli", "audit-rollout",
            "--repos", f"test:{r1}",
            "--output", str(tmp_path / "out.json"),
        ],
        capture_output=True, text=True, timeout=15,
        cwd=str(OMO_PROJ),
    )
    assert r.returncode == 1, f"expected exit 1 (drift detected), got {r.returncode}, stderr: {r.stderr}"


def test_cli_audit_rollout_zero_drift_returns_0(tmp_path):
    """baseline 0 drift → CLI 退出码 0."""
    r1 = tmp_path / "r1"
    (r1 / ".omo" / "_knowledge").mkdir(parents=True)
    (r1 / ".omo" / "_knowledge" / "_audit_baseline.json").write_text(
        json.dumps({
            "drift_by_consumer": {"x": 0},
            "total_drift": 0,
            "total_records": 50,
        }), encoding="utf-8"
    )

    OMO_PROJ = Path(__file__).resolve().parents[1]
    r = subprocess.run(
        [
            sys.executable, "-m", "omo.cli", "audit-rollout",
            "--repos", f"test:{r1}",
            "--output", str(tmp_path / "out.json"),
        ],
        capture_output=True, text=True, timeout=15,
        cwd=str(OMO_PROJ),
    )
    assert r.returncode == 0, f"expected exit 0 (zero drift), got {r.returncode}, stderr: {r.stderr}"
