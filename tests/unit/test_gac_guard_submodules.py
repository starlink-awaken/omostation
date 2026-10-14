"""BET-Y2Q4-T10-252 — guard-submodules --fix 非破坏性对齐回归。

背景: 并发 agent 的 submodule update 周期把 worktree 内手动布置的检出（.git 指向
外部 gitdir）当无效目录先删后建, 网络受限时留下空目录, 打断交付 (ptr-bump 实证)。
本测试从生产脚本抽取 guard_submodules() 本体执行, 不复制逻辑。
"""

from __future__ import annotations

import subprocess
import textwrap
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "bin" / "gac" / "gac-worktree.sh"

GUARD_FN = textwrap.dedent(
    """
    set -euo pipefail
    WS_ROOT=__SUPER__
    guard_submodules() {
    __GUARD_BODY__
    }
    guard_submodules __FIX__
    """
)


def _guard_body() -> str:
    """从生产脚本抽取 guard_submodules() 函数体（首个 ^} 结束）。"""
    text = SCRIPT.read_text(encoding="utf-8")
    start = text.index("guard_submodules() {")
    start = text.index("{", start) + 1
    end = text.index("\n}\n", start)
    return text[start:end]


def run_guard(super: Path, fix: bool) -> subprocess.CompletedProcess[str]:
    fix_flag = "--fix" if fix else ""
    script = GUARD_FN.replace("__SUPER__", str(super)).replace(
        "__GUARD_BODY__", _guard_body()
    ).replace("__FIX__", fix_flag)
    return subprocess.run(
        ["bash", "-c", script], capture_output=True, text=True, cwd=str(super)
    )


def git(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=str(cwd), capture_output=True, text=True, check=True
    )


def make_sub_repo(path: Path, commits: list[str]) -> dict[str, str]:
    """建一个对象库仓库, 每个 commit 一个文件; 返回 {tag: sha}。"""
    path.mkdir(parents=True)
    git(["init", "-q", "-b", "main"], path)
    shas: dict[str, str] = {}
    for tag in commits:
        (path / f"{tag}.txt").write_text(tag, encoding="utf-8")
        git(["add", "."], path)
        git(["-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", tag], path)
        shas[tag] = git(["rev-parse", "HEAD"], path).stdout.strip()
    return shas


def make_super(tmp_path: Path, sub_url: str) -> tuple[Path, Path]:
    """建超仓: .gitmodules 登记 projects/foo, index 里放 gitlink, origin 指向 sub_url。"""
    super_repo = tmp_path / "super"
    super_repo.mkdir()
    git(["init", "-q", "-b", "main"], super_repo)
    git(["remote", "add", "origin", sub_url], super_repo)
    (super_repo / ".gitmodules").write_text(
        f"[submodule \"projects/foo\"]\n\tpath = projects/foo\n\turl = {sub_url}\n",
        encoding="utf-8",
    )
    git(["add", ".gitmodules"], super_repo)
    return super_repo, sub_url


def plant_checkout(super: Path, gitdir: Path, head_sha: str) -> Path:
    """在超仓里手动布置检出: .git 文件指向外部 gitdir, HEAD = head_sha。"""
    wt = super / "projects" / "foo"
    wt.mkdir(parents=True, exist_ok=True)
    (wt / ".git").write_text(f"gitdir: {gitdir}/.git\n", encoding="utf-8")
    subprocess.run(
        ["git", f"--git-dir={gitdir}/.git", f"--work-tree={wt}", "checkout", "-q", head_sha],
        capture_output=True, text=True, check=True,
    )
    return wt


def set_gitlink(super: Path, sha: str, path: str = "projects/foo") -> None:
    git(["update-index", "--add", "--cacheinfo", f"160000,{sha},{path}"], super)


