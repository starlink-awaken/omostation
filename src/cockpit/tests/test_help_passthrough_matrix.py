"""help 透传冒烟矩阵 — Phase: help-passthrough 修复验证.

覆盖:
  · SHELL_HELP 壳层帮助接管: bcos/mof/runtime/gbrain/l4-kernel/kairon
    ``--help`` / ``-h`` / 空参 → 壳层输出用法引导, 不 spawn 子进程
  · 真实参数透传不受影响 (passthrough 含非 help 参数时正常委派)
  · 子进程冒烟矩阵 (代表性样本): 真实 CLI --help 退出码 0
"""

from __future__ import annotations

import argparse
import subprocess
import sys

import pytest

from cockpit.commands.delegation import (
    EXISTING_REMAINDER_DELEGATIONS,
    SHELL_HELP,
    SHELL_HELP_HELP_ONLY,
    SHELL_HELP_SHORT_ONLY,
    shell_help_if_requested,
)

# 10 个壳层接管命令
SHELL_HELP_CMDS = sorted(SHELL_HELP.keys())
# 全拦截命令 (空参也接管); 排除 help-only (omo/resident/ssb 空参保持原行为)
# 与 short-only (omlxc 仅拦 -h, --help 透传 Click)
FULL_INTERCEPT_CMDS = sorted(
    set(SHELL_HELP_CMDS) - SHELL_HELP_HELP_ONLY - SHELL_HELP_SHORT_ONLY
)


def _get_attr(cmd: str) -> str:
    """查命令的 REMAINDER attr; B 组命令在单测进程需从 SPECS 派生 (parser 未构建)."""
    if cmd in EXISTING_REMAINDER_DELEGATIONS:
        return EXISTING_REMAINDER_DELEGATIONS[cmd]
    import importlib

    from cockpit.commands.delegation import GROUP_MODULES

    for mod_name in GROUP_MODULES:
        try:
            mod = importlib.import_module(mod_name)
        except ImportError:
            continue
        for spec in getattr(mod, "SPECS", []):
            if spec.name == cmd:
                EXISTING_REMAINDER_DELEGATIONS.setdefault(cmd, spec.arg_attr)
                return spec.arg_attr
    raise KeyError(cmd)


def _make_args(cmd: str, attr: str, passthrough: list[str]) -> argparse.Namespace:
    ns = argparse.Namespace(command=cmd)
    setattr(ns, attr, list(passthrough))
    return ns


