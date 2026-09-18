"""主工作区提交守卫回归测试.

对应 2026-09-18 事故: AGENTS.md 早已声明"主工作区只读, 改动走 worktree",
但没有执行层。本守卫补上 —— 主工作区停在非 main 分支时提交即拦截。
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

GUARD = Path(__file__).resolve().parents[1] / "bin/gac/check-main-workspace-commit.py"


def _load():
    spec = importlib.util.spec_from_file_location("ws_commit_guard", GUARD)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["ws_commit_guard"] = mod
    spec.loader.exec_module(mod)
    return mod


def _run(cwd: Path, *args: str, env=None) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(cwd), *args],
                          capture_output=True, text=True, env=env, check=False)


def _main_repo(tmp_path: Path, branch: str = "main") -> Path:
    """造一个"主工作区"形态的仓库 (git-dir == git-common-dir)."""
    work = tmp_path / "mainws"
    work.mkdir()
    _run(work, "init", "-q", "-b", branch)
    _run(work, "config", "user.email", "t@t")
    _run(work, "config", "user.name", "t")
    (work / "a.txt").write_text("x\n")
    _run(work, "add", "-A")
    _run(work, "commit", "-qm", "init")
    return work


# ── 判定表 ───────────────────────────────────────────────


def test_worktree_passes(tmp_path):
    """worktree 天然隔离 → 放行 (agent 的常规路径)."""
    repo = _main_repo(tmp_path)
    wt = tmp_path / "wt"
    _run(repo, "worktree", "add", "-q", "-b", "agent/x", str(wt))
    guard = _load()
    r = guard.evaluate(root=wt)
    assert r["verdict"] == "pass"
    assert r["reason"] == "not_main_workspace"
    assert r["main_workspace"] is False


def test_main_workspace_on_main_passes(tmp_path):
    """主工作区停在 main → 放行 (无"分支被切走"孤立风险)."""
    repo = _main_repo(tmp_path)
    guard = _load()
    r = guard.evaluate(root=repo)
    assert r["main_workspace"] is True
    assert r["branch"] == "main"
    assert r["verdict"] == "pass"
    assert r["reason"] == "on_main_or_detached"


def test_main_workspace_non_main_blocks(tmp_path):
    """核心: 主工作区停在特性分支 → 拦截 (2026-09-18 事故形态)."""
    repo = _main_repo(tmp_path, branch="agent/governance-agent/foo")
    guard = _load()
    r = guard.evaluate(root=repo)
    assert r["main_workspace"] is True
    assert r["branch"] == "agent/governance-agent/foo"
    assert r["verdict"] == "block"
    assert r["reason"] == "main_workspace_non_main_branch"


def test_env_override_passes_and_records_ledger(tmp_path):
    """逃生舱: GAC_ALLOW_MAIN_WORKSPACE_COMMIT=1 → 放行 + 记台账."""
    repo = _main_repo(tmp_path, branch="agent/x")
    guard = _load()
    guard.OVERRIDE_LEDGER = tmp_path / "overrides.jsonl"
    r = guard.evaluate(root=repo, allow_env="1")
    assert r["verdict"] == "pass"
    assert r["reason"] == "env_override"
    assert guard.OVERRIDE_LEDGER.is_file()
    entry = json.loads(guard.OVERRIDE_LEDGER.read_text().splitlines()[0])
    assert entry["branch"] == "agent/x"


def test_override_only_when_value_is_1(tmp_path):
    """只有显式 =1 才放行, 其他值不构成逃生舱."""
    repo = _main_repo(tmp_path, branch="agent/x")
    guard = _load()
    for value in ("0", "yes", "true", ""):
        assert guard.evaluate(root=repo, allow_env=value)["verdict"] == "block"


def test_detached_head_passes(tmp_path):
    repo = _main_repo(tmp_path)
    head = _run(repo, "rev-parse", "HEAD").stdout.strip()
    _run(repo, "checkout", "-q", head)
    guard = _load()
    assert guard.evaluate(root=repo)["verdict"] == "pass"


def test_reports_unpushed_count(tmp_path):
    """拦截时要能量化风险: 报告该分支已有多少未推送提交."""
    repo = _main_repo(tmp_path)  # 先建在 main 上
    bare = tmp_path / "origin.git"
    bare.mkdir()
    _run(bare, "init", "--bare", "-q")
    _run(repo, "remote", "add", "origin", str(bare))
    _run(repo, "push", "-q", "origin", "main")   # 建立 origin/main 基准
    _run(repo, "switch", "-q", "-c", "agent/x")  # 再切到特性分支
    for i in range(3):
        (repo / f"f{i}.txt").write_text(f"{i}\n")
        _run(repo, "add", "-A")
        _run(repo, "commit", "-qm", f"c{i}")
    guard = _load()
    r = guard.evaluate(root=repo)
    assert r["verdict"] == "block"
    assert r["unpushed"] == 3


# ── CLI 退出码 ───────────────────────────────────────────


def test_cli_exit_codes(tmp_path):
    repo = _main_repo(tmp_path, branch="agent/x")
    guard = _load()
    assert guard.main(["--root", str(repo), "--json"]) == 1, "主工作区非 main → exit 1"
    assert guard.main(["--root", str(repo), "--branch", "main", "--json"]) == 0


def test_cli_block_message_is_actionable(tmp_path, capsys):
    """拦截信息必须可执行: 给出 worktree 命令 + 逃生舱 + 恢复入口."""
    repo = _main_repo(tmp_path, branch="agent/x")
    guard = _load()
    guard.main(["--root", str(repo)])
    err = capsys.readouterr().err
    assert "gac-worktree.sh claim" in err
    assert "GAC_ALLOW_MAIN_WORKSPACE_COMMIT=1" in err
    assert "list-protected" in err


# ── 端到端: 真实 pre-commit 拦截 ─────────────────────────


def test_blocks_real_commit_in_main_workspace(tmp_path):
    """端到端: 在"主工作区"形态的仓库 + 特性分支上安装守卫, 提交必须失败."""
    repo = _main_repo(tmp_path, branch="agent/feature")
    hooks = repo / ".git" / "hooks"
    hooks.mkdir(parents=True, exist_ok=True)
    hook = hooks / "pre-commit"
    hook.write_text(
        "#!/bin/bash\n"
        f'exec python3 "{GUARD}" --root "{repo}"\n'
    )
    hook.chmod(0o755)

    (repo / "new.txt").write_text("y\n")
    _run(repo, "add", "-A")
    res = _run(repo, "commit", "-m", "should be blocked")
    assert res.returncode != 0, "守卫应拦截提交"
    assert "主工作区提交被拦截" in (res.stderr + res.stdout)

    # 逃生舱生效
    env = {**os.environ, "GAC_ALLOW_MAIN_WORKSPACE_COMMIT": "1"}
    res2 = _run(repo, "commit", "-m", "with override", env=env)
    assert res2.returncode == 0, f"逃生舱应放行: {res2.stderr}"


def test_does_not_block_commit_in_worktree(tmp_path):
    """端到端: worktree 里提交不受影响 (agent 常规路径不得被打断)."""
    repo = _main_repo(tmp_path)
    wt = tmp_path / "wt"
    _run(repo, "worktree", "add", "-q", "-b", "agent/ok", str(wt))
    hook = wt / ".git" if (wt / ".git").is_file() else None
    # worktree 的 hooks 来自 common dir; 直接装到 common hooks 上
    hooks = repo / ".git" / "hooks"
    hooks.mkdir(parents=True, exist_ok=True)
    h = hooks / "pre-commit"
    h.write_text("#!/bin/bash\n"
                 f'exec python3 "{GUARD}" --root "$(git rev-parse --show-toplevel)"\n')
    h.chmod(0o755)

    (wt / "b.txt").write_text("z\n")
    _run(wt, "add", "-A")
    res = _run(wt, "commit", "-m", "worktree commit")
    assert res.returncode == 0, f"worktree 提交不得被拦截: {res.stderr}"
