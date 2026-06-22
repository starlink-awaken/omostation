#!/usr/bin/env python3
"""ecos workflow — 工作流 CLI 命令

用法:
    ecos workflow list                    # 列出所有可用工作流
    ecos workflow run <name> [--dry-run]  # 执行工作流
    ecos workflow describe <name>         # 查看工作流定义
    ecos workflow backends                # 查看后端注册状态
    ecos workflow logs [--recent N] [--status ok|failed] [--verbose] [<workflow_id>]
                                          # 工作流运行历史

子命令委派:
    logs/runs → cli.workflow_runs
"""

from __future__ import annotations

import sys
from typing import Any


def main() -> None:
    """CLI 入口"""
    args = sys.argv[1:] if sys.argv[1:] else ["--help"]

    subcmd = args[0] if args else "help"
    subargs = args[1:]

    dispatcher = {
        "list": _cmd_list,
        "ls": _cmd_list,
        "run": _cmd_run,
        "describe": _cmd_describe,
        "cat": _cmd_describe,
        "backends": _cmd_backends,
        "logs": _cmd_logs,
        "runs": _cmd_logs,
        "--help": _cmd_help,
        "-h": _cmd_help,
        "help": _cmd_help,
    }

    cmd = dispatcher.get(subcmd)
    if cmd is None:
        print(f"未知子命令: {subcmd}")
        _cmd_help()
        sys.exit(1)

    cmd(subargs)


# ── 子命令实现 ──


def _cmd_list(_args: list[str]) -> None:
    """ecos workflow list — 列出所有可用工作流"""
    from ecos.workflow import list_workflows

    wfs = list_workflows()
    if not wfs:
        print("没有可用工作流。")
        return

    print(f"📋 可用工作流 ({len(wfs)} 个)")
    print(f"{'=' * 80}")
    for wf in wfs:
        src = "📄" if wf.get("source") == "definition" else "📌"
        name = wf.get("name", "?")
        display = wf.get("display", name)
        extra = ""
        if wf.get("domain"):
            extra = f"  domain={wf['domain']}"
        if wf.get("layer"):
            extra += f"  layer={wf['layer']}"
        print(f"  {src}  {display:30s}  [{name}]{extra}")
    print(f"{'=' * 80}")


def _cmd_run(args: list[str]) -> None:
    """ecos workflow run <name> — 执行工作流"""
    from ecos.workflow import execute_m1_workflow

    dry_run = "--dry-run" in args or "--dry" in args
    args = [a for a in args if a not in ("--dry-run", "--dry")]

    if not args:
        print("用法: ecos workflow run <name> [--dry-run]")
        sys.exit(1)

    name = args[0]
    print(f"🚀 执行工作流: {name}" + (" (干跑模式)" if dry_run else ""))
    print()

    result = execute_m1_workflow(name, dry_run=dry_run)

    if "error" in result:
        print(f"❌ {result['error']}")
        sys.exit(1)

    _print_result(result)


def _cmd_describe(args: list[str]) -> None:
    """ecos workflow describe <name> — 查看工作流定义"""
    from ecos.workflow import load_workflow

    if not args:
        print("用法: ecos workflow describe <name>")
        sys.exit(1)

    wf = load_workflow(args[0])
    if not wf:
        print(f"工作流不存在: {args[0]}")
        sys.exit(1)

    print(f"📖 工作流: {wf.get('name', args[0])}")
    print(f"  ID: {wf.get('id', '(definition)')}")
    if wf.get("description"):
        print(f"  描述: {wf['description']}")
    if wf.get("domain"):
        print(f"  域: {wf['domain']}")
    if wf.get("layer"):
        print(f"  层: {wf['layer']}")
    if wf.get("bos_uri"):
        print(f"  BOS: {wf['bos_uri']}")
    print()

    execution = wf.get("execution", {})
    has_exec = bool(execution)
    if has_exec:
        print(f"  后端: {execution.get('backend', 'default')}")
        print(f"  模式: {execution.get('mode', 'workflow')}")
        if execution.get("on_failure"):
            print(f"  失败策略: {execution['on_failure']}")
        print()

    steps = wf.get("steps", [])
    if not steps:
        print("  (无步骤定义)")
        return

    print(f"  步骤 ({len(steps)} 步):")
    print(f"  {'─' * 60}")
    for i, step in enumerate(steps, 1):
        name = step.get("name", f"step-{i}")
        action = step.get("action", "?")
        on_fail = step.get("on_failure", "")
        fail_info = f"  [on_failure={on_fail}]" if on_fail else ""
        print(f"    {i:2d}. {name:25s}  {action}{fail_info}")
    print(f"  {'─' * 60}")


