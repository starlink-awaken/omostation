"""ADR-0376 G8: M1 tracked-truth 回归测试.

并发 agent 在 projects/ecos 工作树生成 untracked M1 / 切分支时,
working tree 与 root pointer 分离. gac-m1-sync --tracked 应基于
git ls-tree HEAD 的提交态, 忽略 working tree 噪声.

污染 fixture: 写入 properties.id=BRAND-NEW 的全新 id untracked 文件,
worktree 模式 (默认) 应报 orphan, tracked 模式应归零.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SYNC_SCRIPT = ROOT / "bin" / "gac" / "gac-m1-sync.py"
POLLUTION = (
    ROOT
    / "projects"
    / "ecos"
    / "src"
    / "ecos"
    / "ssot"
    / "mof"
    / "m1"
    / "governance"
    / "GAC-RULE-BRAND-NEW.yaml"
)

FIXTURE = """\
# ADR-0376 tracked-truth regression fixture — untracked pollution
id: GAC-RULE-BRAND-NEW
type: GacRule
name: BRAND-NEW pollution fixture
description: untracked M1 节点, 模拟并发 agent 未提交产物
status: active
domain: meta
layer: L2
created: '2026-07-31'
version: 1.0.0
properties:
  m3_parent: GovernanceElement.GacRule
  id: BRAND-NEW
"""


def _run_sync(tracked: bool) -> dict:
    cmd = ["python3", str(SYNC_SCRIPT), "--json"]
    if tracked:
        cmd.append("--tracked")
    proc = subprocess.run(
        cmd, cwd=str(ROOT), capture_output=True, text=True, check=False, timeout=120
    )
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


def _cleanup() -> None:
    if POLLUTION.exists():
        POLLUTION.unlink()


def test_worktree_mode_detects_untracked_pollution() -> None:
    """基线: 不带 --tracked, untracked 全新 id M1 文件应报 orphan."""
    try:
        POLLUTION.write_text(FIXTURE, encoding="utf-8")
        result = _run_sync(tracked=False)
        orphans = result["diff"]["orphan_in_m1"]
        assert "BRAND-NEW" in orphans, f"worktree 模式应检测到 BRAND-NEW, 实际 orphans={orphans}"
    finally:
        _cleanup()
        assert not POLLUTION.exists(), "fixture 清理失败"


def test_tracked_mode_ignores_untracked_pollution() -> None:
    """核心价值: --tracked 基于 git HEAD 提交态, untracked 污染不应报 orphan."""
    try:
        POLLUTION.write_text(FIXTURE, encoding="utf-8")
        result = _run_sync(tracked=True)
        orphans = result["diff"]["orphan_in_m1"]
        assert "BRAND-NEW" not in orphans, (
            f"tracked 模式不应看到 untracked BRAND-NEW, 实际 orphans={orphans}"
        )
        assert orphans == [], f"tracked 模式应零 orphan, 实际={orphans}"
    finally:
        _cleanup()
        assert not POLLUTION.exists(), "fixture 清理失败"


def test_tracked_instances_match_root_pointer() -> None:
    """tracked 模式实例数应等于 registry 规则数 (ADR-0374 后 M1=117 对齐)."""
    result = _run_sync(tracked=True)
    assert result["registry_rules"] == result["m1_instances"], (
        f"registry={result['registry_rules']} != m1_instances={result['m1_instances']}, "
        "root pointer 应已对齐 (ADR-0374 G3)"
    )
    assert result["diff"]["missing_in_m1"] == []
    assert result["diff"]["orphan_in_m1"] == []
