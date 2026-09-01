"""delegation 基建测试 — Phase A1/B 的不变量.

覆盖:
  · DelegatedSpec 表完整性 (kebab 命名 / arg_attr 可用)
  · 空参回退: REMAINDER 为空 → 注入 --help
  · --help 透传: add_help=False 的子 parser parse_known_args 不触发 SystemExit
  · EXISTING_REMAINDER_DELEGATIONS 覆盖的 attr 在对应命令上真实存在
"""

from __future__ import annotations

import argparse
from unittest.mock import MagicMock, patch

import pytest

from cockpit.commands.delegation import (
    EXISTING_REMAINDER_DELEGATIONS,
    DelegatedSpec,
    add_delegation_parser,
    inject_empty_help,
    make_handler,
    resolve_target,
)


class TestSpecContract:
    def test_kebab_case_names(self):
        spec = DelegatedSpec(
            name="my-cmd",
            summary="s",
            category="🧰 工具集",
            target=("echo",),
            arg_attr="my_cmd_args",
        )
        assert spec.name == "my-cmd"
        assert spec.maturity == "beta"
        assert spec.risk == "low"

    def test_resolve_workspace_placeholder(self):
        resolved = resolve_target(("python3", "<ws>/bin/x.py"))
        assert resolved[0] == "python3"
        assert resolved[1].endswith("/bin/x.py")
        assert "<ws>" not in resolved[1]


class TestEmptyHelpFallback:
    def test_empty_remainder_injects_help(self):
        spec = DelegatedSpec(
            name="demo-cmd",
            summary="s",
            category="🧰 工具集",
            target=("echo",),
            arg_attr="demo_cmd_args",
        )
        handler = make_handler(spec)
        ns = argparse.Namespace(demo_cmd_args=[])
        with patch("cockpit.commands.delegation.subprocess.call", MagicMock(return_value=0)) as call:
            rc = handler(ns)
        assert rc == 0
        argv = call.call_args[0][0]
        assert argv[-1] == "--help", "空 REMAINDER 必须回退注入 --help"

    def test_nonempty_remainder_passthrough_keeps_order(self):
        spec = DelegatedSpec(
            name="demo-cmd",
            summary="s",
            category="🧰 工具集",
            target=("echo",),
            arg_attr="demo_cmd_args",
        )
        handler = make_handler(spec)
        ns = argparse.Namespace(demo_cmd_args=["--help", "--extra"])
        with patch("cockpit.commands.delegation.subprocess.call", MagicMock(return_value=0)) as call:
            handler(ns)
        argv = call.call_args[0][0]
        assert argv == ["echo", "--help", "--extra"], "透传参数必须保序"


class TestHelpPassthroughParser:
    def _build(self) -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser(prog="cockpit-test")
        sub = parser.add_subparsers(dest="command")
        spec = DelegatedSpec(
            name="proxy",
            summary="s",
            category="🧰 工具集",
            target=("echo",),
            arg_attr="proxy_args",
        )
        add_delegation_parser(sub, spec)
        return parser

    def test_help_flag_lands_in_remainder_not_systemexit(self):
        """add_help=False 后 --help 不触发 HelpAction (无 SystemExit);

        argparse REMAINDER 不捕获前导 option → --help 落入 unknown,
        经 reclaim_unknown_for_delegation 拼回 REMAINDER 完成透传 (main() 已接线)。
        """
        from cockpit.commands.delegation import reclaim_unknown_for_delegation

        parser = self._build()
        ns, unknown = parser.parse_known_args(["proxy", "--help"])
        # 未注册 attr 映射的临时 spec 走手动登记路径
        from cockpit.commands.delegation import EXISTING_REMAINDER_DELEGATIONS

        EXISTING_REMAINDER_DELEGATIONS.setdefault("proxy", "proxy_args")
        unknown = reclaim_unknown_for_delegation(ns, unknown)
        assert unknown == []
        assert getattr(ns, "proxy_args") == ["--help"], "前导 --help 须拼回 REMAINDER 实现透传"

    def test_bare_command_empty_remainder(self):
        parser = self._build()
        ns, _ = parser.parse_known_args(["proxy"])
        assert getattr(ns, "proxy_args") == []

    def test_inject_empty_help_targets_known_commands(self):
        ns = argparse.Namespace(command="policy", policy_args=[])
        inject_empty_help(ns)
        assert ns.policy_args == ["--help"]

    def test_inject_empty_help_respects_override_none(self):
        """EMPTY_FALLBACK_OVERRIDES[cmd]=None 的命令 (omo) 不注入 --help."""
        ns = argparse.Namespace(command="omo", omo_args=[])
        inject_empty_help(ns)
        assert ns.omo_args == [], "omo 顶层不支持 --help, 注入反而制造报错输出"

    def test_inject_empty_help_skips_unknown_commands(self):
        ns = argparse.Namespace(command="research", topic=["x"])
        inject_empty_help(ns)
        # research 不在 EXISTING_REMAINDER_DELEGATIONS, 不注入
        assert not hasattr(ns, "omo_args")


class TestExistingDelegationsContract:
    @pytest.mark.parametrize("cmd,attr", sorted(EXISTING_REMAINDER_DELEGATIONS.items()))
    def test_attr_registered_in_source(self, cmd: str, attr: str):
        """EXISTING_REMAINDER_DELEGATIONS 的每个命令必须在注册源有对应 REMAINDER dest.

        Phase B 起 attr 有两个合法来源:
          · 存量命令: _subcommands.py 源码
          · 薄委派组: 组模块 (SPECS.arg_attr / register() 内登记)
        """
        from pathlib import Path

        src_dir = Path(__file__).resolve().parent.parent
        subcommands_src = (src_dir / "_subcommands.py").read_text(encoding="utf-8")
        if f'"{cmd}"' in subcommands_src:
            assert f'"{attr}"' in subcommands_src, f"存量命令 {cmd} 的 REMAINDER dest {attr} 未在 _subcommands.py 注册"
            return
        # Phase B 组模块: 扫描 commands/ 下的组模块源码
        commands_dir = src_dir / "commands"
        group_sources = "\n".join(
            p.read_text(encoding="utf-8")
            for p in commands_dir.glob("*_group.py")
        ) + "\n".join(
            p.read_text(encoding="utf-8")
            for p in (commands_dir / "project_cli.py", commands_dir / "root_bin.py")
            if p.exists()
        )
        assert f'"{cmd}"' in group_sources, f"命令 {cmd} 既不在 _subcommands.py 也不在任何组模块注册"
        assert attr in group_sources, f"命令 {cmd} 的 REMAINDER dest {attr} 未在组模块声明"
