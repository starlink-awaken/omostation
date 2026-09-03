"""cockpit.commands.delegation — 薄委派命令统一注册与执行 (Phase A1 基建).

模式 (ADR 待补: 薄委派 + help 透传):
  · 壳 parser ``add_help=False`` → ``--help``/``-h`` 落入 REMAINDER 原样透传给下游 CLI
  · 空参回退: REMAINDER 为空时追加 ``["--help"]`` → 裸 ``cockpit <cmd>`` 也显示下游帮助
  · catalog 自动派生: DelegatedSpec 即唯一手写源, CommandMeta 由 spec 表生成并入
    COMMAND_CATALOG (register_all 时合并), 避免双源漂移

B 组挂载点 (预声明, 各组只建自己的模块, 零共享文件冲突):
  · commands/gac_group.py    (nested: gac <sub>, 自带 register())
  · commands/adr_group.py    (flat: SPECS)
  · commands/sweep_group.py  (flat: SPECS)
  · commands/project_cli.py  (flat: SPECS)
  · commands/root_bin.py     (flat: SPECS)

组模块契约:
  · flat 组: 暴露 ``SPECS: list[DelegatedSpec]``
  · nested 组: 暴露 ``register(sub, workspace_parser) -> dict[str, handler]``
    与 ``CATALOG_EXTRA: dict[str, CommandMeta]``
"""

from __future__ import annotations

import argparse
import importlib
import os
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from cockpit.commands.registry import CATEGORY_GROUPS, CommandMeta

# workspace 根: delegation.py → [0]commands → [1]cockpit(包) → [2]src → [3]cockpit(项目) → [4]projects → [5]workspace
_WS_ROOT = Path(__file__).resolve().parents[5]

# 预声明的 B 组模块 (存在才注册, 允许分批落地)
GROUP_MODULES: tuple[str, ...] = (
    "cockpit.commands.gac_group",
    "cockpit.commands.adr_group",
    "cockpit.commands.sweep_group",
    "cockpit.commands.project_cli",
    "cockpit.commands.root_bin",
)


@dataclass(frozen=True)
class DelegatedSpec:
    """薄委派命令声明 (唯一手写源, catalog/handler/parser 均由此派生)."""

    name: str  # cockpit 命令名, kebab-case 小写 (测试 regex 约束)
    summary: str
    category: str
    target: tuple[str, ...]  # 前缀 argv, 支持 "<ws>" 占位符
    arg_attr: str  # REMAINDER dest, 如 "gac_drift_args" (组内需唯一)
    example: str = ""
    owner: str = "cockpit"
    maturity: str = "beta"  # stable | beta | experimental | deprecated
    risk: str = "low"  # low | medium | high
    aliases: tuple[str, ...] = ()


def workspace_root() -> Path:
    return _WS_ROOT


def resolve_target(argv: tuple[str, ...]) -> list[str]:
    """把 target 中的 '<ws>' / '<ws>/...' 占位符替换为 workspace 根绝对路径."""
    root = str(_WS_ROOT)
    out: list[str] = []
    for a in argv:
        if a == "<ws>":
            out.append(root)
        elif a.startswith("<ws>/"):
            out.append(root + a[4:])
        else:
            out.append(a)
    return out


def clean_env() -> dict[str, str]:
    """清 VIRTUAL_ENV/PYTHONHOME, 防子进程 uv venv 冲突 (同 cli.py dispatch_panorama)."""
    return {k: v for k, v in os.environ.items() if not k.startswith("VIRTUAL_ENV") and k != "PYTHONHOME"}


def make_handler(spec: DelegatedSpec) -> Callable[[argparse.Namespace], int]:
    """生成薄委派 handler: 空参回退 --help + subprocess 原样透传."""

    def handler(ns: argparse.Namespace) -> int:
        passthrough = list(getattr(ns, spec.arg_attr, []) or []) or ["--help"]
        return subprocess.call(resolve_target(spec.target) + passthrough, env=clean_env())

    handler.__name__ = f"cmd_{spec.name.replace('-', '_')}"
    handler.__doc__ = f"薄委派 → {' '.join(spec.target)}"
    return handler


def spec_to_meta(spec: DelegatedSpec) -> CommandMeta:
    """DelegatedSpec → CommandMeta (catalog 派生, 不重复手写)."""
    return CommandMeta(
        name=spec.name,
        summary=spec.summary,
        category=spec.category,
        aliases=spec.aliases,
        example=spec.example,
        owner=spec.owner,
        maturity=spec.maturity,
        risk=spec.risk,
        delegated_target=" ".join(spec.target),
        chain_enabled=spec.risk != "high",  # high-risk 命令默认禁止进入 chain 编排
    )


