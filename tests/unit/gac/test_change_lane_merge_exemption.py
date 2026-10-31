"""change-lane-check 对 merge commit 的豁免 (ADR-0122 §验收「每 commit 单 lane」)。

**为什么需要豁免** (2026-10-30 实锤):

- merge commit 天然含**两侧**的内容 ⇒ 必然混多个 lane (实测 40 个 merge commit 里
  29 个混 lane, 73%)。这是「合并」这一动作的**结构性事实**, 不是提交形态缺陷。
- 本仓的合流路径只剩 merge 一条: `pre-rebase` hook 明确拒绝 rebase onto main
  (「应走 merge/PR 合流」), 而 main 自身全 squash 合并 ⇒ **merge 是唯一合规的合流路径**。
- 若 lane 尺对 merge commit 一视同仁, 就把这条唯一路径堵死 —— 规则与仓库策略直接冲突。

故 merge 状态下判据**照常计算并报告**, 但**不阻断** (降级为 advisory)。

**定位必须精确** (本文件的测试锁的就是这个):

- MERGE_HEAD 是 **per-worktree** 文件。普通仓在 `<repo>/.git/MERGE_HEAD`;
  linked worktree 在 `<main>/.git/worktrees/<name>/MERGE_HEAD`。
  用 `git rev-parse --git-dir` 会取到**主仓**的 `.git` (worktree 下是错的位置);
  用 `--git-path MERGE_HEAD` 会返回**相对路径** (相对调用 git 时的 cwd),
  拼到别的基准上会指向错的仓。唯一无歧义的定位是 `--absolute-git-dir`。
- 判据的读取对象是 **WORKSPACE 那个仓** (staged 判据走 `git diff --cached`,
  cwd=WORKSPACE) ⇒ 「正在创建的 commit」就是 WORKSPACE 仓的 commit,
  merge 状态必须按**同一个仓**判定。
- 豁免**只对 staged 路径**生效。范围判据 (`--range` / PUSH_RANGE) 用 `--no-merges`,
  merge commit 根本不在范围内 ⇒ 范围里的混 lane 都不是 merge 造成的;
  若那里也按 MERGE_HEAD 豁免, 等于给「push 时恰好有未完成 merge」开了后门
  (MERGE_HEAD 在 merge 完成前一直存在)。
"""

from __future__ import annotations

import importlib.util
import io
import subprocess
import sys
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
LANE_SCRIPT = ROOT / "bin" / "change-lane-check.py"


def _load():
    spec = importlib.util.spec_from_file_location("change_lane_check", str(LANE_SCRIPT))
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["change_lane_check"] = module
    spec.loader.exec_module(module)
    return module


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=repo, capture_output=True, text=True, check=True
    )
    return result.stdout.strip()


def _make_repo(tmp_path: Path, name: str = "repo") -> Path:
    repo = tmp_path / name
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@t.t")
    _git(repo, "config", "user.name", "t")
    return repo


def _git_dir(repo: Path) -> Path:
    """该仓的 (absolute) git dir —— worktree 下是私有 git dir。"""
    return Path(_git(repo, "rev-parse", "--absolute-git-dir"))


def _run_main(module, argv: list[str]) -> tuple[int, str]:
    original = sys.argv
    sys.argv = ["change-lane-check.py", *argv]
    buffer = io.StringIO()
    try:
        with redirect_stdout(buffer):
            code = module.main()
    finally:
        sys.argv = original
    return code, buffer.getvalue()


def test_merge_state_detected_via_absolute_git_dir(tmp_path):
    """MERGE_HEAD 必须按 --absolute-git-dir 定位 —— 相对路径会指错仓。

    `--git-path MERGE_HEAD` 返回 `.git/MERGE_HEAD`, 该相对路径是相对**调用 git
    时的 cwd** 的: 从子目录调用得到 `../.git/MERGE_HEAD`, 换 cwd 结果就变。
    拼到 WORKSPACE 上会指向错的仓库 ⇒ 判据静默失效。
    """
    repo = _make_repo(tmp_path)
    module = _load()
    module.WORKSPACE = repo

    assert module._in_merge_state() is False, "非 merge 状态不应误判"

    (_git_dir(repo) / "MERGE_HEAD").write_text("deadbeef\n", encoding="utf-8")
    assert module._in_merge_state() is True, "MERGE_HEAD 存在时应识别为 merge 状态"


def test_merge_state_detection_is_relative_to_the_governed_repo(tmp_path):
    """检测必须相对**被治理的那个仓** (WORKSPACE), 而非进程 cwd。

    场景: 判据读的 index 是 WORKSPACE 的 (staged 路径走 git diff --cached),
    那么「正在创建的 commit」就是 WORKSPACE 仓的 commit —— merge 状态必须按
    同一个仓判定, 否则两处可能指向不同的仓 (A 仓在 merge, B 仓被判定为非 merge)。
    """
    governed = _make_repo(tmp_path, "governed")
    other = _make_repo(tmp_path, "other")

    module = _load()
    module.WORKSPACE = governed
    (_git_dir(other) / "MERGE_HEAD").write_text("deadbeef\n", encoding="utf-8")

    assert module._in_merge_state() is False, "别的仓在 merge 不应让被治理的仓变成 merge 状态"

    (_git_dir(governed) / "MERGE_HEAD").write_text("deadbeef\n", encoding="utf-8")
    assert module._in_merge_state() is True, "被治理的仓自己在 merge 时必须识别出来"


