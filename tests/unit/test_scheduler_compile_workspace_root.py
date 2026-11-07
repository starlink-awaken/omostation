"""scheduler-compile 的根必须从 `Path.home()` 派生, 不得写死本机用户目录.

**为什么** (2026-11-07 实证): `_expand_workspace` 曾把 registry 里的 `$HOME/Workspace`
展开成硬编码的 `/Users/<name>/Workspace`。本机看不出来 (Path.home() 恰好等于它),
换机后登记面会**全部指向不存在的路径** ⇒ `check_drift` 永久 drift, 且
`--diff` 的 removed/added 判据随之失真。

同口径参照: `bin/ops/install-cron-plane.py` 的 `_expand_workspace` 与 `_key`
一直用 `Path.home()` —— 两个脚本对同一归一化口径不一致, 换机后必然分叉。

根目录是参数不是事实 (AGENTS.md §1.9): 不写字面量, 从环境派生。
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "scheduler_compile_root", WORKSPACE / "bin" / "scheduler-compile.py"
)
assert _spec and _spec.loader
sc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sc)

SENTINEL = Path("/sentinel-home-for-sc-test")


def test_expand_workspace_root_follows_path_home(monkeypatch) -> None:
    """把 `Path.home()` 换成哨兵 ⇒ 展开结果必须跟着走。

    用哨兵而不是断言「等于本机 home」: 后者在本机恒真, 恰好放过了字面量回归
    (判据与被检对象共享失效模式)。换 home 后才分得清「派生」与「写死」。
    """
    monkeypatch.setattr(sc.Path, "home", lambda: SENTINEL)
    assert (
        sc._expand_workspace("cd $HOME/Workspace && python3 x.py")
        == "cd /sentinel-home-for-sc-test/Workspace && python3 x.py"
    )
    assert (
        sc._expand_workspace('cd "$HOME/Workspace" && python3 x.py')
        == "cd /sentinel-home-for-sc-test/Workspace && python3 x.py"
    )


def test_normalized_installed_line_root_follows_path_home(monkeypatch) -> None:
    """`harness-cron.sh` 折叠特例的根同样从 `Path.home()` 派生。

    这处特例把重复登记的两行折成规范形; 根写死会让换机后折出来的规范形
    与登记面 (从 `$HOME` 展开而来) 对不上, 重复登记重新变成 drift/orphan。
    """
    monkeypatch.setattr(sc.Path, "home", lambda: SENTINEL)
    out = sc._normalize_installed_line(
        "0 */6 * * * cd /somewhere-else && bash projects/l4-kernel/scripts/"
        "harness-cron.sh >> runtime/cron/l4-harness-cron.log 2>&1"
    )
    assert out == (
        "0 */6 * * * cd /sentinel-home-for-sc-test/Workspace && bash "
        "projects/l4-kernel/scripts/harness-cron.sh "
        ">> runtime/cron/l4-harness-cron.log 2>&1"
    )


def test_source_carries_no_hardcoded_home_root() -> None:
    """源码tripwire: 本文件不得再出现本机用户根字面量。

    行为判据证明「派生正确」, 本条挡住「把派生改回字面量」这个具体回归 ——
    它是回归的第一现场, 且不需要换机就能命中。
    """
    src = (WORKSPACE / "bin" / "scheduler-compile.py").read_text(encoding="utf-8")
    home = str(Path.home())
    if len(home) > 1:
        assert home not in src, f"源码写死了本机用户根 {home}; 应从 Path.home() 派生"