def _cmd_backends(_args: list[str]) -> None:
    """ecos workflow backends — 查看后端注册状态"""
    from ecos.workflow import list_backends

    backends = list_backends()
    if not backends:
        print("没有已注册的后端。")
        return

    print(f"🔌 后端注册表 ({len(backends)} 个)")
    print(f"{'=' * 80}")
    for b in backends:
        loaded = "✅" if b.get("loaded") else "💤"
        desc = b.get("description", "")
        print(f"  {loaded}  {b['name']:15s}  {b['module_path']:30s}  {desc}")
    print(f"{'=' * 80}")
    print("💡 workflow 通过 execution.backend 字段选择后端。")


def _cmd_logs(args: list[str]) -> None:
    """ecos workflow logs — 委派到 workflow_runs"""
    from ecos.cli.workflow_runs import cmd_runs

    cmd_runs(args)


def _cmd_help(_args: list[str] | None = None) -> None:
    print("用法: ecos workflow <子命令> [参数]")
    print()
    print("子命令:")
    print("  list                    列出所有可用工作流")
    print("  run <name> [--dry-run]  执行工作流")
    print("  describe <name>         查看工作流定义")
    print("  backends                查看后端注册表")
    print("  logs|runs [选项]        工作流运行历史（同 ecos workflow runs）")
    print()
    print("运行历史选项:")
    print("  --status ok|failed      按状态过滤")
    print("  --recent N              最近 N 条")
    print("  -v, --verbose           显示详细步骤")
    print("  <workflow_id>           查看指定工作流的所有运行")
    print()
    print("示例:")
    print("  ecos workflow list")
    print("  ecos workflow run WORKFLOW-ECOS-DAILY-HEALTH")
    print("  ecos workflow run WORKFLOW-ECOS-DAILY-HEALTH --dry-run")
    print("  ecos workflow describe WORKFLOW-ECOS-DAILY-HEALTH")
    print("  ecos workflow backends")
    print("  ecos workflow logs --recent 5")
    print("  ecos workflow logs --status failed --verbose")


# ── 内部格式化 ──


def _print_result(result: dict[str, Any]) -> None:
    """格式化执行结果"""
    steps = result.get("steps", [])
    passed = result.get("passed", 0)
    failed = result.get("failed", 0)
    total = len(steps)

    violations = result.get("violations", [])
    if violations:
        for v in violations:
            icon = "⚠️" if v.get("severity") == "warning" else "❌"
            print(f"  {icon} {v.get('message', '')}")

    print()
    for step in steps:
        status = step.get("status", "?")
        icon = "✅" if status == "ok" else "❌" if status in ("failed", "error") else "➖"
        name = step.get("name", "?")
        result_text = step.get("result", {}).get("summary", "")
        error = step.get("error", "")
        extra = result_text or error
        print(f"  {icon}  {name:30s}  {extra}" if extra else f"  {icon}  {name}")

    print()
    print(f"  结果: {passed}✅  {failed}❌  (共{total}步)")

    m0 = result.get("m0_snapshot")
    if m0:
        print(f"  M0 快照: {m0}")
    finished = result.get("finished", "")
    if finished:
        print(f"  完成时间: {finished[:19].replace('T', ' ')}")


if __name__ == "__main__":
    main()
