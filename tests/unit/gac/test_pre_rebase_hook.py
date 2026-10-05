"""pre-rebase hook 回归测试 (PITFALL-GAT-012 要求的「补 pre-rebase 回归测试」)。

覆盖旧版两个缺陷：
  ① 逃生口写死失效 —— 单引号 `[ ]` 内 `!=` 是字面串比较，只有 `[[ ]]` 才 glob
     ⇒ `SWARM_ESCAPE_ID=rebase-ci` 永远不生效。
  ② onto 取错参数 —— 旧版读 `$2` 当 onto，但 git 传的 `$2` 是**被 rebase 的分支名**
     ⇒ 拒绝逻辑从不触发。

设计要点（沿用 memory 的「判据须自证」纪律）：每个用例都用**真实 git 仓库**跑 hook，
不 mock 掉 hook 本身；并对每条拒绝分支跑「正反对照」——改坏时测试必须变红。
"""

from __future__ import annotations

import os
import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
HOOK = REPO_ROOT / ".githooks" / "pre-rebase"


def _git(*args: str, cwd: Path, env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, env=env
    )


@pytest.fixture
def sandbox(tmp_path: Path) -> Path:
    """一个含 main + feature 分支的裸克隆，可直接跑 git rebase。"""
    origin = tmp_path / "origin.git"
    origin.mkdir()
    _git("init", "-q", "--bare", ".", cwd=origin)

    work = tmp_path / "work"
    _git("clone", "-q", str(origin), str(work), cwd=tmp_path)
    _git("config", "user.email", "hook@test", cwd=work)
    _git("config", "user.name", "hook test", cwd=work)

    (work / "f").write_text("base\n")
    _git("add", "f", cwd=work)
    _git("commit", "-qm", "base", cwd=work)
    _git("push", "-q", "origin", "HEAD:refs/heads/main", cwd=work)

    # feature 分支多一个提交
    _git("checkout", "-qb", "feature", cwd=work)
    (work / "f").write_text("feature\n")
    _git("commit", "-qam", "feature", cwd=work)

    # main 前进，逼 feature 真的需要 rebase
    _git("checkout", "-q", "main", cwd=work)
    (work / "m").write_text("main\n")
    _git("add", "m", cwd=work)
    _git("commit", "-qm", "main advance", cwd=work)
    _git("push", "-q", "origin", "main", cwd=work)
    _git("checkout", "-q", "feature", cwd=work)
    _git("fetch", "-q", "origin", cwd=work)
    return work


def _run_hook(args: list[str], cwd: Path, escape: str | None = None) -> subprocess.CompletedProcess:
    """直接调 hook，参数与 git 实际传入的一致。"""
    env = dict(os.environ)
    if escape is not None:
        env["SWARM_ESCAPE_ID"] = escape
    else:
        env.pop("SWARM_ESCAPE_ID", None)
    return subprocess.run(
        [str(HOOK), *args], cwd=cwd, capture_output=True, text=True, env=env
    )


class TestOntoComesFromArg1:
    """缺陷②：onto 是 $1，不是 $2。"""

    def test_rejects_rebase_onto_main(self, sandbox: Path) -> None:
        """git rebase main → $1=main ⇒ 必须拒绝。"""
        r = _run_hook(["main"], sandbox)
        assert r.returncode == 1, f"onto=main 应拒绝，实际 rc={r.returncode}"
        assert "拒绝 rebase onto main" in r.stderr

    def test_rejects_rebase_onto_origin_main(self, sandbox: Path) -> None:
        r = _run_hook(["origin/main"], sandbox)
        assert r.returncode == 1
        assert "拒绝 rebase onto origin/main" in r.stderr

    def test_arg2_is_branch_not_onto(self, sandbox: Path) -> None:
        """$2=main 形态（--onto 的第三参恰为 main）不得被当成 onto 拒绝。

        旧版在这里会读 $2=main ⇒ 误拒；新版 $2 只是分支名提示。
        用 HEAD^ 作 $1（确为祖先，隔离掉祖先检查，只验「$2 不当 onto」）。
        """
        head_parent = _git("rev-parse", "HEAD^", cwd=sandbox).stdout.strip()
        r = _run_hook([head_parent, "main"], sandbox)
        assert r.returncode == 0, (
            f"$2 是分支名，不该当 onto 拒绝；rc={r.returncode} stderr={r.stderr}"
        )

    def test_allows_rebase_onto_feature_branch(self, sandbox: Path) -> None:
        """onto 非 main ⇒ 放行（证明判据有判别力，不是恒拒）。"""
        head_parent = _git("rev-parse", "HEAD^", cwd=sandbox).stdout.strip()
        r = _run_hook([head_parent], sandbox)
        assert r.returncode == 0, f"非 main 的 onto 应放行；rc={r.returncode} stderr={r.stderr}"


