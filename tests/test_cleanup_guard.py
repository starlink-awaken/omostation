"""T10-140: 清理器引用保护测试.

覆盖: guard 三维保护 (未推 commit / open PR / 活跃认领) + 放行场景
+ 三清理器接入冒烟 (dry-run 不炸).
隔离原则: git 场景用 tmp repo (subprocess init); claim 场景 monkeypatch 模块缓存.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

_spec = importlib.util.spec_from_file_location("cleanup_guard", ROOT / "lib" / "cleanup-guard.py")
assert _spec is not None and _spec.loader is not None
cg = importlib.util.module_from_spec(_spec)
sys.modules["cleanup_guard"] = cg
_spec.loader.exec_module(cg)


def _init_repo(tmp_path: Path) -> Path:
    """临时 repo: main + 一个已推 origin 同步分支 + 一个未推分支."""
    repo = tmp_path / "repo"
    repo.mkdir()
    def git(*args: str) -> None:
        subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)
    git("init", "-b", "main")
    git("config", "user.email", "t@t")
    git("config", "user.name", "t")
    (repo / "f.txt").write_text("1")
    git("add", ".")
    git("commit", "-m", "init")
    # origin 同步分支: clean (远端有同名分支且无新 commit)
    git("branch", "work/clean-branch")
    # 哑 origin: 用本地 bare 仓模拟远端同名分支
    bare = tmp_path / "origin.git"
    subprocess.run(["git", "clone", "--bare", str(repo), str(bare)], check=True, capture_output=True)
    git("remote", "add", "origin", str(bare))
    git("push", "origin", "main")
    git("push", "origin", "work/clean-branch")
    # 未推分支: 基于 main 新 commit, 不推
    git("checkout", "-b", "work/unpushed-branch")
    (repo / "f.txt").write_text("2")
    git("add", ".")
    git("commit", "-m", "local-only")
    git("checkout", "main")
    return repo


def test_unpushed_protected(tmp_path: Path) -> None:
    """未推 commit 分支 → unpushed 保护."""
    repo = _init_repo(tmp_path)
    assert cg.protect_reason("work/unpushed-branch", cwd=repo) == "unpushed"


def test_clean_branch_deletable(tmp_path: Path, monkeypatch) -> None:
    """远端同步分支 (无 PR/认领命中) → None 放行."""
    repo = _init_repo(tmp_path)
    monkeypatch.setattr(cg, "pr_open", lambda b: False)
    monkeypatch.setattr(cg, "active_claim_bets", lambda: [])
    assert cg.protect_reason("work/clean-branch", cwd=repo) is None


def test_pr_open_protected(tmp_path: Path, monkeypatch) -> None:
    """open PR 分支 → open-pr 保护."""
    repo = _init_repo(tmp_path)
    monkeypatch.setattr(cg, "pr_open", lambda b: True)
    monkeypatch.setattr(cg, "active_claim_bets", lambda: [])
    assert cg.protect_reason("work/unpushed-branch", cwd=repo) == "unpushed"  # 未推优先
    # 未推维度不命中时 PR 生效
    monkeypatch.setattr(cg, "has_unpushed_commits", lambda b, cwd=None: False)
    assert cg.protect_reason("work/clean-branch", cwd=repo) == "open-pr"


def test_bet_claim_protected(tmp_path: Path, monkeypatch) -> None:
    """分支名含活跃认领 bet_id → bet-claimed 保护 (T10-139 广播联动).

    双形态: 全 id (work/BET-Y1Q4-T10-139-xx) 与尾段短 id (work/t10-139-xx,
    真实命名惯例) 都命中; 相邻编号 (t10-13) 不误伤.
    """
    repo = _init_repo(tmp_path)
    monkeypatch.setattr(cg, "has_unpushed_commits", lambda b, cwd=None: False)
    monkeypatch.setattr(cg, "pr_open", lambda b: False)
    monkeypatch.setattr(cg, "active_claim_bets", lambda: ["BET-Y1Q4-T10-139"])
    # 尾段短 id 形态 (真实惯例)
    assert cg.protect_reason("work/t10-139-claim-broadcast-v2", cwd=repo) == "bet-claimed (BET-Y1Q4-T10-139)"
    # 全 id 形态
    assert cg.protect_reason("work/BET-Y1Q4-T10-139-full-form", cwd=repo) == "bet-claimed (BET-Y1Q4-T10-139)"
    # 相邻编号不误伤 (T10-139 ≠ T10-13)
    assert cg.protect_reason("work/t10-13-other-bet", cwd=repo) is None
    # 不含认领 id 的分支不受影响
    assert cg.protect_reason("work/clean-branch", cwd=repo) is None


def test_active_claim_bets_reads_dir(tmp_path: Path, monkeypatch) -> None:
    """active_claim_bets 从 bet-claims 目录读 bet_id."""
    claims = tmp_path / "bet-claims"
    claims.mkdir()
    (claims / "BET-X.json").write_text(json.dumps({"bet_id": "BET-X", "actor": "a"}))
    monkeypatch.setattr(cg, "CLAIMS_DIR", claims)
    monkeypatch.setattr(cg, "_active_claims_cache", None)
    assert cg.active_claim_bets() == ["BET-X"]


def test_cli_check(tmp_path: Path, monkeypatch) -> None:
    """CLI 形态: return 0=可删 / 1=保护 (shell 清理器依赖 exit code 契约)."""
    repo = _init_repo(tmp_path)
    monkeypatch.setattr(cg, "pr_open", lambda b: False)
    monkeypatch.setattr(cg, "active_claim_bets", lambda: [])
    # 未推 → 保护 (rc=1); 真实进程经 sys.exit(main()) 传导为 exit code
    assert cg.main(["check", "work/unpushed-branch", "--cwd", str(repo)]) == 1
    # 干净 → 可删 (rc=0)
    assert cg.main(["check", "work/clean-branch", "--cwd", str(repo)]) == 0


def test_three_cleaners_smoke() -> None:
    """三清理器接入冒烟: dry-run 全链跑通不炸 (语法+import+guard 路径)."""
    for tool in (
        "bin/gac/prune-zombie-worktrees.py",
        "bin/gac/branch-ttl-gate.py",
    ):
        r = subprocess.run(
            [sys.executable, str(ROOT / tool)],
            capture_output=True, text=True, timeout=300, cwd=ROOT,
        )
        assert r.returncode == 0, f"{tool} rc={r.returncode}: {r.stderr[-300:]}"
    r = subprocess.run(
        ["bash", str(ROOT / "bin/gac/gac-branch-prune.sh"), "--dry-run"],
        capture_output=True, text=True, timeout=300, cwd=ROOT,
    )
    assert r.returncode == 0, f"gac-branch-prune.sh rc={r.returncode}: {r.stderr[-300:]}"
