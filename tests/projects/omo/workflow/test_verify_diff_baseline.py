"""BET-Y1Q3-T9-01 ①: verify diff 基线漂移检测测试.

模式 1 教训 (PR #1518): status 变更在 worktree A、PR 从 worktree B 提交,
变更丢失。本测试验证 claim 基线 → verify 对比机制能拦住漂移。

不真实化 run 文件: 直接测 diff_baseline_report 的分支逻辑 (构造 payload)。
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "projects/omo/src"))

from omo.workflow.lifecycle import diff_baseline_report  # noqa: E402


def _run_file(tmp_path: Path, claims: list[dict]) -> Path:
    rf = tmp_path / "r1.yaml"
    rf.write_text("dummy")  # read_run 被 mock, 文件存在即可
    return rf


def _with_run(claims: list[dict], tmp_path: Path):
    """mock run_file_for + read_run — 单元测试不落真实 run 目录."""
    from unittest.mock import patch
    import omo.workflow.lifecycle as lif
    _run_file(tmp_path, claims)
    payload = {"run_id": "r1", "status": "active", "workflow_id": "w", "claims": claims}
    return patch.object(lif, "run_file_for", return_value=tmp_path / "r1.yaml"), \
           patch.object(lif, "read_run", return_value=(tmp_path / "r1.yaml", payload))


def test_no_run_id_skips():
    rep = diff_baseline_report({}, None, [])
    assert rep["ok"] is True and rep["checked"] is False


def test_legacy_claim_without_baseline_skips(tmp_path):
    reg = {}
    p1, p2 = _with_run([{"paths": ["docs/a.md"]}], tmp_path)
    with p1, p2:
        rep = diff_baseline_report(reg, "r1", [])
    assert rep["ok"] is True and "baseline_commit" in rep["reason"] or rep["reason"] == "no baseline_commit (legacy claim)"


def test_drift_detected_and_fails(tmp_path):
    """claim 后有变更绕过 claim → drifted 非空 → ok=False (核心防线)."""
    reg = {}
    p1, p2 = _with_run([{
        "paths": ["docs/plans/ledger.yaml"],
        "baseline_commit": "abc123",
    }], tmp_path)
    fake_diff = "docs/plans/ledger.yaml\ndocs/plans/OTHER.yaml\n"  # OTHER 未被 claim
    with p1, p2, patch("subprocess.run") as mock:
        mock.return_value.returncode = 0
        mock.return_value.stdout = fake_diff
        rep = diff_baseline_report(reg, "r1", ["docs/plans/ledger.yaml"])
    assert rep["checked"] is True
    assert rep["ok"] is False
    assert rep["drifted_files"] == ["docs/plans/OTHER.yaml"]
    assert any("drifted beyond claim" in w for w in rep["warnings"])


def test_no_drift_when_all_covered(tmp_path):
    """claim 后变更全部在 claim 覆盖内 → ok=True."""
    reg = {}
    p1, p2 = _with_run([{
        "paths": ["docs/plans/"],
        "baseline_commit": "abc123",
    }], tmp_path)
    fake_diff = "docs/plans/ledger.yaml\n"
    with p1, p2, patch("subprocess.run") as mock:
        mock.return_value.returncode = 0
        mock.return_value.stdout = fake_diff
        rep = diff_baseline_report(reg, "r1", [])
    assert rep["ok"] is True and rep["drifted_files"] == []


def test_git_failure_never_blocks(tmp_path):
    """git 失败不阻塞 (向后兼容)."""
    reg = {}
    p1, p2 = _with_run([{"paths": [], "baseline_commit": "deadbeef"}], tmp_path)
    with p1, p2, patch("subprocess.run") as mock:
        mock.return_value.returncode = 128
        mock.return_value.stderr = "bad object"
        rep = diff_baseline_report(reg, "r1", [])
    assert rep["ok"] is True and rep["checked"] is False
