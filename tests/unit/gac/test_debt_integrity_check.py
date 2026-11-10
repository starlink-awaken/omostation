"""DEBT-INTEGRITY 的合同测试: debt.yaml::seed_items 与 items 目录的双向一致性。

缺陷背景 (2026-11-09 实锤): 原判据只有**单向** (seed_items → 磁盘存在),
于是「文件存在但未登记」的条目对 ledger 完全不可见 —— `load_debt_ledger`
只遍历 seed_items, 未登记的条目不进 dashboard / metrics / review queue /
action packet, 也没有任何告警。实测 21 个孤儿文件, 其中 7 个 `identified`
(high/medium) + 1 个 `in_progress`, 即「活债务 + 逾期未复审 + 零可见」。

本测试锁住四件事:
1. **反向判据有牙齿**: 从 seed_items 里删掉一条, 必须点名那个孤儿文件并 exit 1;
2. **正向判据仍有牙齿**: 登记一个不存在的文件, 必须点名并 exit 1;
3. **空 seed_items 不被静默放过** (那等于账本整块消失);
4. **对齐状态下常绿**: 真实仓库 exit 0 —— 这条是「检测器没空转」的自证,
   判据在它自己交付的那一刻起必须真的命中过。
"""

from __future__ import annotations

import importlib.util
import io
from contextlib import redirect_stdout
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "bin" / "gac" / "debt-integrity-check.py"


def _load_module(workspace: Path, registry: Path):
    spec = importlib.util.spec_from_file_location("debt_integrity_check", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.WORKSPACE = workspace
    module.DEBT_REGISTRY = registry
    return module


def _run(module) -> tuple[int, str]:
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = module.main()
    return rc, buf.getvalue()


def _make_workspace(tmp_path: Path, item_names: list[str], seed_names: list[str]) -> tuple[Path, Path]:
    """自建最小工作区: .omo/debt/items/*.yaml + .omo/_truth/registry/debt.yaml。"""
    items_dir = tmp_path / ".omo" / "debt" / "items"
    items_dir.mkdir(parents=True, exist_ok=True)
    for name in item_names:
        (items_dir / name).write_text(
            yaml.safe_dump({"id": name.removesuffix(".yaml"), "lifecycle_state": "identified"}),
            encoding="utf-8",
        )
    registry = tmp_path / ".omo" / "_truth" / "registry" / "debt.yaml"
    registry.parent.mkdir(parents=True, exist_ok=True)
    registry.write_text(
        yaml.safe_dump(
            {
                "items_dir": ".omo/debt/items",
                "seed_items": [f".omo/debt/items/{n}" for n in seed_names],
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    return tmp_path, registry


def test_real_repository_is_aligned_and_green() -> None:
    """真实仓库: 两个方向都对齐 —— 检测器没空转的自证。"""
    module = _load_module(ROOT, ROOT / ".omo" / "_truth" / "registry" / "debt.yaml")
    rc, out = _run(module)
    assert rc == 0, out
    assert "every items/*.yaml is registered" in out


def test_reverse_direction_names_the_orphan(tmp_path: Path) -> None:
    """文件在、登记不在 → 必须点名那个孤儿并 exit 1。"""
    workspace, registry = _make_workspace(
        tmp_path,
        item_names=["A.yaml", "B.yaml"],
        seed_names=["A.yaml"],  # B.yaml 故意不登记
    )
    module = _load_module(workspace, registry)
    rc, out = _run(module)
    assert rc == 1
    assert ".omo/debt/items/B.yaml" in out
    assert "not registered" in out
    # 正向方向不得因反向失败而沉默 —— 两条都该报
    assert "registered but absent" not in out  # A 存在, 不该有正向违规


def test_forward_direction_names_the_missing_file(tmp_path: Path) -> None:
    """登记一个不存在的文件 → 必须点名并 exit 1 (原有判据未被削弱)。"""
    workspace, registry = _make_workspace(
        tmp_path,
        item_names=["A.yaml"],
        seed_names=["A.yaml", "GHOST.yaml"],
    )
    module = _load_module(workspace, registry)
    rc, out = _run(module)
    assert rc == 1
    assert ".omo/debt/items/GHOST.yaml" in out
    assert "registered but absent" in out


def test_empty_seed_items_is_rejected(tmp_path: Path) -> None:
    """空 seed_items 不得静默通过 (那等于账本整块消失)。"""
    workspace, registry = _make_workspace(tmp_path, item_names=[], seed_names=[])
    module = _load_module(workspace, registry)
    rc, out = _run(module)
    assert rc == 1
    assert "debt system is empty" in out
