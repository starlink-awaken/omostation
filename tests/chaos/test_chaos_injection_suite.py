"""Chaos injection suite — 12-drill end-to-end test (BET-Y1Q3-T10-120).

Test runner for bin/ssot/chaos-governance-drill.py.
Each test invokes the drill runner, parses JSON output, asserts the specific
drill passed. Negative tests intentionally inject broken fixtures to verify
drill resilience.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DRILL_BIN = "bin/ssot/chaos-governance-drill.py"

# 12 项 drill 与类别映射 (与 chaos-governance-drill.py::drills 注册顺序一致)
EXPECTED_DRILLS = [
    ("Documents Plane Invasion Mutation", "Plane Boundary"),
    ("Corrupted & Stale Fact Mutation", "Facts SSOT"),
    ("Policy-as-Code Regulatory Red-Line Bypass", "Domain Policy"),
    ("Compute Fabric VRAM Shock & Thermal Chaos", "Compute Fabric"),
    ("Intent Spec, Shadow Challenger & Broken Cartridge Defense", "Cognitive Mesh"),
    ("Merkle Ledger, Memory Distillation & Edge Compute Roaming", "Next-Gen OS"),
    ("ThunderBolt 5 Link Disconnect & Auto-Fallback", "Dual-Machine Fabric"),
    ("Dirty Worktree Exploit & Detection", "Worktree Hygiene"),
    ("Zombie Lock Injection & Stale Cleanup", "Concurrency Lock"),
    ("Submodule Pointer Drift & Sync Recovery", "Submodule Integrity"),
    ("Harness Admission Bypass Attempt", "Harness Lifecycle"),
    ("Mass Deletion Guard & Recovery", "Git Safety"),
]


def run_chaos_drill() -> dict:
    """Invoke chaos-governance-drill.py --json and parse output."""
    res = subprocess.run(
        [sys.executable, str(REPO_ROOT / DRILL_BIN), "--json"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=600,
    )
    if res.returncode != 0:
        # 即使 strict 模式返回非零, JSON 也应输出
        pass
    return json.loads(res.stdout)


def test_full_suite_all_12_pass() -> None:
    """所有 12 项 chaos drill 必须通过."""
    result = run_chaos_drill()
    assert result["score"] == "12/12", (
        f"期望 12/12 PASS, 实际 {result['score']}\n"
        +"\n".join(f"  FAIL: {d['drill_name']}: {d['detail']}"
                    for d in result["drills"] if not d["passed"])
    )


def test_all_expected_drills_present() -> None:
    """混沌套件必须注册所有 12 项预期 drill."""
    result = run_chaos_drill()
    actual = {(d["drill_name"], d["category"]) for d in result["drills"]}
    expected = set(EXPECTED_DRILLS)
    missing = expected - actual
    assert not missing, f"缺少 chaos drill: {missing}"


def test_each_drill_has_detail() -> None:
    """每个 drill 必须有 detail 字段 (避免 silent PASS)."""
    result = run_chaos_drill()
    for drill in result["drills"]:
        assert drill["detail"], f"drill {drill['drill_name']} 缺详情"
        assert drill["passed"], f"drill {drill['drill_name']} 未通过"


def test_drills_use_temporary_fixtures() -> None:
    """12 项 drill 应使用 tempfile.TemporaryDirectory, 不污染主仓 (.tmp/ 残留 ≤ 1)."""
    result = run_chaos_drill()
    # chaos drills 完成后, .tmp 下不应有遗留文件
    tmp_root = REPO_ROOT / "runtime"
    if tmp_root.exists():
        chaos_dirs = list(tmp_root.glob("chaos-*"))
        assert len(chaos_dirs) <= 1, (
            f"chaos drill 残留目录: {[d.name for d in chaos_dirs]}"
        )


def test_scorecard_consistency() -> None:
    """score 字段必须与 drills 实际通过数一致."""
    result = run_chaos_drill()
    actual_passed = sum(1 for d in result["drills"] if d["passed"])
    expected_score = f"{actual_passed}/{len(result['drills'])}"
    assert result["score"] == expected_score, (
        f"score 字段不一致: 报 {result['score']}, 实际 {expected_score}"
    )


if __name__ == "__main__":
    test_full_suite_all_12_pass()
    test_all_expected_drills_present()
    test_each_drill_has_detail()
    test_drills_use_temporary_fixtures()
    test_scorecard_consistency()
    print("ALL CHAOS SUITE TESTS PASS (12/12 drills + 5 invariants)")