"""provenance 身份校验只应覆盖 clone 自身提交 (ADR-0460, BET 收窄 commit_identities_match).

原实现用 `rev-list <base>..<head>` 区间, 该区间包含 clone 建立之后**他人合入 main 的
提交**; 而 `provenance_late_binding` 又禁止重绑 frozen_root_sha。二者构成闭环依赖,
使 clone-lifecycle 在任何并发活跃的仓里不可用。

收窄后区间为 `HEAD --not <mainline refs>`; 主线 ref 不可解析时 fail closed。

三项契约 (ADR-0460 §验收):
  1. 自身提交身份不符          -> 必须拒绝
  2. main 上他人提交            -> 不得阻断
  3. mainline ref 不可解析      -> fail closed
"""

from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("agent_clone", WORKSPACE / "bin" / "gac" / "agent-clone.py")
assert _spec and _spec.loader
ac = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ac)

SELF = ("Clone Bot", "clone@example.invalid")
OTHER = ("Someone Else", "other@example.invalid")


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=True
    ).stdout.strip()


def _repo(tmp_path: Path) -> Path:
    """裸仓: origin 是本地 bare 仓, main 上先有一个他人提交, 交付分支再加一个自身提交。"""
    origin = tmp_path / "origin.git"
    origin.mkdir()
    subprocess.run(["git", "init", "--bare", "-b", "main", str(origin)], check=True, capture_output=True)

    work = tmp_path / "work"
    work.mkdir()
    env_cmds = [
        ["git", "init", "-b", "main", str(work)],
        ["git", "-C", str(work), "config", "user.name", OTHER[0]],
        ["git", "-C", str(work), "config", "user.email", OTHER[1]],
        ["git", "-C", str(work), "remote", "add", "origin", str(origin)],
    ]
    for cmd in env_cmds:
        subprocess.run(cmd, check=True, capture_output=True)
    (work / "a.txt").write_text("a\n")
    subprocess.run(["git", "-C", str(work), "add", "-A"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(work), "commit", "-m", "mainline base"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(work), "push", "origin", "main"], check=True, capture_output=True)
    return work


def _identity(work: Path, base: str, working_branch: str = "deliver") -> dict:
    return {
        "agent_id": "test-agent",
        "requested_revision": "refs/heads/main",
        "working_branch": working_branch,
        "frozen_root_sha": base,
    }


def _add_own_commit(work: Path, name: str, email: str, filename: str = "own.txt") -> None:
    subprocess.run(["git", "-C", str(work), "checkout", "-q", "-b", "deliver"], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(work), "-c", f"user.name={name}", "-c", f"user.email={email}",
         "commit", "-q", "--allow-empty", "-m", f"own {filename}"],
        check=True, capture_output=True,
    )


def test_own_commit_with_wrong_identity_is_rejected(tmp_path: Path) -> None:
    """契约 1: 自身区间内任一提交身份不符 -> 拒绝。收窄不得削弱这项核心保证。"""
    work = _repo(tmp_path)
    base = _git(work, "rev-parse", "HEAD")
    _add_own_commit(work, *OTHER)  # 交付分支上出现了他人身份的提交
    subprocess.run(["git", "-C", str(work), "push", "-q", "origin", "deliver"], check=True, capture_output=True)

    digest = ac.author_identity_digest(*SELF)
    refs = ac._mainline_refs(str(work), _identity(work, base))

    assert ac.commit_identities_match(str(work), base, digest, "HEAD", mainline_refs=refs) is False, (
        "自身提交身份不符却通过了校验 —— 收窄削弱了核心保证"
    )


