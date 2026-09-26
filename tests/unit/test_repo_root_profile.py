"""ADR-0456 / BET-Y2Q4-T10-203 — profile-root seam guard.

`bin/lib/repo_root.py` 是 code_root / state_root 的唯一解析处。这个文件的存在理由
是防止收敛被重新分叉: 曾经用于强制这一点的 lint
(`bin/gac/machine-config-write-lint.py`) 已于 2026-09-20 归档, 所以判据必须以测试
的形式留下来, 而不是随 bet 一起消失。
"""

from __future__ import annotations

import ast
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
