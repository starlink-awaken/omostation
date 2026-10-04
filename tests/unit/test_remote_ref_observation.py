"""changeset 阶段的远端 ref 观察 (ADR-0461 第 5 步).

`expected_remote_oid` 是**推送前置条件**, 不是「分支当前在哪」的快照:
integrate 首次推送 delivery 分支时远端该 ref 尚不存在, 正常取值就是哨兵
`ABSENT_REMOTE_OID`("0"*40) —— 语义与 fence 侧的
`build_remote_observation_pair`(clone-lifecycle.py:1266)对齐。

核心契约: **不可达 ≠ 不存在**。网络抖动若被当成「ref 缺失」返回哨兵,
fence 的前置条件就失去意义 —— 这正是本轮反复修的「不可判定 ≠ 不可用」同一族缺陷。
"""

from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path

import pytest

WORKSPACE = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "agent_clone_remote", WORKSPACE / "bin" / "gac" / "agent-clone.py"
)
assert _spec and _spec.loader
ac = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ac)


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=True
    ).stdout.strip()


@pytest.fixture
def clone_with_remote(tmp_path: Path) -> tuple[Path, str]:
    """一个带 origin 的 clone, 并在 origin 上放一条已存在的远端分支。"""
    origin = tmp_path / "origin.git"
    origin.mkdir()
    subprocess.run(["git", "init", "--bare", "-b", "main", str(origin)], check=True, capture_output=True)

    seed = tmp_path / "seed"
    seed.mkdir()
    for cmd in (
        ["git", "init", "-b", "main", str(seed)],
        ["git", "-C", str(seed), "config", "user.name", "t"],
        ["git", "-C", str(seed), "config", "user.email", "t@example.com"],
        ["git", "-C", str(seed), "remote", "add", "origin", str(origin)],
    ):
        subprocess.run(cmd, check=True, capture_output=True)
    (seed / "a.txt").write_text("a\n")
    subprocess.run(["git", "-C", str(seed), "add", "-A"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(seed), "commit", "-m", "base"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(seed), "push", "origin", "main"], check=True, capture_output=True)

    work = tmp_path / "work"
    work.mkdir()
    for cmd in (
        ["git", "clone", str(origin), str(work)],
        ["git", "-C", str(work), "config", "user.name", "t"],
        ["git", "-C", str(work), "config", "user.email", "t@example.com"],
    ):
        subprocess.run(cmd, check=True, capture_output=True)
    return work, "refs/heads/main"


def test_green_existing_ref_returns_its_oid(clone_with_remote) -> None:
    work, ref = clone_with_remote
    expected = _git(work, "ls-remote", "origin", "refs/heads/main").split()[0]
    assert ac.observe_remote_ref(str(work), ref) == expected


def test_green_absent_ref_returns_sentinel_not_error(clone_with_remote) -> None:
    """delivery 分支首推时远端尚不存在 —— 正常取值是哨兵, 不是异常。"""
    work, _ = clone_with_remote
    assert ac.observe_remote_ref(str(work), "refs/heads/agent/does-not-exist") == ac.ABSENT_REMOTE_OID
    assert ac.ABSENT_REMOTE_OID == "0" * 40


def test_red_unreachable_remote_raises_instead_of_reporting_absent(
    clone_with_remote, monkeypatch
) -> None:
    """不可达不得伪装成「不存在」—— 返回哨兵会让 fence 前置条件失效。"""
    work, ref = clone_with_remote

    class _P:
        returncode = 128
        stdout = ""
        stderr = "fatal: unable to access 'https://example.invalid': Could not resolve host"

    monkeypatch.setattr(ac, "git", lambda *_a, **_k: _P())
    with pytest.raises(ac.ToolError) as exc:
        ac.observe_remote_ref(str(work), ref)
    assert exc.value.reason == "remote_ref_observation_unavailable"


def test_red_timeout_raises_rather_than_reporting_absent(
    clone_with_remote, monkeypatch
) -> None:
    work, ref = clone_with_remote

    class _P:
        returncode = 124
        stdout = ""
        stderr = "timeout after 60s"

    monkeypatch.setattr(ac, "git", lambda *_a, **_k: _P())
    with pytest.raises(ac.ToolError) as exc:
        ac.observe_remote_ref(str(work), ref)
    assert exc.value.reason == "remote_ref_observation_unavailable"


def test_red_malformed_ls_remote_output_raises(clone_with_remote, monkeypatch) -> None:
    work, ref = clone_with_remote

    class _P:
        returncode = 0
        stdout = "not-a-sha\trefs/heads/main\n"
        stderr = ""

    monkeypatch.setattr(ac, "git", lambda *_a, **_k: _P())
    with pytest.raises(ac.ToolError) as exc:
        ac.observe_remote_ref(str(work), ref)
    assert exc.value.reason == "remote_ref_observation_malformed"


def test_red_multiple_rows_raises(clone_with_remote, monkeypatch) -> None:
    """一行 ref 只应对应一行输出; 多行说明观测本身不可信。"""
    work, ref = clone_with_remote

    class _P:
        returncode = 0
        stdout = f"{'a' * 40}\trefs/heads/main\n{'b' * 40}\trefs/heads/other\n"
        stderr = ""

    monkeypatch.setattr(ac, "git", lambda *_a, **_k: _P())
    with pytest.raises(ac.ToolError) as exc:
        ac.observe_remote_ref(str(work), ref)
    assert exc.value.reason == "remote_ref_observation_malformed"


def test_sentinel_matches_fence_side_constant() -> None:
    """哨兵必须与 fence 侧 (clone-lifecycle.py:1244) 逐字节一致。"""
    src = (WORKSPACE / "bin" / "gac" / "clone-lifecycle.py").read_text(encoding="utf-8")
    # 源码里是表达式字面量 "_ABSENT_REMOTE_OID = \"0\" * 40", 不是展开后的 40 个零
    assert '_ABSENT_REMOTE_OID = "0" * 40' in src
    assert ac.ABSENT_REMOTE_OID == "0" * 40