def add_delegation_parser(
    sub: argparse._SubParsersAction,
    spec: DelegatedSpec,
    workspace_parser: type[argparse.ArgumentParser] | None = None,
) -> None:
    """注册单个薄委派 parser (add_help=False 是 --help 透传的关键).

    注意: parser_class 由父级 ``add_subparsers(parser_class=...)`` 继承,
    不能也不需要传给 ``add_parser`` (那是 add_subparsers 的参数, 传了会 TypeError)。
    workspace_parser 参数保留仅为兼容调用方签名, 不再使用。
    """
    kwargs: dict = dict(
        help=spec.summary,
        add_help=False,
        description=f"薄委派 → {' '.join(spec.target)}\n参数原样透传给下游; 不带参数时显示下游 --help。",
        epilog=f"示例: cockpit {spec.name} {spec.example}".rstrip() if spec.example else None,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p = sub.add_parser(spec.name, **kwargs)
    p.add_argument(
        spec.arg_attr,
        nargs=argparse.REMAINDER,
        help="透传给下游 CLI 的参数 (空 = 显示下游 --help)",
    )


# ── 存量 REMAINDER 委派命令的空参回退 (Phase A1) ──────────────────────────────
# cli.py main() 在 parse_known_args 之后统一调用 inject_empty_help(args):
# 这些命令的 REMAINDER 为空时注入 ["--help"], 使裸命令也显示下游真实帮助.

EXISTING_REMAINDER_DELEGATIONS: dict[str, str] = {
    "omo": "omo_args",
    "resident": "resident_args",
    "bcos": "bcos_args",
    "runtime": "runtime_args",
    "mof": "extra",  # mof/ssb 共用 dest "extra"
    "ssb": "extra",
    "agora": "agora_args",
    "gbrain": "gbrain_args",
    "kairon": "kairon_args",
    "agent-workflow": "agent_workflow_args",
    "agent": "agent_args",
    "compass": "compass_args",
    "policy": "policy_args",
}

# 空参回退覆盖表:
#   None      → 不注入 (下游顶层不支持 --help, 注入会制造报错输出; 如 omo 仅子命令级支持)
#   ["..."]   → 注入自定义参数 (默认为 ["--help"])
EMPTY_FALLBACK_OVERRIDES: dict[str, list[str] | None] = {
    "omo": None,  # omo CLI 顶层无 --help (子命令级才有), 裸 cockpit omo 保持原行为
    "resident": None,  # 委派 omo resident, 同 omo
}

# ── 壳层帮助接管 (Phase: help-passthrough 修复) ─────────────────────────────
# 下游 CLI 顶层不支持 --help 的委派命令: ``cockpit <cmd> --help`` / 裸命令
# 不再 spawn 子进程 (下游会报错/输出版本号/dry-run), 改为壳层直接打印用法引导。
SHELL_HELP: dict[str, str] = {
    "kairon": (
        "用法: cockpit kairon <package> <sub> [args...]\n"
        "示例: cockpit kairon codeanalyze status\n"
        "说明: kairon 是知识引擎 monorepo 聚合入口, 顶层不接受 --help。\n"
        "完整帮助: uv run --project projects/knowledge/kairon kairon --help"
    ),
    "gbrain": (
        "用法: cockpit gbrain <sub> [args...]\n"
        "子命令: search / import / stats\n"
        "示例: cockpit gbrain search \"关键词\""
    ),
    "l4-kernel": (
        "用法: cockpit l4-kernel <sub> [args...]\n"
        "说明: L4 自我层管理面 (委派 projects/l4-kernel CLI)。"
    ),
    "bcos": (
        "用法: cockpit bcos <sub> [args...]\n"
        "子命令: evolve / signals / north-star\n"
        "示例: cockpit bcos evolve --dry-run · cockpit bcos north-star"
    ),
    "mof": (
        "用法: cockpit mof <sub> [args...]\n"
        "说明: mof 独立 CLI 已弃用, 日常请使用 cockpit 替代命令\n"
        "      (cockpit mof-contract-lint / cockpit mof-contract-agent)。"
    ),
    "runtime": (
        "用法: cockpit runtime <sub> [args...]\n"
        "说明: 委派 runtime 项目 CLI (projects/runtime)。"
    ),
    "omo": (
        "用法: cockpit omo <sub> [args...]\n"
        "说明: OMO Agent OS CLI (治理/任务/证据面)。omo 顶层不支持 --help,\n"
        "      子命令级帮助: cockpit omo <sub> --help。"
    ),
    "resident": (
        "用法: cockpit resident <sub> [args...]\n"
        "子命令: status / roles / daemon 等 (委派 omo resident)。"
    ),
    "ssb": (
        "用法: cockpit ssb <sub> [options]\n"
        "子命令: publish / query / state / recover / events / stats\n"
        "(委派 ssb-client, 下游 --help 返回码非 0 故由壳层接管)。"
    ),
}

# 仅拦截显式 --help/-h、空参保持原行为的命令 (omo/resident 空参委派下游是既有约定)
SHELL_HELP_HELP_ONLY: frozenset[str] = frozenset({"omo", "resident", "ssb"})

_HELP_MARKER = ("--help", "-h")


def shell_help_if_requested(args: argparse.Namespace) -> int | None:
    """下游不支持 --help 的委派命令: --help/空参 → 壳层帮助 (不 spawn 子进程).

    返回 0 表示已输出帮助 (调用方直接 return); 返回 None 表示继续正常分发。
    SHELL_HELP_HELP_ONLY 内命令仅拦截显式 --help/-h (空参保持既有委派行为)。
    """
    cmd = getattr(args, "command", "")
    text = SHELL_HELP.get(cmd)
    if text is None:
        return None
    attr = EXISTING_REMAINDER_DELEGATIONS.get(cmd)
    if attr is None:
        return None
    passthrough = list(getattr(args, attr, []) or [])
    if passthrough and passthrough[0] in _HELP_MARKER:
        print(text)
        return 0
    if not passthrough and cmd not in SHELL_HELP_HELP_ONLY:
        print(text)
        return 0
    return None


def inject_empty_help(args: argparse.Namespace) -> None:
    """空 REMAINDER → 注入 --help (在 cli.py 分发前调用一次).

    EMPTY_FALLBACK_OVERRIDES[cmd] 为 None 时不注入; 为 list 时注入该参数。
    """
    cmd = getattr(args, "command", "")
    attr = EXISTING_REMAINDER_DELEGATIONS.get(cmd)
    if attr is None or list(getattr(args, attr, []) or []):
        return
    fallback = EMPTY_FALLBACK_OVERRIDES.get(cmd, ["--help"])
    if fallback is None:
        return
    setattr(args, attr, list(fallback))


def reclaim_unknown_for_delegation(args: argparse.Namespace, unknown: list[str]) -> list[str]:
    """argparse REMAINDER 不捕获前导 option (如 ``cmd --help`` 的 --help 落入 unknown).

    对委派命令, 把 unknown 拼回其 REMAINDER attr, 使 ``cockpit <cmd> --help``
    真正透传下游。非委派命令原样返回 unknown (保持现状)。
    """
    cmd = getattr(args, "command", "")
    attr = EXISTING_REMAINDER_DELEGATIONS.get(cmd)
    if attr is None or not unknown:
        return unknown
    existing = list(getattr(args, attr, []) or [])
    setattr(args, attr, existing + list(unknown))
    return []


# ── B 组注册聚合 ──────────────────────────────────────────────────────────────

DELEGATED_COMMANDS: dict[str, Callable[[argparse.Namespace], int]] = {}


def register_all(
    sub: argparse._SubParsersAction,
    workspace_parser: type[argparse.ArgumentParser],
) -> dict[str, Callable[[argparse.Namespace], int]]:
    """发现并注册全部 B 组薄委派命令; 返回 handlers (供 cli.py handlers.update)."""
    handlers: dict[str, Callable[[argparse.Namespace], int]] = {}
    for mod_name in GROUP_MODULES:
        try:
            mod = importlib.import_module(mod_name)
        except ImportError:
            continue  # 组模块尚未落地 (分批实施), 静默跳过
        specs: list[DelegatedSpec] = list(getattr(mod, "SPECS", []))
        for spec in specs:
            add_delegation_parser(sub, spec, workspace_parser)
            handlers[spec.name] = make_handler(spec)
            # 登记 REMAINDER attr, 供 main() 回收前导 --help 等 unknown options
            EXISTING_REMAINDER_DELEGATIONS.setdefault(spec.name, spec.arg_attr)
        custom: Callable[..., dict[str, Callable[[argparse.Namespace], int]]] | None = getattr(
            mod, "register", None
        )
        if callable(custom):
            handlers.update(custom(sub, workspace_parser))
    DELEGATED_COMMANDS.clear()
    DELEGATED_COMMANDS.update(handlers)
    return handlers


def ensure_delegated_catalog() -> dict[str, CommandMeta]:
    """把全部组模块的 CommandMeta (flat SPECS 派生 + nested CATALOG_EXTRA) 并入 COMMAND_CATALOG.

    供 register_all 与测试调用; 幂等.
    """
    from cockpit.commands.registry import COMMAND_CATALOG

    merged: dict[str, CommandMeta] = {}
    for mod_name in GROUP_MODULES:
        try:
            mod = importlib.import_module(mod_name)
        except ImportError:
            continue
        for spec in getattr(mod, "SPECS", []):
            merged[spec.name] = spec_to_meta(spec)
        for k, v in getattr(mod, "CATALOG_EXTRA", {}).items():
            merged.setdefault(k, v)
    for k, v in merged.items():
        COMMAND_CATALOG.setdefault(k, v)
    return merged


def category_order(category: str) -> int:
    """help_map 分组排序 (未登记的 category 排最后)."""
    return CATEGORY_GROUPS.get(category, (999, "white"))[0]


def category_color(category: str) -> str:
    return CATEGORY_GROUPS.get(category, (999, "white"))[1]


__all__ = [
    "DelegatedSpec",
    "GROUP_MODULES",
    "DELEGATED_COMMANDS",
    "EXISTING_REMAINDER_DELEGATIONS",
    "EMPTY_FALLBACK_OVERRIDES",
    "workspace_root",
    "resolve_target",
    "clean_env",
    "make_handler",
    "spec_to_meta",
    "add_delegation_parser",
    "inject_empty_help",
    "shell_help_if_requested",
    "SHELL_HELP",
    "SHELL_HELP_HELP_ONLY",
    "register_all",
    "ensure_delegated_catalog",
]