def test_mainline_foreign_commits_do_not_block(tmp_path: Path) -> None:
    """契约 2: main 上他人提交 -> 不得阻断。区间应只含 clone 自身提交。"""
    work = _repo(tmp_path)
    base = _git(work, "rev-parse", "HEAD")
    _add_own_commit(work, *SELF)
    subprocess.run(["git", "-C", str(work), "push", "-q", "origin", "deliver"], check=True, capture_output=True)

    # 交付之后, 他人又往 main 合了一个提交 (并发常态)
    main = tmp_path / "other"
    main.mkdir()
    for cmd in (
        ["git", "init", "-b", "main", str(main)],
        ["git", "-C", str(main), "config", "user.name", OTHER[0]],
        ["git", "-C", str(main), "config", "user.email", OTHER[1]],
        ["git", "-C", str(main), "remote", "add", "origin", str(tmp_path / "origin.git")],
        ["git", "-C", str(main), "fetch", "-q", "origin"],
        ["git", "-C", str(main), "reset", "-q", "--hard", "origin/main"],
    ):
        subprocess.run(cmd, check=True, capture_output=True)
    (main / "b.txt").write_text("b\n")
    subprocess.run(["git", "-C", str(main), "add", "-A"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(main), "commit", "-q", "-m", "other agent lands on main"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(main), "push", "-q", "origin", "main"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(work), "fetch", "-q", "origin"], check=True, capture_output=True)
    # 真实 clone 的 clone-local user.name/email 必须等于绑定身份
    # (live_author_identity 的硬性要求), 故先切到 SELF 再 rebase。
    # 注意: git rebase 会用**当前 config** 重写 committer 身份 —— 若仓 config 是
    # 他人, 重放后 committer 即变成他人。这既是本用例必须先设 config 的原因,
    # 也是 ADR-0460 方案 A 的一个实际约束: 自身提交的身份依赖 clone-local config。
    subprocess.run(["git", "-C", str(work), "config", "user.name", SELF[0]], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(work), "config", "user.email", SELF[1]], check=True, capture_output=True)
    # 关键: 交付分支更新到新 main (rebase / merge, 即并发下的常态)。
    # 不做这一步, 新旧两种区间都只含自身提交, 测试就抓不到任何东西。
    subprocess.run(
        ["git", "-C", str(work), "rebase", "origin/main"], check=True, capture_output=True
    )

    digest = ac.author_identity_digest(*SELF)
    refs = ac._mainline_refs(str(work), _identity(work, base))
    own = ac.own_commit_shas(str(work), "HEAD", refs)

    # 旧区间 frozen..HEAD 此时已含他人提交 —— 证明本用例非空跑
    legacy = subprocess.run(
        ["git", "-C", str(work), "rev-list", f"{base}..HEAD"],
        capture_output=True, text=True, check=True,
    ).stdout.split()
    assert len(legacy) == 2, f"旧区间应含 2 个提交(自身 + main 上的他人), 实际 {len(legacy)}"
    assert len(own) == 1, f"收窄后自身提交应为 1 个, 实际 {own}"
    # 旧区间下他人提交会让校验失败; 收窄后应通过
    assert ac.commit_identities_match(str(work), base, digest, "HEAD") is False, (
        "旧全区间行为下他人提交本应导致失败"
    )
    assert ac.commit_identities_match(str(work), base, digest, "HEAD", mainline_refs=refs) is True, (
        "收窄后 main 上的他人提交不应阻断自身提交的校验"
    )


def test_working_branch_remote_ref_is_excluded_and_no_remote_degrades(tmp_path: Path) -> None:
    """交付分支自身的远端引用必须被排除, 否则身份校验退化为空转。

    2026-09-30 端到端验收实测: 若把 origin/<交付分支> 也计为主线 ref, 待校验的
    提交本身就是它可达的, own-commit 集恒为空 → 校验空转通过 (橡皮章)。
    """
    work = _repo(tmp_path)
    base = _git(work, "rev-parse", "HEAD")
    _add_own_commit(work, *OTHER)                 # 身份不符的自身提交
    subprocess.run(["git", "-C", str(work), "push", "-q", "origin", "deliver"],
                   check=True, capture_output=True)

    digest = ac.author_identity_digest(*SELF)
    refs = ac._mainline_refs(str(work), _identity(work, base))
    assert "refs/remotes/origin/deliver" not in refs, "交付分支自身的远端引用不得计为主线"
    assert ac.commit_identities_match(str(work), base, digest, "HEAD", mainline_refs=refs) is False, \
        "自身提交身份不符却通过了校验 —— 收窄削弱了核心保证"

    # 完全无 remote 的仓: 返回空列表, 由调用方按「不可判定」降级
    noremote = tmp_path / "noremote"
    noremote.mkdir()
    subprocess.run(["git", "init", "-q", str(noremote)], check=True, capture_output=True)
    assert ac._mainline_refs(str(noremote), {"requested_revision": "refs/heads/main"}) == []


def test_missing_local_main_branch_does_not_fail_closed(tmp_path: Path) -> None:
    """本地 main 分支不存在时**不得** fail-closed (2026-09-30 端到端验收抓到)。

    独立 clone 常处于 detached HEAD 或特性分支, 根本没有 refs/heads/main。
    把 identity.requested_revision 当必需 ref 会让 integrate 100% 阻塞 ——
    而本地分支存不存在与 gitlink 对主线的可达性无关。
    """
    work = _repo(tmp_path)
    base = _git(work, "rev-parse", "HEAD")
    _add_own_commit(work, *SELF)
    subprocess.run(["git", "-C", str(work), "push", "-q", "origin", "deliver"], check=True, capture_output=True)
    # 删掉本地 main, 只留远端跟踪 ref
    subprocess.run(["git", "-C", str(work), "checkout", "-q", "--detach"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(work), "branch", "-qD", "main"], check=True, capture_output=True)

    digest = ac.author_identity_digest(*SELF)
    refs = ac._mainline_refs(str(work), _identity(work, base))
    assert "refs/heads/main" not in refs, "本地 main 不该被当作主线 ref"
    assert ac.commit_identities_match(str(work), base, digest, "HEAD", mainline_refs=refs) is True
