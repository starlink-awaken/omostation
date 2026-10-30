"""PUSH_RANGE 导出点 (ADR-4443 v9 机制) 的合同测试。

缺陷背景 (2026-10-30 实锤): `bin/change-lane-check.py` 的 `PUSH_RANGE` 分支自设计起
**在 `.githooks/` 里没有任何导出点** ⇒ 该机制从未生效 (实测
`grep -rn PUSH_RANGE .githooks/` = 0 命中; 仓内
`docs/reports/2026-10-27-bet-273-...md` §6 已记同一事实)。

本测试锁住:
1. **base 取 merge-base(remote-tracking, local_sha)** —— 精确表示「本地分支相对远端
   多出的 commit」。用 origin/<branch> 直接当 base 是错的: 分支可能落后于远端
   (远端有别人推的 commit), 那样算出的范围会含不属于本次推送的变更。
2. **新分支首次 push 的兜底**: git 在 push **成功之后** 才创建 remote-tracking ref,
   而 pre-push 跑在 push 之前 ⇒ 新分支首次 push 时 origin/<branch> 还不存在 ⇒
   退到 origin/HEAD (默认分支) 作 base 候选。
3. **解析不出范围时显式 SKIP**, 不输出 PUSH_RANGE —— 下游必须看到「没有范围」
   而不是「范围是空」(后者会被当成「无违规」而假绿)。
4. **判据粒度是 per-commit**: PUSH_RANGE 分支已改为复用 check_range(), 不再走
   aggregate 的 `git diff --name-only <range>` (那个粒度与规则「每 commit 单 lane」
   不符, 且实测会误判「commit A=docs + commit B=子模块指针」那类合法形状)。
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
EXPORT_SCRIPT = ROOT / "bin" / "gac" / "export-push-range.py"
LANE_SCRIPT = ROOT / "bin" / "change-lane-check.py"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, str(path))
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=repo, capture_output=True, text=True, check=True
    )
    return result.stdout.strip()


def _make_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@t.t")
    _git(repo, "config", "user.name", "t")
    return repo


def _commit(repo: Path, name: str, content: str = "x\n") -> str:
    (repo / name).parent.mkdir(parents=True, exist_ok=True)
    (repo / name).write_text(content, encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", f"add {name}")
    return _git(repo, "rev-parse", "HEAD")


def _fake_remote(repo: Path, branch: str, sha: str) -> None:
    """造一个 remote-tracking ref 指向给定 sha (不需要真实远端)。"""
    _git(repo, "update-ref", f"refs/remotes/origin/{branch}", sha)


def _write_refs(tmp_path: Path, remote_ref: str, local_sha: str, remote_sha: str) -> str:
    path = tmp_path / "push_refs.txt"
    path.write_text(
        f"{remote_ref} {local_sha} {remote_ref} {remote_sha}\n", encoding="utf-8"
    )
    return str(path)


def test_range_uses_merge_base_of_remote_tracking_and_local(tmp_path):
    """base = merge-base(origin/<branch>, local_sha) —— 精确表示本地多出的 commit。"""
    repo = _make_repo(tmp_path)
    base_sha = _commit(repo, "base.txt")
    _fake_remote(repo, "feature", base_sha)

    local_sha = _commit(repo, "feature.txt")
    refs = _write_refs(tmp_path, "refs/heads/feature", local_sha, base_sha)

    module = _load(EXPORT_SCRIPT, "export_push_range")
    module.WORKSPACE = repo
    git_range, reason = module.resolve_range(refs)

    assert git_range == f"{base_sha}..{local_sha}", reason


def test_range_excludes_commits_that_come_only_from_remote(tmp_path):
    """分支落后于远端时, 范围不得含远端多出的 commit。

    用 origin/<branch> 直接当 base 会把远端多的 commit 算进来 —— 那些不属于本次推送。
    """
    repo = _make_repo(tmp_path)
    common = _commit(repo, "common.txt")
    _fake_remote(repo, "feature", common)

    # 远端多了一个 commit (只在 remote-tracking 上, 本地分支不含)
    remote_only = _commit(repo, "remote-only.txt")
    _git(repo, "reset", "-q", "--hard", common)
    _fake_remote(repo, "feature", remote_only)

    local_sha = _commit(repo, "local.txt")
    refs = _write_refs(tmp_path, "refs/heads/feature", local_sha, remote_only)

    module = _load(EXPORT_SCRIPT, "export_push_range_range")
    module.WORKSPACE = repo
    git_range, reason = module.resolve_range(refs)

    assert git_range == f"{common}..{local_sha}", reason
    # 远端独有的 commit 不在范围里
    assert remote_only not in git_range.split("..")[0]


def test_new_branch_falls_back_to_default_branch(tmp_path):
    """新分支首次 push (无 origin/<branch>) ⇒ 退到 origin/HEAD 作 base 候选。

    git 在 push **成功之后** 才创建 remote-tracking ref, 而 pre-push 跑在 push 之前。
    """
    repo = _make_repo(tmp_path)
    base_sha = _commit(repo, "base.txt")
    _git(repo, "update-ref", "refs/remotes/origin/main", base_sha)
    _git(repo, "symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/main")

    local_sha = _commit(repo, "new.txt")
    refs = _write_refs(tmp_path, "refs/heads/brand-new", local_sha, base_sha)

    module = _load(EXPORT_SCRIPT, "export_push_range_new_branch")
    module.WORKSPACE = repo
    git_range, reason = module.resolve_range(refs)

    assert git_range == f"{base_sha}..{local_sha}", reason


def test_unresolvable_range_reports_reason_instead_of_empty_range(tmp_path):
    """解析不出范围 ⇒ 返回空 range + 明确 reason (不静默返回空集)。"""
    repo = _make_repo(tmp_path)
    local_sha = _commit(repo, "a.txt")
    # 无任何 remote-tracking ref ⇒ 无法定 base
    refs = _write_refs(tmp_path, "refs/heads/orphan", local_sha, "0" * 40)

    module = _load(EXPORT_SCRIPT, "export_push_range_orphan")
    module.WORKSPACE = repo
    git_range, reason = module.resolve_range(refs)

    assert git_range == ""
    assert reason, "必须给出原因, 不能只返回空范围"


def test_empty_refs_file_reports_reason(tmp_path):
    """ref 对为空 (本次 push 没有要推的 ref) ⇒ 空 range + reason。"""
    repo = _make_repo(tmp_path)
    path = tmp_path / "empty_refs.txt"
    path.write_text("", encoding="utf-8")

    module = _load(EXPORT_SCRIPT, "export_push_range_empty")
    module.WORKSPACE = repo
    git_range, reason = module.resolve_range(str(path))

    assert git_range == ""
    assert reason


def test_push_range_env_triggers_per_commit_judgement(tmp_path):
    """PUSH_RANGE 环境变量 ⇒ per-commit 判据 (不是 aggregate)。

    粒度修正的必要性: 「commit A=docs」「commit B=子模块指针」两个 commit 每 commit
    单 lane ⇒ 合规; aggregate 判据却得到 {docs, submodule_pointer} 的假违规。
    """
    repo = _make_repo(tmp_path)
    base_sha = _commit(repo, "base.txt")
    # 第一个 commit: docs 档 (docs lane)
    _commit(repo, "docs/a.md", "doc\n")
    # 第二个 commit: 子模块指针 (submodule_pointer lane)
    (repo / "projects" / "demo").mkdir(parents=True, exist_ok=True)
    (repo / "projects" / "demo" / "x.txt").write_text("x\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "add pointer-ish")
    head = _git(repo, "rev-parse", "HEAD")

    module = _load(LANE_SCRIPT, "change_lane_check_push_range")
    module.WORKSPACE = repo
    report = module.check_range(f"{base_sha}..{head}")

    # 两个 commit 各自单 lane ⇒ 合规
    assert report["ok"], report
    assert report["commits"] == 2


def test_push_range_env_reports_mixed_commit(tmp_path):
    """范围内某个 commit 混 lane ⇒ 必须报出 (判据有牙齿)。"""
    repo = _make_repo(tmp_path)
    base_sha = _commit(repo, "base.txt")
    # 一个 commit 同时改 docs 与 .omo/ (docs + governance_state, 已于 2026-10-30 放宽
    # 为合法组合) —— 故用 code + governance_state 才是仍被拒的形态
    (repo / "bin" / "tool.py").parent.mkdir(parents=True, exist_ok=True)
    (repo / "bin" / "tool.py").write_text("# tool\n", encoding="utf-8")
    (repo / ".omo" / "_knowledge" / "decisions").mkdir(parents=True, exist_ok=True)
    (repo / ".omo" / "_knowledge" / "decisions" / "d.md").write_text("# d\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "mixed")
    head = _git(repo, "rev-parse", "HEAD")

    module = _load(LANE_SCRIPT, "change_lane_check_push_mixed")
    module.WORKSPACE = repo
    report = module.check_range(f"{base_sha}..{head}")

    assert not report["ok"], report
    assert len(report["violations"]) == 1
    assert set(report["violations"][0]["lanes"]) == {"code", "governance_state"}


def test_hook_runner_exports_push_range_in_pre_push(tmp_path):
    """pre-push 必须真的导出 PUSH_RANGE 并跑这道尺。

    2026-10-30 实锤: PUSH_RANGE 分支在 .githooks/ 里无导出点 ⇒ 从未生效。
    """
    hook_runner = ROOT / "bin" / "gac" / "hook-runner.sh"
    text = hook_runner.read_text(encoding="utf-8")
    assert "export-push-range.py" in text, "pre-push 未接线导出脚本"
    assert "export PUSH_RANGE=" in text, "未 export PUSH_RANGE"
    # 必须 blocking (run_check 第 3 参 = true)
    assert 'run_check "change-lane-check" "$py run --profile pyyaml -- bin/change-lane-check.py" true' in text


def test_change_lane_check_push_range_uses_per_commit_not_aggregate(tmp_path):
    """PUSH_RANGE 分支必须走 per-commit 判据, 不是 aggregate。

    aggregate (git diff --name-only <range>) 会把整段合并成一个集合 =>
    「commit A=docs + commit B=子模块指针」两个合规 commit 被判成
    {docs, submodule_pointer} 假违规。规则原文是「每 commit 单 lane」。
    """
    source = LANE_SCRIPT.read_text(encoding="utf-8")
    assert "push_range" in source
    assert 'git_range = args.git_range or (push_range if ".." in push_range else "")' in source
    assert "check_range(git_range" in source
