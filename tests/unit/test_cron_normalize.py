"""bin/lib/cron_normalize.py —— crontab 归一化公共口径的用例.

这个模块存在的原因就是**两次静默漂移** (见模块 docstring): 比较键的截断范围、
解释器归一化的范围。用例因此不是「覆盖当前实现」, 而是钉住两种漂移形状本身,
以及那个被两边同形继承下来的末段 off-by-one.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "cron_normalize_under_test", WORKSPACE / "bin" / "lib" / "cron_normalize.py"
)
assert _spec and _spec.loader
cn = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cn)

SENTINEL = Path("/sentinel-home-for-cron-normalize")


def test_interpreter_at_command_start_is_normalized() -> None:
    """命令起始处的绝对路径解释器归一化成裸 `python3`。

    安装态写 `/opt/homebrew/bin/python3.13` 而登记面写 `python3` —— 语义相同,
    不该算 drift (2026-10-22 有 4 条 cron 因解释器写法分裂连续失败数周)。
    """
    assert (
        cn.normalize_interpreter("/opt/homebrew/bin/python3.13 bin/x.py") == "python3 bin/x.py"
    )
    assert (
        cn.normalize_interpreter("cd /x && /opt/homebrew/bin/python3.13 bin/y.py")
        == "cd /x && python3 bin/y.py"
    )


def test_segmentation_preserves_shell_operators() -> None:
    r"""分段替换不得让正则前缀跨越 shell 元字符把运算符吃掉。

    全局替换下 `&&/opt/homebrew/bin/python3.13` 会被吃成 `python3` (`\S*/`
    跨越了 `&&`); 分段后运算符保留。这是分段实现**唯一**的实质收益。
    """
    assert (
        cn.normalize_interpreter("&&/opt/homebrew/bin/python3.13") == "&&python3"
    )
    assert cn.normalize_interpreter("x;/usr/bin/python3") == "x;python3"


def test_argument_token_is_still_normalized() -> None:
    """分段不挡参数误伤 —— `--flag=python3.13` 照样被归一化。

    写这条是为了**钉住 docstring 的边界**: 别以为分段能阻止参数里的
    `python3.x` 被改 (那是正则的固有边界, 不是分段的功劳)。
    """
    assert cn.normalize_interpreter("cmd --flag=python3.13 arg") == "cmd --flag=python3 arg"


def test_trailing_command_segment_is_normalized() -> None:
    """行尾的执行段也要归一化 (末段 off-by-one)。

    旧实现只处理到最后一个边界为止, 把 `cmd[last:]` 原样追加 ⇒ `&& python3.13`
    在行尾时永远不被归一化: 登记面写 `&& python3`、安装态写
    `&& /opt/homebrew/bin/python3.13` 会报**假 drift** —— 正是本函数存在的目的。
    两份生产副本与一份测试本地副本曾同形继承这个 off-by-one。
    """
    assert cn.normalize_interpreter("cd /x && python3.13") == "cd /x && python3"
    assert (
        cn.normalize_interpreter("cd /x && /opt/homebrew/bin/python3.13")
        == "cd /x && python3"
    )


def test_comparison_key_is_the_whole_normalized_line() -> None:
    """比较键不得截断: 前 120 字符相同、之后不同的两条行必须不同键。

    这是第一次漂移的形状 (BET-Y2Q4-T10-291 / PR #5106): 截断会让用户自装的
    外部行被误认领, 安装时**被删掉**。
    """
    head = "0 6 * * * cd /some/where && python3 script.py --flag " + "x" * 100
    assert len(head) > 120, "前缀未超 120 字符 —— 本用例失去判别力"
    assert cn.comparison_key(head + "--alpha") != cn.comparison_key(head + "--beta")


def test_comparison_key_skips_blank_and_comment_lines() -> None:
    assert cn.comparison_key("") == ""
    assert cn.comparison_key("   ") == ""
    assert cn.comparison_key("# a comment") == ""
    assert cn.comparison_key("0 6 * * * true") == "0 6 * * * true"


def test_expand_workspace_root_follows_path_home(monkeypatch) -> None:
    """根从 `Path.home()` 派生, 不写字面量 —— 写死本机用户目录换机后必 drift。"""
    monkeypatch.setattr(cn.Path, "home", lambda: SENTINEL)
    assert (
        cn.expand_workspace("cd $HOME/Workspace && python3 x.py")
        == "cd /sentinel-home-for-cron-normalize/Workspace && python3 x.py"
    )
    assert (
        cn.expand_workspace('cd "$HOME/Workspace" && python3 x.py')
        == "cd /sentinel-home-for-cron-normalize/Workspace && python3 x.py"
    )


def test_normalize_installed_line_folds_duplicate_harness_registration(monkeypatch) -> None:
    """`harness-cron.sh` 的重复登记折成规范形, 根同样从 `Path.home()` 派生。

    登记面把同一作业登记两次 (`l4-harness-6h` / `l4-harness-6h-active`),
    已装面也因此有两行 —— 不折叠会被报成 drift/orphan。
    """
    monkeypatch.setattr(cn.Path, "home", lambda: SENTINEL)
    out = cn.normalize_installed_line(
        "0 */6 * * * cd /somewhere && bash projects/l4-kernel/scripts/"
        "harness-cron.sh >> runtime/cron/l4-harness-cron.log 2>&1"
    )
    assert out == (
        "0 */6 * * * cd /sentinel-home-for-cron-normalize/Workspace && bash "
        "projects/l4-kernel/scripts/harness-cron.sh "
        ">> runtime/cron/l4-harness-cron.log 2>&1"
    )
    # 非 harness-cron 行原样返回
    assert cn.normalize_installed_line("0 3 * * * true") == "0 3 * * * true"
