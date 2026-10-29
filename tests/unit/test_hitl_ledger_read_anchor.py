"""ADR-0456 B1 读侧锚定: HITL 人在环门禁的台账读取不得随进程 CWD 漂.

被检对象: `bin/hitl-proposal.py::check_human_gate_needed()` —— 它原先用
`Path("docs/plans/3y-bet-ledger.yaml")` 相对**进程 CWD** 取台账，于是同一命令
在仓根读出 `HITL_REQUIRED`、在 `/tmp` 读出「不需要人审」，审批步静默 fail-open。

判据分层（缺一层就会留下「测试绿着但锚定仍随 CWD」的缝）：
- **锚定**：CWD 在别处时仍按检出根读到台账（第 1 条，修复前必红）。
- **锚定直接取证**：resolver 返回的台账路径必须落在 fixture 造的那棵假检出里，
  不是宿主检出（第 2 条；它读返回值本身，与被测函数不共享失效模式）。
- **fixture 自证**：台账只在 fixture 检出存在、foreign_cwd 按构造没有（第 3 条）
  —— 修复前后都绿，所以第 1 条的红只能来自锚定，不能来自装置坏。
- **对照**：CWD 恰为检出根时同样为真（第 4 条，修复前后都绿）。
- **非 blanket**：未声明 human_gate 的 id 与不存在的 id 仍为 False（第 5 条，
  排除「把返回值改成恒真」这类作弊修法）。
- **语义守恒**：检出里真的没有台账时仍然返回 False，不抛（第 6 条 —— ADR-0451
  把这条降级写成设计行为，本轮只改锚定，不改 fail-open 政策）。

台账内容全部由 fixture 造，不读宿主台账 ⇒ 无时钟/数据依赖（AGENTS.md §7「时钟炸弹」）。
"""

from __future__ import annotations

import importlib.util
import shutil
import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "bin" / "lib"))
import repo_root  # noqa: E402

CHECKOUT = repo_root.code_root()
HITL_SRC = CHECKOUT / "bin" / "hitl-proposal.py"
REPO_ROOT_SRC = CHECKOUT / "bin" / "lib" / "repo_root.py"

LEDGER_REL = "docs/plans/3y-bet-ledger.yaml"
GATED_ID = "BET-FAKE-GATED"
UNGATED_ID = "BET-FAKE-UNGATED"


def _materialize_checkout(root: Path, *, with_ledger: bool) -> Path:
    """造一棵只在此处存在的检出：真源复制 + 一份含 human_gate 的台账。

    复制真源而不是重写路径解析，测的才是那把尺本身。
    """
    (root / "bin" / "lib").mkdir(parents=True)
    shutil.copy2(HITL_SRC, root / "bin" / "hitl-proposal.py")
    shutil.copy2(REPO_ROOT_SRC, root / "bin" / "lib" / "repo_root.py")
    ledger = root / LEDGER_REL
    ledger.parent.mkdir(parents=True)
    if with_ledger:
        ledger.write_text(
            yaml.safe_dump(
                {
                    "bets": [
                        {"id": GATED_ID, "human_gate": True, "title": "需要人审"},
                        {"id": UNGATED_ID, "human_gate": False, "title": "不需要人审"},
                    ]
                },
                allow_unicode=True,
                sort_keys=False,
            ),
            encoding="utf-8",
        )
    return root


