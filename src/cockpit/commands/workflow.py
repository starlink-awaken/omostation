"""cockpit workflow command — L3 驾驶舱接管 MetaOS 与 ecos 工作流编排

用法:
  cockpit workflow plan "<任务>"           动态规划 (MetaOS L2)
  cockpit workflow ecos <子命令>            执行 ecos L0 M1 工作流
  cockpit workflow ecos list               列出 L0 工作流
  cockpit workflow ecos run <name>         执行 L0 工作流
  cockpit workflow ecos describe <name>    查看 L0 工作流定义
  cockpit workflow ecos backends           查看后端注册表
  cockpit workflow ecos logs [选项]        查看运行历史
  cockpit workflow run <yaml>              执行 YAML 定义 (MetaOS L2)
  cockpit workflow history                 查看执行历史
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def _run_metaos(*args: str) -> int:
    """调用 MetaOS CLI"""
    cmd = [
        "uv",
        "run",
        "--directory",
        str(Path(__file__).parents[5] / "projects" / "metaos"),
        "metaos",
        *args,
    ]
    result = subprocess.run(cmd, check=False)
    return result.returncode


def _run_ecos_workflow(*args: str) -> int:
    """调用 ecos workflow CLI (L0 协议层 M1 工作流引擎)"""
    cmd = [
        sys.executable or "python3",
        "-m",
        "ecos.cli.workflow",
        *args,
    ]
    result = subprocess.run(cmd, check=False)
    return result.returncode


def handle_workflow(args):
    """Cockpit workflow 子命令分发器"""
    if not args:
        _print_help()
        return 0

    action = args[0]
    rest = args[1:]

    if action == "ecos":
        return _run_ecos_workflow(*rest)

    if action == "plan":
        if not rest:
            print('❌ 用法: cockpit workflow plan "<任务描述>" [--dry-run] [--no-llm] [--save <file>]')
            return 1
        return _run_metaos("plan", *rest)

    elif action == "run":
        if not rest:
            print("❌ 用法: cockpit workflow run <yaml_file>")
            return 1
        return _run_metaos("run", *rest)

    elif action == "history":
        return _run_metaos("history", *rest)

    elif action == "approve":
        if not rest:
            print("❌ 用法: cockpit workflow approve <workflow_id>")
            return 1
        return _run_metaos("approve", *rest)

    elif action in ("-h", "--help", "help"):
        _print_help()
        return 0

    else:
        print(f"❌ 未知操作: {action}")
        _print_help()
        return 1


def _print_help():
    print("""
🧠 MetaOS / L0 工作流编排 (通过 cockpit workflow)

用法:
  cockpit workflow ecos list               列出 ecos L0 工作流
  cockpit workflow ecos run <name>         执行 ecos L0 工作流
  cockpit workflow ecos describe <name>    查看 L0 工作流定义
  cockpit workflow ecos backends           查看后端注册表
  cockpit workflow ecos logs [选项]        查看运行历史
  cockpit workflow plan "<任务>"           动态规划 (MetaOS L2)
  cockpit workflow run <yaml>              执行 YAML 定义 (MetaOS L2)
  cockpit workflow history                 查看执行历史
  cockpit workflow approve <id>            批准 RED 门控

示例:
  cockpit workflow plan "研究 Agent-to-Agent 协议"
  cockpit workflow ecos list
  cockpit workflow ecos run WORKFLOW-ECOS-DAILY-HEALTH --dry-run
  cockpit workflow ecos logs --recent 5
""")
