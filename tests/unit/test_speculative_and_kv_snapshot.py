"""Unit tests for SpeculativeRouter and KVCacheSnapshotStore (ADR-0197)."""

from __future__ import annotations

import tempfile
from pathlib import Path

from typer.testing import CliRunner

from omlxc.cli import app
from omlxc.dataplane.kv_snapshot import KVCacheSnapshotStore
from omlxc.dataplane.speculative import SpeculativeRouter

runner = CliRunner()


def test_kv_snapshot_store_lifecycle() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        store = KVCacheSnapshotStore(root_dir=Path(tmpdir))
        snapshots = store.list_snapshots()
        assert len(snapshots) >= 2

        rec = store.create_snapshot("test-snap", model_id="qwen2.5-coder:14b", prefix_text="Prompt prefix test")
        assert rec.snapshot_id == "test-snap"
        assert rec.is_warm is True

        ok = store.warm_snapshot("test-snap")
        assert ok is True
        assert store.warm_snapshot("nonexistent") is False


def test_speculative_router_decisions() -> None:
    router = SpeculativeRouter()

    # 1. Quick local syntax task
    decision_local = router.evaluate("检查这段 Python 语法是否合规")
    assert decision_local.target_tier == "local"
    assert decision_local.estimated_speedup_ratio >= 1.5

    # 2. Deep architectural / red-team reasoning task
    decision_cloud = router.evaluate("请进行卫健委区域医疗数据跨平台互联互通架构设计与长远愿景博弈推演")
    assert decision_cloud.target_tier == "hybrid-speculative"
    assert decision_cloud.draft_model is not None


def test_cli_fabric_snapshot_and_speculative() -> None:
    # 1. Snapshot list CLI
    res = runner.invoke(app, ["fabric", "snapshot", "list", "--json"])
    assert res.exit_code == 0
    assert "snapshots" in res.output

    # 2. Speculative eval CLI
    res = runner.invoke(app, ["fabric", "speculative-eval", "系统架构长期愿景推演", "--json"])
    assert res.exit_code == 0
    assert "target_tier" in res.output