def _load_hitl(checkout: Path):
    """按 checkout 里那份 hitl-proposal 加载模块，并保证它 bind 的是同棵树的 repo_root。

    宿主 bin/lib 往往已在 sys.path 上（本文件顶部就插过一次），所以路径深度写错时
    `from repo_root import ...` 不会 ImportError，而是**静默 bind 到宿主检出** —— 那是
    一种会同时骗过所有断言的失效形状，只能在这里显式拦下。

    修前那份模块根本不 import repo_root，此时 bound 为 None 并跳过本检查 —— 让它
    在第 1 条的锚定断言上红，而不是报「没加载到 repo_root」这种指错方向的话。
    """
    saved = sys.modules.pop("repo_root", None)
    try:
        spec = importlib.util.spec_from_file_location(
            "hitl_proposal_under_test", str(checkout / "bin" / "hitl-proposal.py")
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        bound = sys.modules.get("repo_root")
        if bound is not None:
            assert Path(bound.__file__).resolve().is_relative_to(checkout.resolve()), (
                f"被测模块 bind 到了宿主 repo_root: {bound.__file}"
            )
    finally:
        if saved is not None:
            sys.modules["repo_root"] = saved
        else:
            sys.modules.pop("repo_root", None)
    return mod


@pytest.fixture()
def fake_checkout(tmp_path: Path) -> Path:
    return _materialize_checkout(tmp_path / "checkout", with_ledger=True)


@pytest.fixture()
def foreign_cwd(tmp_path: Path) -> Path:
    """一个按构造不含 docs/plans/3y-bet-ledger.yaml 的目录。"""
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    return elsewhere


def test_gate_read_survives_foreign_cwd(fake_checkout, foreign_cwd, monkeypatch):
    """核心判据：进程 CWD 在别处，审批门禁仍按检出根读到 human_gate。修复前必红。"""
    monkeypatch.chdir(foreign_cwd)
    mod = _load_hitl(fake_checkout)
    assert mod.check_human_gate_needed(GATED_ID) is True


def test_loaded_module_binds_the_fixture_checkout(fake_checkout, foreign_cwd, monkeypatch):
    """锚定的直接取证：解析出的台账路径必须落在 fixture 检出，不是宿主检出。

    与第 1 条不共享失效模式 —— 它读的是 resolver 的返回值本身，因此宿主台账
    被误读、或 CWD 恰好等于宿主检出这类情形都会在这里现形。
    """
    monkeypatch.chdir(foreign_cwd)
    mod = _load_hitl(fake_checkout)
    assert Path(mod.__file__).resolve().is_relative_to(fake_checkout.resolve())
    assert mod._ledger_path().resolve() == (fake_checkout / LEDGER_REL).resolve()


def test_ledger_fixture_is_visible_at_all_basenames(fake_checkout):
    """装置自证：台账只在 fixture 检出里，foreign_cwd 里按构造没有。

    修复前后都绿，所以第 1 条的红只能来自锚定，不能来自 fixture 坏。
    """
    assert (fake_checkout / LEDGER_REL).is_file()
    assert not (fake_checkout.parent / "elsewhere" / LEDGER_REL).exists()


def test_gate_read_when_cwd_is_the_checkout(fake_checkout, monkeypatch):
    """对照：CWD == 检出根时同样为真（修复前后都绿，证明 fixture 没坏）。"""
    monkeypatch.chdir(fake_checkout)
    mod = _load_hitl(fake_checkout)
    assert mod.check_human_gate_needed(GATED_ID) is True


def test_gate_read_is_not_a_blanket_true(fake_checkout, foreign_cwd, monkeypatch):
    """反作弊：未声明 human_gate 的 id 与台账里不存在的 id 仍为 False。"""
    monkeypatch.chdir(foreign_cwd)
    mod = _load_hitl(fake_checkout)
    assert mod.check_human_gate_needed(UNGATED_ID) is False
    assert mod.check_human_gate_needed("BET-FAKE-ABSENT") is False


def test_fail_open_semantics_unchanged_when_ledger_absent(tmp_path, foreign_cwd, monkeypatch):
    """语义守恒：检出里真的没有台账 ⇒ 仍然 False 且不抛（ADR-0451 的既有降级行为）。"""
    checkout = _materialize_checkout(tmp_path / "checkout", with_ledger=False)
    monkeypatch.chdir(foreign_cwd)
    mod = _load_hitl(checkout)
    assert mod.check_human_gate_needed(GATED_ID) is False