class TestEscapeHatch:
    """缺陷①：`[[ ]]` glob 让逃生口真正生效。"""

    def test_blocked_without_escape(self, sandbox: Path) -> None:
        assert _run_hook(["main"], sandbox).returncode == 1

    def test_escape_id_allows_through(self, sandbox: Path) -> None:
        """旧版此用例必红：`[ "rebase-ci" != rebase-* ]` 恒真 ⇒ 仍 exit 1。"""
        r = _run_hook(["main"], sandbox, escape="rebase-ci")
        assert r.returncode == 0, (
            f"SWARM_ESCAPE_ID=rebase-ci 应放行；rc={r.returncode} stderr={r.stderr}"
        )
        assert "已放行" in r.stderr

    def test_unrelated_escape_id_does_not_bypass(self, sandbox: Path) -> None:
        """非 rebase-* 的逃生 id 不得放行（证明 glob 不是通配一切）。"""
        r = _run_hook(["main"], sandbox, escape="some-other-task")
        assert r.returncode == 1, "不相关 escape id 不该放行"


class TestAncestorCheck:
    def test_non_ancestor_base_blocks(self, sandbox: Path) -> None:
        """base 非 HEAD 祖先 ⇒ 拒绝。"""
        unrelated = _git("rev-parse", "origin/main", cwd=sandbox).stdout.strip()
        # 造一个与 feature 无祖先关系的提交
        _git("checkout", "-q", "--orphan", "island", cwd=sandbox)
        _git("rm", "-rfq", ".", cwd=sandbox)
        (sandbox / "x").write_text("island\n")
        _git("add", "x", cwd=sandbox)
        _git("commit", "-qm", "island", cwd=sandbox)
        island = _git("rev-parse", "HEAD", cwd=sandbox).stdout.strip()
        _git("checkout", "-q", "feature", cwd=sandbox)
        assert unrelated and island

        r = _run_hook([island], sandbox)
        assert r.returncode == 1
        assert "不是 HEAD 的祖先" in r.stderr

    def test_ancestor_base_passes(self, sandbox: Path) -> None:
        """base 是祖先 ⇒ 放行（判别力：不是恒拒）。"""
        base = _git("rev-parse", "HEAD", cwd=sandbox).stdout.strip()
        r = _run_hook([base], sandbox)
        assert r.returncode == 0, f"祖先 base 应放行；rc={r.returncode} stderr={r.stderr}"


class TestHookIsExecutable:
    """补 +x 之后，git 才真正会调用它；模式须为 100755。"""

    @pytest.mark.parametrize("name", ["pre-rebase", "pre-merge-commit", "post-merge"])
    def test_hook_mode_is_executable(self, name: str) -> None:
        mode = _git(
            "ls-files", "-s", f".githooks/{name}", cwd=REPO_ROOT
        ).stdout.split()[0]
        assert mode == "100755", f".githooks/{name} 应为 100755，实际 {mode}"

    def test_pre_rebase_has_shebang(self) -> None:
        assert HOOK.read_text().startswith("#!/bin/bash")


class TestRealGitInvocation:
    """端到端：装上 hook 后真跑 `git rebase main` 必须被拦。"""

    def test_git_rebase_main_is_blocked(self, sandbox: Path) -> None:
        hooks = sandbox / ".githooks"
        hooks.mkdir(exist_ok=True)
        shutil.copy(HOOK, hooks / "pre-rebase")
        (hooks / "pre-rebase").chmod(0o755)
        _git("config", "core.hooksPath", ".githooks", cwd=sandbox)

        r = _git("rebase", "main", cwd=sandbox)
        assert r.returncode != 0, "真 git rebase main 应被 hook 拦住"
        assert "拒绝 rebase onto main" in (r.stderr + r.stdout)

    def test_git_rebase_onto_feature_succeeds(self, sandbox: Path) -> None:
        """正向对照：onto 非 main 时 rebase 成功（证明 hook 不是恒拦）。"""
        hooks = sandbox / ".githooks"
        hooks.mkdir(exist_ok=True)
        shutil.copy(HOOK, hooks / "pre-rebase")
        (hooks / "pre-rebase").chmod(0o755)
        _git("config", "core.hooksPath", ".githooks", cwd=sandbox)
        _git("branch", "other", cwd=sandbox)

        r = _git("rebase", "other", cwd=sandbox)
        assert r.returncode == 0, f"onto=other 应成功；stderr={r.stderr}"