def test_worktree_merge_head_is_found_in_worktree_private_dir(tmp_path):
    """linked worktree: MERGE_HEAD 在 worktree 私有 git dir, 不在主仓 .git。

    用 --git-dir 会拿到主仓的 .git (错); --absolute-git-dir 拿 worktree 私有目录 (对)。
    """
    main_repo = _make_repo(tmp_path, "main")
    (main_repo / "a.txt").write_text("a\n", encoding="utf-8")
    _git(main_repo, "add", "-A")
    _git(main_repo, "commit", "-q", "-m", "base")

    wt = tmp_path / "wt"
    _git(main_repo, "worktree", "add", "-q", str(wt), "-b", "feature")

    module = _load()
    module.WORKSPACE = wt

    # worktree 私有 git dir 与主仓 .git 是两个不同目录
    wt_git_dir = Path(_git(wt, "rev-parse", "--absolute-git-dir"))
    main_git_dir = Path(_git(main_repo, "rev-parse", "--absolute-git-dir"))
    assert wt_git_dir != main_git_dir
    assert wt_git_dir.parent.parent == main_git_dir, (
        f"worktree 私有 git dir 应在 <main>/.git/worktrees/<name> 下, 实得 {wt_git_dir}"
    )

    assert module._in_merge_state() is False

    # 只在 worktree 私有目录放 MERGE_HEAD => 必须能被识别
    (wt_git_dir / "MERGE_HEAD").write_text("deadbeef\n", encoding="utf-8")
    assert module._in_merge_state() is True, "worktree 私有 git dir 的 MERGE_HEAD 必须被识别"

    # 主仓目录里的 MERGE_HEAD 不应影响 worktree 的判定
    (wt_git_dir / "MERGE_HEAD").unlink()
    (main_git_dir / "MERGE_HEAD").write_text("deadbeef\n", encoding="utf-8")
    assert module._in_merge_state() is False, "主仓的 MERGE_HEAD 不等于该 worktree 在 merge"


def test_merge_commit_is_reported_but_not_blocking(tmp_path):
    """merge 状态下: 混 lane 照常报出, 但 exit code 为 0 (不阻断)。

    非 merge 状态下同样的混 lane 必须仍然阻断 —— 豁免不能扩大到普通提交。
    """
    repo = _make_repo(tmp_path)
    (repo / "a.txt").write_text("a\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "base")

    module = _load()
    module.WORKSPACE = repo

    # 造一个混 lane 的暂存区: bin/ (code) + .omo/ (governance_state)
    (repo / "bin").mkdir(exist_ok=True)
    (repo / "bin" / "x.py").write_text("# x\n", encoding="utf-8")
    (repo / ".omo" / "_knowledge").mkdir(parents=True, exist_ok=True)
    (repo / ".omo" / "_knowledge" / "x.md").write_text("# x\n", encoding="utf-8")
    _git(repo, "add", "-A")

    # 非 merge 状态: 必须阻断
    code, out = _run_main(module, ["--staged"])
    assert code == 1, "非 merge 状态的混 lane 必须阻断"
    assert "FAIL" in out

    # merge 状态: 报告但不阻断
    (_git_dir(repo) / "MERGE_HEAD").write_text("deadbeef\n", encoding="utf-8")
    code, out = _run_main(module, ["--staged"])
    assert code == 0, "merge commit 的混 lane 应降级为 advisory (exit 0)"
    assert "FAIL" in out, "仍须报告混 lane (不能静默放行)"


def test_range_path_is_not_exempted_by_in_progress_merge(tmp_path):
    """范围判据 (--range / PUSH_RANGE) 不因 MERGE_HEAD 存在而被豁免。

    范围判据用 --no-merges => merge commit 根本不在范围内 ⇒ 范围里的混 lane
    都不是 merge 造成的。若这里也豁免, 等于给「push 时恰好有未完成 merge」
    开了后门 (MERGE_HEAD 在 merge 完成前一直存在)。
    """
    repo = _make_repo(tmp_path)
    (repo / "a.txt").write_text("a\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "base")
    base = _git(repo, "rev-parse", "HEAD")

    (repo / "bin").mkdir(exist_ok=True)
    (repo / "bin" / "x.py").write_text("# x\n", encoding="utf-8")
    (repo / ".omo" / "_knowledge").mkdir(parents=True, exist_ok=True)
    (repo / ".omo" / "_knowledge" / "x.md").write_text("# x\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "mixed")
    head = _git(repo, "rev-parse", "HEAD")

    module = _load()
    module.WORKSPACE = repo

    # 造一个未完成的 merge 状态 (MERGE_HEAD 存在)
    (_git_dir(repo) / "MERGE_HEAD").write_text("deadbeef\n", encoding="utf-8")

    code, out = _run_main(module, ["--range", f"{base}..{head}"])
    assert code == 1, "范围判据不得被 MERGE_HEAD 豁免"
    assert "FAIL" in out