class TestShellHelpIntercept:
    """shell_help_if_requested 单元测试 (无子进程)."""

    @pytest.mark.parametrize("cmd", sorted(set(SHELL_HELP_CMDS) - SHELL_HELP_SHORT_ONLY))
    def test_help_flag_shows_shell_help(self, cmd: str, capsys: pytest.CaptureFixture):
        """--help → 壳层帮助, 返回 0 (SHORT_ONLY 的 omlxc 除外, 其 --help 透传 Click)."""
        attr = _get_attr(cmd)
        ns = _make_args(cmd, attr, ["--help"])
        rc = shell_help_if_requested(ns)
        assert rc == 0, f"{cmd} --help 应由壳层接管 (rc=0)"
        out = capsys.readouterr().out
        assert "用法" in out, f"{cmd} 壳层帮助应包含 '用法'"

    @pytest.mark.parametrize("cmd", sorted(SHELL_HELP_SHORT_ONLY))
    def test_short_only_h_intercepted(self, cmd: str, capsys: pytest.CaptureFixture):
        """SHORT_ONLY (omlxc): -h 由壳层接管 (下游 Click 不认 -h)."""
        attr = _get_attr(cmd)
        ns = _make_args(cmd, attr, ["-h"])
        assert shell_help_if_requested(ns) == 0
        assert "用法" in capsys.readouterr().out

    @pytest.mark.parametrize("cmd", sorted(SHELL_HELP_SHORT_ONLY))
    def test_short_only_help_passthrough(self, cmd: str):
        """SHORT_ONLY (omlxc): --help 仍透传下游 Click 完整帮助 (不接管)."""
        attr = _get_attr(cmd)
        ns = _make_args(cmd, attr, ["--help"])
        assert shell_help_if_requested(ns) is None

    @pytest.mark.parametrize("cmd", SHELL_HELP_CMDS)
    def test_h_flag_shows_shell_help(self, cmd: str):
        """-h → 同样接管."""
        attr = _get_attr(cmd)
        ns = _make_args(cmd, attr, ["-h"])
        assert shell_help_if_requested(ns) == 0

    @pytest.mark.parametrize("cmd", FULL_INTERCEPT_CMDS)
    def test_empty_remainder_shows_shell_help(self, cmd: str):
        """空 REMAINDER (裸命令) → 壳层帮助 (全拦截命令)."""
        attr = _get_attr(cmd)
        ns = _make_args(cmd, attr, [])
        assert shell_help_if_requested(ns) == 0

    @pytest.mark.parametrize("cmd", sorted(SHELL_HELP_HELP_ONLY))
    def test_help_only_empty_remainder_not_intercepted(self, cmd: str):
        """help-only 命令 (omo/resident/ssb): 空参保持既有委派行为, 不接管."""
        attr = _get_attr(cmd)
        ns = _make_args(cmd, attr, [])
        assert shell_help_if_requested(ns) is None

    @pytest.mark.parametrize("cmd", SHELL_HELP_CMDS)
    def test_real_args_pass_through(self, cmd: str):
        """真实参数 (非 help) → 不接管, 返回 None (继续正常分发)."""
        attr = _get_attr(cmd)
        ns = _make_args(cmd, attr, ["some-sub", "--flag"])
        assert shell_help_if_requested(ns) is None

    def test_non_shell_help_command_untouched(self):
        """非 SHELL_HELP 命令 (如 compass) → 永不接管 (--help 仍透传下游)."""
        ns = _make_args("compass", "compass_args", ["--help"])
        assert shell_help_if_requested(ns) is None

    def test_unknown_command_untouched(self):
        """未注册命令 → 永不接管."""
        ns = argparse.Namespace(command="not-a-cmd")
        assert shell_help_if_requested(ns) is None


class TestShellHelpContent:
    """壳层帮助文本质量."""

    def test_all_have_usage_line(self):
        """每条帮助文本都含 '用法' 行."""
        for cmd, text in SHELL_HELP.items():
            assert "用法" in text, f"{cmd} 缺少 '用法' 行"

    def test_kairon_mentions_project_help(self):
        """kairon 帮助应指向下游项目级 --help."""
        assert "kairon --help" in SHELL_HELP["kairon"]

    def test_bcos_lists_subcommands(self):
        """bcos 帮助应列出三个子命令."""
        text = SHELL_HELP["bcos"]
        for sub in ("evolve", "signals", "north-star"):
            assert sub in text


# 子进程冒烟矩阵: 代表性样本 (全量 83 命令见 command-audit 评分卡;
# 全量子进程矩阵耗时 ~2min, 此处覆盖每个功能域 + 全部 6 个修复命令)
SMOKE_SAMPLE = [
    # 6 个修复命令 (必须全过)
    *SHELL_HELP_CMDS,
    # 各功能域代表
    "status",
    "health",
    "memory",
    "research",
    "gac",
    "gac coverage",
    "gac readiness",
    "adr-coverage",
    "sweep-ruff",
    "agent",
    "bos",
    "kems",
    "readiness",
]


@pytest.mark.slow
class TestSubprocessSmokeMatrix:
    """真实 CLI 子进程冒烟 (每命令 --help, 退出码 0)."""

    @pytest.mark.parametrize("cmd", SMOKE_SAMPLE)
    def test_help_exit_zero(self, cmd: str):
        result = subprocess.run(
            [sys.executable, "-m", "cockpit", *cmd.split(), "--help"],
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert result.returncode == 0, (
            f"cockpit {cmd} --help 退出码 {result.returncode}\n"
            f"stdout: {result.stdout[:200]}\nstderr: {result.stderr[:200]}"
        )
