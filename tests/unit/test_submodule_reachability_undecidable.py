"""submodule-reachability 的「不可判定 ≠ 不可达」契约 (2026-09-29).

原实现的三处缺陷, 均可在 PASW 工作树里复现:

1. 回退判定用 ``git branch -r --contains <sha>``, 它**依赖可解析的 HEAD**。
   残缺 clone (``rev-parse HEAD`` → unknown revision) 下该命令以 rc=128 +
   "failed to resolve HEAD as a valid ref" 失败, stdout 为空。
2. 该路径**从不检查 returncode** —— 报错与「真的不可达」被当成同一件事,
   误报 unreachable 并阻断 push。
3. fetch 之后仍为浅克隆 / 对象缺失时, 未降级 —— 而 ``_fetch_verdict`` 的
   docstring 明写「拒绝把超时伪装成 unreachable 阻断 push」。

另有一个自我阻断死循环: 上一次 ``git fetch --unshallow`` 超时会留下
``shallow.lock``, 使后续 fetch 立即失败 → 仓库永远停在浅克隆 → 误报 unreachable
→ push 被永久阻断, 而唯一能修好它的正是这个被阻断的 push。

本测试用真实 git 仓覆盖**可复现**的契约:
  - gitlink 确实不是主线祖先        -> 必须拦下
  - 本地 main 领先/含孤立提交       -> 必须拦下 (防橡皮章后门)
  - require_main 模式仍能正常判可达

关于「残缺 clone 导致 branch --contains 返回空」这一具体机制: 实测
`git branch -r --contains` 对 HEAD 不可解析**并不失败** (rc=0), 故无法用合成仓
复现, 不在本文件断言。它的证据是端到端的: 2026-09-29 某 PASW 工作树上
submodule-reachability 报 5 failures, 本改动后同命令报 PASS (16 gitlinks)。
"""

from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "reach_gate", WORKSPACE / "bin" / "ssot" / "submodule-reachability-gate.py"
)
assert _spec and _spec.loader
gate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gate)


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=True
    ).stdout.strip()


def _bind(tmp_path: Path) -> Path:
    """把 gate 的 WORKSPACE 指向 tmp, 使 remote_contains 能按相对路径找到子模块。"""
    gate.WORKSPACE = tmp_path
    return tmp_path


def _submodule(tmp_path: Path, name: str = "sub") -> tuple[Path, Path]:
    """origin bare 仓 + 一个已 fetch 过 origin/main 的 submodule clone."""
    origin = tmp_path / "origin.git"
    origin.mkdir()
    subprocess.run(["git", "init", "--bare", "-b", "main", str(origin)], check=True, capture_output=True)

    seed = tmp_path / "seed"
    seed.mkdir()
    for cmd in (
        ["git", "init", "-b", "main", str(seed)],
        ["git", "-C", str(seed), "config", "user.name", "T"],
        ["git", "-C", str(seed), "config", "user.email", "t@example.invalid"],
        ["git", "-C", str(seed), "remote", "add", "origin", str(origin)],
    ):
        subprocess.run(cmd, check=True, capture_output=True)
    (seed / "a").write_text("a\n")
    subprocess.run(["git", "-C", str(seed), "add", "-A"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(seed), "commit", "-qm", "reachable base"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(seed), "push", "-q", "origin", "main"], check=True, capture_output=True)
    reachable = _git(seed, "rev-parse", "HEAD")

    sub = tmp_path / name
    subprocess.run(["git", "clone", "-q", str(origin), str(sub)], check=True, capture_output=True)
    return sub, reachable


def test_genuinely_unreachable_gitlink_is_still_blocked(tmp_path: Path) -> None:
    """契约 2: gitlink 确实不在任何主线 ref 上 -> **必须拦下**。

    这是防止本次修复把检查改成橡皮章的关键断言。
    """
    _bind(tmp_path)
    sub, _reachable = _submodule(tmp_path)

    # 造一个本地存在、但不在 origin/main 历史里的提交 (孤立提交)
    orphan = subprocess.run(
        ["git", "-C", str(sub), "commit", "-qm", "orphan", "--allow-empty"], capture_output=True
    )
    assert orphan.returncode == 0
    orphan_sha = _git(sub, "rev-parse", "HEAD")

    ok, _detail = gate.remote_contains(path="sub", sha=orphan_sha, fetch=False, require_main=False)

    assert ok is False, "真正不可达的 gitlink 被放行 —— 检查已退化为橡皮章"


def test_require_main_mode_resolves_reachability(tmp_path: Path) -> None:
    """CI 模式 (require_main=True) 同样走 is-ancestor, 不依赖分支枚举。"""
    _bind(tmp_path)
    sub, reachable = _submodule(tmp_path)

    ok, detail = gate.remote_contains(path="sub", sha=reachable, fetch=False, require_main=True)

    assert ok is True, f"CI 模式误杀可达 gitlink: {detail}"


def test_local_branch_ahead_does_not_grant_reachability(tmp_path: Path) -> None:
    """本地 main 领先/含孤立提交时**不得**被判为可达 (防橡皮章)。"""
    _bind(tmp_path)
    sub, _reachable = _submodule(tmp_path)
    # 在 clone 的本地 main 上造一个只存在于本地的孤立提交
    subprocess.run(
        ["git", "-C", str(sub), "-c", "user.name=T", "-c", "user.email=t@example.invalid",
         "commit", "-qm", "local only", "--allow-empty"],
        check=True, capture_output=True,
    )
    orphan = _git(sub, "rev-parse", "HEAD")

    ok, _detail = gate.remote_contains(path="sub", sha=orphan, fetch=False, require_main=False)

    assert ok is False, "只存在于本地分支的提交被放行 —— 检查已退化为橡皮章"


def test_stale_lock_detection_helpers() -> None:
    assert gate._looks_like_locked("fatal: Another git process seems to be running") is True
    assert gate._looks_like_locked("error: cannot lock ref 'x': is at ...") is True
    assert gate._looks_like_locked("fatal: unable to access 'https://...': timeout") is False
    assert gate._looks_like_locked("") is False
