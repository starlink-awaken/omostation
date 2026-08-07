"""
Unit tests for projects/omo/src/omo/omo_belief.py (BET-Y1Q1-T3-01)
"""
import pytest
from pathlib import Path
from omo.omo_belief import MOSBeliefManager


def test_belief_manager_record_and_query(tmp_path: Path):
    mgr = MOSBeliefManager(root=tmp_path)
    
    # 记录第一个 belief
    b_id = mgr.record_belief(
        topic="git_isolation",
        belief_text="Agent 在共享主工作区修改代码会导致写冲突，必须走 Worktree",
        pitfall="直接在 main 运行 git commit --no-verify 覆盖改动",
        solution="使用 bash bin/gac/gac-worktree.sh claim <session> 创建隔离工作区",
        scope_path="bin/gac/*",
        source_run_id="run-test-001",
    )
    
    assert b_id == "belief-0001"
    assert mgr.state_file.exists()
    assert mgr.registry_file.exists()

    # 查询断言
    results = mgr.query_beliefs("git_isolation")
    assert len(results) == 1
    assert results[0]["id"] == "belief-0001"
    assert "Worktree" in results[0]["belief"]
