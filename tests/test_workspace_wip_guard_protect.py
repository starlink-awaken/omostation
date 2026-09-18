"""主工作区未推送提交钉扎（模式 B）回归测试.

对应 2026-09-18 实证: 提交已完成但未推送, 另一 agent 把共享工作区 switch 到
别的分支后, 该提交不再可从工作树到达 (e4787d290 / #3976 "dropped from #3969").

关键不变量: **即使原分支被删除, 钉扎的提交仍可达且可恢复**.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, Path(rel))
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


GUARD = Path(__file__).resolve().parents[1] / "bin/gac/workspace-wip-guard.py"


def _run(cwd: Path, *args: str) -> str:
    res = subprocess.run(["git", "-C", str(cwd), *args],
                         capture_output=True, text=True, check=True)
    return res.stdout.strip()


def _repo(tmp_path: Path) -> Path:
    """造一个带 origin/main 的仓库 + 一个含未推送提交的 feature 分支."""
    bare = tmp_path / "origin.git"
    bare.mkdir()
    _run(bare, "init", "--bare", "-q")
    work = tmp_path / "repo"
    work.mkdir()
    _run(work, "init", "-q", "-b", "main")
    _run(work, "config", "user.email", "t@t")
    _run(work, "config", "user.name", "t")
    (work / "a.txt").write_text("base\n")
    _run(work, "add", "-A")
    _run(work, "commit", "-qm", "base")
    _run(work, "remote", "add", "origin", str(bare))
    _run(work, "push", "-q", "-u", "origin", "main")

    _run(work, "checkout", "-q", "-b", "feat/unpushed")
    (work / "b.txt").write_text("wip\n")
    _run(work, "add", "-A")
    _run(work, "commit", "-qm", "wip: unpushed work")
    return work


def _guard(tmp_path: Path, work: Path):
    mod = _load("wip_guard", str(GUARD))
    mod._ROOT = work
    mod.SNAPSHOT_DIR = tmp_path / "snapshots"
    return mod


# ── 检测 ─────────────────────────────────────────────────


def test_detects_unpushed_commits(tmp_path):
    work = _repo(tmp_path)
    guard = _guard(tmp_path, work)
    shas = guard.unpushed_commits("feat/unpushed")
    assert len(shas) == 1, "feature 分支应有 1 个未推送提交"
    # main 本身无未推送提交
    assert guard.unpushed_commits("main") == []


def test_status_flags_branch_anomaly_and_unpushed(tmp_path):
    work = _repo(tmp_path)
    guard = _guard(tmp_path, work)
    info = guard.status()
    assert info["main_workspace"] is True
    assert info["branch"] == "feat/unpushed"
    assert info["branch_anomaly"] is True, "主工作区不在 main 即异常"
    assert info["unpushed_commits"] == 1
    assert info["unpushed_over_threshold"] is True


def test_check_exits_nonzero_on_unpushed(tmp_path):
    work = _repo(tmp_path)
    guard = _guard(tmp_path, work)
    assert guard.check() == 1, "有未推送提交时 check 必须非零"


# ── 钉扎 ─────────────────────────────────────────────────


def test_protect_pins_unpushed_commit(tmp_path):
    work = _repo(tmp_path)
    guard = _guard(tmp_path, work)
    result = guard.protect()
    assert result["ok"] is True
    assert len(result["pinned"]) == 1
    assert result["pinned"][0]["branch"] == "feat/unpushed"

    refs = guard.list_protected()
    assert len(refs) == 1
    assert refs[0]["ref"].startswith("refs/wip/")
    assert refs[0]["sha"] == result["pinned"][0]["sha"]
    # 台账落盘
    assert (guard.SNAPSHOT_DIR / "pinned-commits.jsonl").is_file()


def test_protect_pins_one_ref_per_branch_tip(tmp_path):
    """每分支只钉 1 个 ref（tip）—— 可达性传递, 钉 tip 即保住整条历史."""
    work = _repo(tmp_path)
    # 再加 2 个提交, 形成 3 个未推送提交
    for i in range(2):
        (work / f"c{i}.txt").write_text(f"{i}\n")
        _run(work, "add", "-A")
        _run(work, "commit", "-qm", f"more {i}")
    guard = _guard(tmp_path, work)
    assert len(guard.unpushed_commits("feat/unpushed")) == 3

    result = guard.protect()
    assert len(result["pinned"]) == 1, "3 个未推送提交只应产生 1 个 ref"
    assert result["pinned"][0]["unpushed"] == 3
    assert len(guard.list_protected()) == 1
    # tip = 分支头, 且能到达最早的未推送提交
    tip = result["pinned"][0]["sha"]
    assert tip == _run(work, "rev-parse", "feat/unpushed")
    log = _run(work, "rev-list", "--count", "origin/main..refs/wip/feat_unpushed-" + tip[:12])
    assert int(log) == 3, "钉住 tip 后整条未推送历史必须可达"


def test_protect_is_idempotent(tmp_path):
    work = _repo(tmp_path)
    guard = _guard(tmp_path, work)
    guard.protect()
    second = guard.protect()
    assert second["pinned"] == []
    assert second["already_pinned"] == 1, "已钉扎不重复创建"


def test_protect_dry_run_creates_nothing(tmp_path):
    work = _repo(tmp_path)
    guard = _guard(tmp_path, work)
    result = guard.protect(dry_run=True)
    assert len(result["pinned"]) == 1, "dry-run 应报告将要钉扎的内容"
    assert guard.list_protected() == [], "但不得真的创建 ref"


def test_protect_skips_in_worktree(tmp_path):
    """worktree 本就隔离 → 不钉扎."""
    work = _repo(tmp_path)
    guard = _guard(tmp_path, work)
    guard.is_main_workspace = lambda: False  # 模拟 worktree
    assert guard.protect()["reason"] == "not_main_workspace"


# ── 恢复（核心不变量）────────────────────────────────────


def test_pinned_commit_survives_branch_deletion(tmp_path):
    """核心: 删掉分支后, 钉扎的提交仍可达 —— 这正是本次事故的丢失模式."""
    work = _repo(tmp_path)
    guard = _guard(tmp_path, work)
    sha = guard.protect()["pinned"][0]["sha"]

    # 模拟并发 agent 删除分支 / 切换走
    _run(work, "checkout", "-q", "main")
    _run(work, "branch", "-D", "feat/unpushed")

    # 分支没了 → 从分支查不到
    assert guard.unpushed_commits("feat/unpushed") == []

    # 但钉扎 ref 仍在, 提交可达
    refs = guard.list_protected()
    assert any(r["sha"] == sha for r in refs), "分支删除后钉扎必须存活"
    reachable = _run(work, "cat-file", "-t", sha)
    assert reachable == "commit", "被钉扎的提交必须仍是可达对象"

    # 可恢复成新分支
    _run(work, "branch", "recover/wip", "refs/wip/feat_unpushed-" + sha[:12])
    files = _run(work, "ls-tree", "-r", "--name-only", "recover/wip")
    assert "b.txt" in files, "恢复出的分支应含原提交内容"


def test_unprotect_removes_ref(tmp_path):
    work = _repo(tmp_path)
    guard = _guard(tmp_path, work)
    ref = guard.protect()["pinned"][0]["ref"]
    assert guard.unprotect(ref)["ok"] is True
    assert guard.list_protected() == []


def test_unprotect_rejects_non_wip_ref(tmp_path):
    """安全: 拒绝删除 refs/wip/ 之外的任何 ref."""
    work = _repo(tmp_path)
    guard = _guard(tmp_path, work)
    for bad in ("refs/heads/main", "refs/heads/feat/unpushed", "HEAD"):
        result = guard.unprotect(bad)
        assert result["ok"] is False
        assert result["reason"] == "ref_outside_wip_namespace"
    # 业务 ref 完好
    assert _run(work, "rev-parse", "--verify", "refs/heads/main")


def test_pinned_ref_not_pushed_by_default(tmp_path):
    """refs/wip/ 不在 refs/heads|tags 下 → 默认 push 不会带走."""
    work = _repo(tmp_path)
    guard = _guard(tmp_path, work)
    guard.protect()
    _run(work, "push", "-q", "origin", "main")
    remote_refs = _run(work, "ls-remote", "origin")
    assert "refs/wip/" not in remote_refs, "钉扎 ref 不应被默认推送污染远端"
