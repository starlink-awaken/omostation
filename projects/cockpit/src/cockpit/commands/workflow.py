"""cockpit workflow command — L3 驾驶舱接管 MetaOS 工作流编排

用法:
  workspace workflow plan "研究 RAG 架构"
  workspace workflow plan "实现缓存层" --dry-run --save my_plan.yaml
  workspace workflow run my_plan.yaml
  workspace workflow history
  workspace workflow history --id <workflow_id>
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def _run_metaos(*args: str) -> int:
    """调用 MetaOS CLI，透传所有参数。"""
    cmd = [
        "uv", "run", "--directory",
        str(Path(__file__).parents[5] / "projects" / "metaos"),
        "metaos",
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

    if action == "plan":
        if not rest:
            print("❌ 用法: workspace workflow plan \"<任务描述>\" [--dry-run] [--no-llm] [--save <file>]")
            return 1
        return _run_metaos("plan", *rest)

    elif action == "run":
        if not rest:
            print("❌ 用法: workspace workflow run <yaml_file>")
            return 1
        return _run_metaos("run", *rest)

    elif action == "history":
        return _run_metaos("history", *rest)

    elif action == "approve":
        if not rest:
            print("❌ 用法: workspace workflow approve <workflow_id>")
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
🧠 MetaOS 工作流编排 (通过 workspace workflow)

用法:
  workspace workflow plan "<任务>"          动态规划并执行工作流
  workspace workflow plan "<任务>" --dry-run  仅生成规划，不执行
  workspace workflow plan "<任务>" --save <文件>  保存规划为 YAML
  workspace workflow run <yaml_file>         执行 YAML 工作流定义
  workspace workflow history                 查看工作流执行历史
  workspace workflow history --id <id>       查看某个工作流详情
  workspace workflow approve <id>            批准 RED 门控等待中的工作流

示例:
  workspace workflow plan "研究 Agent-to-Agent 协议的技术实现"
  workspace workflow plan "实现 Redis 缓存层" --dry-run --save redis_plan.yaml
  workspace workflow run redis_plan.yaml
  workspace workflow history
""")
