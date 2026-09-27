"""ADR-0456 / BET-Y2Q4-T10-203 — profile-root seam guard.

`bin/lib/repo_root.py` 是 code_root / state_root 的唯一解析处。这个文件的存在理由
是防止收敛被重新分叉: 曾经用于强制这一点的 lint
(`bin/gac/machine-config-write-lint.py`) 已于 2026-09-20 归档, 所以判据必须以测试
的形式留下来, 而不是随 bet 一起消失。
"""

from __future__ import annotations

import ast
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "bin" / "lib"))

import repo_root  # noqa: E402

LEDGER_BASENAME = "event-ledger.sqlite3"
OMO_PATHS_SRC = REPO / "projects" / "omo" / "src" / "omo" / "omo_paths.py"


def _ledger_path_joins(path: Path) -> list[int]:
    """返回以 `/` 拼接出 ledger 文件的行号 (纯字符串常量不算)。"""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    hits: list[int] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.BinOp) or not isinstance(node.op, ast.Div):
            continue
        operands = (node.left, node.right)
        if any(
            isinstance(o, ast.Constant)
            and isinstance(o.value, str)
            and LEDGER_BASENAME in o.value
            for o in operands
        ):
            hits.append(node.lineno)
    return hits


# ── 未声明 profile 时必须逐字节复现历史路径 ──────────────


def test_unset_profile_reproduces_checkout_layout() -> None:
    assert repo_root.state_root() == repo_root.code_root()
    assert repo_root.event_ledger_path() == (
        repo_root.code_root() / "runtime" / "omo" / LEDGER_BASENAME
    )