def test_isc1_existing_checkout_not_deleted(tmp_path: Path):
    """ISC-1: 已存在且可解析的检出在 --fix 后完好（.git 条目与工作树文件未变）。"""
    sub = tmp_path / "sub"
    shas = make_sub_repo(sub, ["v1"])
    super_repo, sub_url = make_super(tmp_path, sub_url=str(sub))
    # pin 指向一个本地对象库不存在的 sha → 不会对齐, 但必须不删除
    set_gitlink(super_repo, "1" * 40)
    wt = plant_checkout(super_repo, sub, shas["v1"])
    (wt / "extra.txt").write_text("keepme", encoding="utf-8")

    r = run_guard(super_repo, fix=True)

    assert r.returncode == 0, r.stderr
    assert (wt / ".git").is_file(), ".git 条目被删除"
    assert (wt / "extra.txt").exists(), "工作树文件被动过"
    assert git(["rev-parse", "HEAD"], wt).stdout.strip() == shas["v1"]


def test_isc2_existing_checkout_aligned_nondestructively(tmp_path: Path):
    """ISC-2: 已存在检出且本地含 pin 对象 → --fix 后 HEAD == pin 且 .git 条目仍在。"""
    sub = tmp_path / "sub"
    shas = make_sub_repo(sub, ["v1", "v2"])
    super_repo, sub_url = make_super(tmp_path, sub_url=str(sub))
    set_gitlink(super_repo, shas["v2"])
    wt = plant_checkout(super_repo, sub, shas["v1"])

    r = run_guard(super_repo, fix=True)

    assert r.returncode == 0, r.stderr
    assert (wt / ".git").is_file()
    head = git(["rev-parse", "HEAD"], wt).stdout.strip()
    assert head == shas["v2"]


def test_isc3_missing_checkout_still_initialized(tmp_path: Path):
    """ISC-3: 无 .git 条目的路径仍走原 update --init 重建（本地 file:// URL 可离线）。"""
    sub = tmp_path / "sub"
    shas = make_sub_repo(sub, ["v1"])
    super_repo, sub_url = make_super(tmp_path, sub_url=str(sub))
    set_gitlink(super_repo, shas["v1"])
    # 完全不建 projects/foo 检出
    wt = super_repo / "projects" / "foo"
    wt.mkdir(parents=True)

    r = run_guard(super_repo, fix=True)

    assert r.returncode == 0, r.stderr
    assert (wt / ".git").exists(), "空缺路径未被 init"
    head = git(["rev-parse", "HEAD"], wt).stdout.strip()
    assert head == shas["v1"]


def test_isc4_missing_pin_objects_skips_with_advisory(tmp_path: Path):
    """ISC-4: 已存在检出但本地无 pin 对象 → 不动检出、advisory 点名、exit 0。"""
    sub = tmp_path / "sub"
    shas = make_sub_repo(sub, ["v1"])
    super_repo, sub_url = make_super(tmp_path, sub_url=str(sub))
    set_gitlink(super_repo, "1" * 40)
    wt = plant_checkout(super_repo, sub, shas["v1"])

    r = run_guard(super_repo, fix=True)

    assert r.returncode == 0
    assert "projects/foo" in r.stdout, "缺对象路径未被 advisory 点名"
    assert "T252" in r.stdout
    assert (wt / ".git").is_file()


def test_isc6_remote_pollution_detection_unchanged(tmp_path: Path):
    """ISC-6: origin URL 落入子仓 URL 集合 → 仍报 remote 污染且不改写。"""
    sub = tmp_path / "sub"
    make_sub_repo(sub, ["v1"])
    super_repo, sub_url = make_super(tmp_path, sub_url=str(sub))
    # super 的 origin URL == 子仓 URL → 污染
    assert super_repo.joinpath(".git").exists()

    r = run_guard(super_repo, fix=False)

    assert "remote 污染" in r.stdout
    # 不改写 remote URL
    url = git(["-C", str(super_repo), "config", "--get", "remote.origin.url"], super_repo)
    assert url.stdout.strip() == str(sub)


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