def test_declared_profile_moves_state_root(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OMO_EVENT_LEDGER_DB", raising=False)
    monkeypatch.setenv("OMOSTATION_STATE_ROOT", "/tmp/omostation-dev-state")
    assert repo_root.state_root() == Path("/tmp/omostation-dev-state")
    assert repo_root.event_ledger_path() == Path(
        "/tmp/omostation-dev-state/runtime/omo/event-ledger.sqlite3"
    )


def test_ledger_env_wins_over_profile(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OMOSTATION_STATE_ROOT", "/tmp/omostation-dev-state")
    monkeypatch.setenv("OMO_EVENT_LEDGER_DB", "/tmp/explicit.sqlite3")
    assert repo_root.event_ledger_path() == Path("/tmp/explicit.sqlite3")


# ── 契约只能有一个变量名 ────────────────────────────────


def test_state_root_env_name_matches_kernel_contract() -> None:
    """omo 包不能反向 import 父仓, 所以两处各自声明同一个 env 名 — 这里钉住它。"""
    src = OMO_PATHS_SRC.read_text(encoding="utf-8")
    assert f'STATE_ROOT_ENV = "{repo_root.STATE_ROOT_ENV}"' in src, (
        "repo_root 与 omo_paths 的 profile 变量名不再一致"
    )


# ── 回归护栏: bin/ 不得再造独立的 ledger 默认值 ──────────


@pytest.mark.parametrize(
    "script",
    sorted((REPO / "bin").rglob("*.py")),
    ids=lambda p: str(p.relative_to(REPO)),
)
def test_bin_ledger_defaults_route_through_seam(script: Path) -> None:
    if not _ledger_path_joins(script):
        return
    src = script.read_text(encoding="utf-8")
    if "event_ledger_path(" in src:
        return
    if script.relative_to(REPO).as_posix() == "bin/lib/repo_root.py":
        return  # 接缝本身
    if "OMO_EVENT_LEDGER_DB" in src:
        return  # 必须能作为单文件部署到仓外的宿主脚本 (panorama)
    pytest.fail(
        f"{script.relative_to(REPO)} 自行拼接 event ledger 路径且不走 seam: "
        "改用 bin/lib/repo_root.py:event_ledger_path()"
    )


# ── omo_paths 的读侧必须留在 code_root ───────────────────


_PROBE = (
    "import sys; sys.path.insert(0, %r);"
    "from omo import omo_paths as p;"
    "print(p.STATE_ROOT);print(p.OMO_ROOT);print(p.TRUTH_DIR);"
    "print(p.RUNTIME_OMO_ROOT);print(p.projection_path('health'))"
) % str(REPO / "projects" / "omo" / "src")


def _probe(state_root: str) -> list[str]:
    env = {**os.environ, "OMOSTATION_STATE_ROOT": state_root}
    out = subprocess.run(
        [sys.executable, "-c", _PROBE],
        capture_output=True,
        text=True,
        env=env,
        check=True,
    )
    return out.stdout.splitlines()


def test_kernel_read_plane_stays_on_checkout(tmp_path: Path) -> None:
    """profile 只搬写侧; 治理 SSOT 读取必须跟随当前检出, 否则 worktree 会去主仓取真值。"""
    state_root = tmp_path / "dev-state"
    canonical = state_root / ".omo" / "state" / "runtime"
    canonical.mkdir(parents=True)
    (canonical / "health.yaml").write_text("score: 0\n", encoding="utf-8")

    state, omo_root, truth_dir, runtime_omo, health = _probe(str(state_root))
    assert state == str(state_root)
    assert runtime_omo == str(state_root / "runtime" / "omo")
    assert health == str(state_root / ".omo" / "state" / "runtime" / "health.yaml")
    assert omo_root == str(REPO / ".omo")
    assert truth_dir == str(REPO / ".omo" / "_truth")


def test_projection_falls_back_to_committed_legacy_path(tmp_path: Path) -> None:
    """空 state root 下读者退回仓内已提交的 legacy 文件 — dev profile 不因缺状态而失明。"""
    (tmp_path / ".omo" / "state" / "runtime").mkdir(parents=True)
    _, _, _, _, health = _probe(str(tmp_path))
    assert health == str(REPO / ".omo" / "state" / "health.yaml")


# ── B4a (BET-Y2Q4-T10-207): 安装位是定位器, 不是开关 ──────
#
# 三条一起才构成这一轮的契约: 安装位可定位、canonical 解析结果没被搬走、
# 每日清扫扫不到它。全部在假 $HOME 下测, 不读真机的 ~/.local 或 ~/Workspace。


def _make_checkout(root: Path) -> Path:
    """造一个看起来像规范检出的目录 (只需要 MARKER)。"""
    (root / repo_root.MARKER).parent.mkdir(parents=True, exist_ok=True)
    (root / repo_root.MARKER).write_text("projects: []\n", encoding="utf-8")
    return root


@pytest.fixture()
def fake_home(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> Path:
    """假 $HOME: 里面有 ~/Workspace 检出, 且 profile env 全部清空。"""
    for var in (
        "HOME",
        "OMOSTATION_ROOT",
        "OMOSTATION_INSTALL_ROOT",
        "OMOSTATION_STATE_ROOT",
        "OMO_EVENT_LEDGER_DB",
    ):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    _make_checkout(tmp_path / "Workspace")
    return tmp_path


def test_install_root_absent_is_none_not_error(fake_home: Path) -> None:
    """没装过运行时的机器(CI、别人的电脑)必须能正常问这一句, 不能靠异常回答。"""
    assert repo_root.install_root() is None


def test_install_root_default_is_under_local_opt(fake_home: Path) -> None:
    located = _make_checkout(fake_home / repo_root.INSTALL_ROOT_RELATIVE)
    assert repo_root.install_root() == located


def test_install_root_env_wins_and_still_requires_marker(
    monkeypatch: pytest.MonkeyPatch, fake_home: Path
) -> None:
    elsewhere = fake_home / "somewhere-else"
    monkeypatch.setenv("OMOSTATION_INSTALL_ROOT", str(elsewhere))
    assert repo_root.install_root() is None  # 没 MARKER 的目录不算安装位
    _make_checkout(elsewhere)
    assert repo_root.install_root() == elsewhere


def test_landing_an_install_root_does_not_move_any_existing_root(fake_home: Path) -> None:
    """B4a 的全部要点: 装上安装位, 但 canonical_root/state_root/ledger 一个都不改道。

    改道是 B4b 的切换动作。此刻 43 个 plist 仍指向 ~/Workspace 且在跑, 让解析器
    在新目录出现的那一刻换目标 = 静默重定向所有写机器级配置的工具。
    """
    before_canonical = repo_root.canonical_root()
    before_state = repo_root.state_root()
    before_ledger = repo_root.event_ledger_path()

    located = _make_checkout(fake_home / repo_root.INSTALL_ROOT_RELATIVE)

    assert repo_root.install_root() == located
    assert repo_root.canonical_root() == before_canonical == fake_home / "Workspace"
    assert repo_root.state_root() == before_state == repo_root.code_root()
    assert repo_root.event_ledger_path() == before_ledger


def test_roots_report_cli_is_read_only_and_names_every_root(tmp_path: Path) -> None:
    """`--json` 是这轮唯一的新入口; 它的键就是 agent 的感知面。"""
    located = _make_checkout(tmp_path / "opt" / "omostation")
    state = tmp_path / "state"
    env = {
        **os.environ,
        "OMOSTATION_INSTALL_ROOT": str(located),
        "OMOSTATION_STATE_ROOT": str(state),
    }
    out = subprocess.run(
        [sys.executable, str(REPO / "bin" / "lib" / "repo_root.py"), "--json"],
        capture_output=True,
        text=True,
        env=env,
        cwd=located,
        check=True,
    )
    report = json.loads(out.stdout)
    assert {
        "code_root",
        "canonical_root",
        "state_root",
        "state_root_declared",
        "event_ledger_path",
        "event_ledger_override",
        "install_root",
        "cwd_is_install_root",
        "cwd_is_canonical_root",
    } <= set(report)
    assert report["install_root"] == str(located)
    assert report["code_root"] == str(repo_root.code_root())
    assert report["state_root"] == str(state)
    assert report["state_root_declared"] is True
    assert report["event_ledger_path"] == str(state / repo_root.LEDGER_RELATIVE)
    # code_root 由 __file__ 推导, 所以跑在哪个 cwd 与它无关 —— 这两条钉住"读侧跟随检出"
    assert report["cwd_is_install_root"] is True
    assert report["cwd_is_canonical_root"] is False


def test_hygiene_sweep_cannot_select_the_install_root(
    monkeypatch: pytest.MonkeyPatch, fake_home: Path
) -> None:
    """plan 原写"加排除清单"; 实测清扫根本扫不到这里, 于是把事实钉成测试。

    worktree-hygiene-audit 的候选面只有 $HOME 的 `ws-*` / `workspace-*` 直接子目录
    (外加登记进共享 .git 的 worktree)。谁把 glob 扩宽到 `$HOME/*` 或 `.local/**`,
    这条就红 —— 那正是"运行时被一次清理残留扫掉"的事故形状。
    """
    located = _make_checkout(fake_home / repo_root.INSTALL_ROOT_RELATIVE)
    (fake_home / "ws-example").mkdir()

    spec = importlib.util.spec_from_file_location(
        "worktree_hygiene_audit", REPO / "bin" / "gac" / "worktree-hygiene-audit.py"
    )
    assert spec and spec.loader
    audit = importlib.util.module_from_spec(spec)
    # dataclass 字段解析要按 __module__ 反查 sys.modules, 不登记就会在 exec_module 里炸
    sys.modules[spec.name] = audit
    spec.loader.exec_module(audit)

    candidates = {str(path) for path in audit._candidate_dirs()}
    assert str(fake_home / "ws-example") in candidates  # 候选面确实生效
    assert not any(str(located).startswith(cand) for cand in candidates)
