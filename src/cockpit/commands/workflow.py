"""cockpit.commands.workflow — L3 驾驶舱接管 MetaOS 与 ecos 工作流编排 (BET-Y1Q4-T8-13 现代化重构).

用法:
  cockpit workflow                         查看可用工作流与编排引擎状态
  cockpit workflow plan "<任务>"           动态规划 (MetaOS L2)
  cockpit workflow ecos <子命令>            执行 ecos L0 M1 工作流 (list / run / describe / backends / logs)
  cockpit workflow run <yaml>              执行 YAML 定义 (MetaOS L2)
  cockpit workflow history                 查看执行历史
  cockpit workflow approve <id>            批准 RED 门控
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.table import Table

from cockpit.domain.exit_codes import ExitCode

WORKSPACE_ROOT = Path(__file__).resolve().parents[4]
METAOS_DIR = WORKSPACE_ROOT / "projects" / "metaos"
ECOS_DIR = WORKSPACE_ROOT / "projects" / "ecos"
WORKFLOW_CATALOG_PATH = ECOS_DIR / "src" / "ecos" / "ssot" / "registry" / "workflow-catalog.yaml"


def _run_metaos(*args: str) -> int:
    """调用 MetaOS CLI"""
    cmd = [
        "uv",
        "run",
        "--directory",
        str(METAOS_DIR),
        "metaos",
        *args,
    ]
    result = subprocess.run(cmd, check=False)
    return result.returncode


def _run_ecos_workflow(*args: str) -> int:
    """调用 ecos workflow CLI (L0 协议层 M1 工作流引擎)"""
    cmd = [
        "uv",
        "run",
        "--project",
        str(ECOS_DIR),
        "python",
        "-m",
        "ecos.cli.workflow",
        *args,
    ]
    result = subprocess.run(cmd, check=False)
    return result.returncode


def _get_workflow_catalog_summary() -> dict[str, Any]:
    """读取 workflow-catalog.yaml 统计信息 (优雅降级)."""
    if not WORKFLOW_CATALOG_PATH.is_file():
        return {"total": 0, "domains": []}
    try:
        import yaml

        with open(WORKFLOW_CATALOG_PATH, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            domains = list((data.get("domains") or {}).keys())
            total = sum(len(d.get("workflows", [])) for d in (data.get("domains") or {}).values() if isinstance(d, dict))
            return {"total": total, "domains": domains}
    except Exception:
        return {"total": 0, "domains": []}


def handle_workflow(args: list[str] | None = None, ns: Any = None) -> int:
    """Cockpit workflow 子命令分发器 (支持结构化纯净 JSON 与 --dry-run 预检)."""
    args = list(args or [])
    is_json = getattr(ns, "json", False) or "--json" in args
    is_dry_run = getattr(ns, "dry_run", False) or "--dry-run" in args
    console = Console()

    # 过滤掉全局控制 flags
    filtered_args = [a for a in args if a not in ("--json", "--dry-run", "-q", "--quiet", "-v", "--verbose")]

    if not filtered_args or filtered_args[0] in ("-h", "--help", "help"):
        summary = _get_workflow_catalog_summary()
        if is_json:
            payload: dict[str, Any] = {
                "status": "ok",
                "engines": [
                    {"name": "MetaOS L2", "type": "Dynamic Planning", "status": "active"},
                    {"name": "ecos L0 M1", "type": "Protocol Engine", "status": "active"},
                ],
                "registered_workflows_count": summary["total"],
                "workflow_domains": summary["domains"],
                "available_subcommands": ["plan", "run", "history", "approve", "ecos", "mesh"],
                "ready": True,
            }
            if is_dry_run:
                payload["dry_run"] = True
            print(json.dumps(payload, ensure_ascii=False, indent=2))
            return int(ExitCode.SUCCESS)

        console.print("[bold cyan]🧠 MetaOS / L0 工作流编排驾驶舱[/bold cyan]")
        if is_dry_run:
            console.print("[yellow][DRY-RUN 模式][/yellow]")

        table = Table(title="编排引擎矩阵", border_style="cyan")
        table.add_column("引擎 (Engine)", style="bold cyan")
        table.add_column("分层 (Layer)", style="white")
        table.add_column("能力说明 (Capabilities)", style="dim")
        table.add_column("典型命令 (Example)", style="green")

        table.add_row("MetaOS", "L2 动态规划", "自然语言转 DAG / 审批门控 / 执行历史", 'cockpit workflow plan "目标"')
        table.add_row("ecos M1", "L0 协议引擎", f"契约状态机执行 ({summary['total']} 个注册工作流)", "cockpit workflow ecos list")
        table.add_row("Mesh", "L1 算力漫游", "分布式工作流与节点调度", "cockpit workflow mesh")
        console.print(table)

        console.print("\n[dim]💡 提示: 运行 [cyan]cockpit workflow --json[/cyan] 可输出机器友好的引擎规范状态。[/dim]")
        return int(ExitCode.SUCCESS)

    action = filtered_args[0]
    rest = filtered_args[1:]

    if action == "ecos":
        if is_dry_run and not rest:
            if is_json:
                print(json.dumps({"dry_run": True, "action": "ecos", "ready": True}))
            else:
                console.print("[yellow][DRY-RUN][/] 预检: ecos L0 M1 工作流引擎接口就绪。")
            return int(ExitCode.SUCCESS)
        return _run_ecos_workflow(*rest)

    if action == "plan":
        if not rest:
            err_msg = '用法: cockpit workflow plan "<任务描述>" [--dry-run] [--no-llm] [--save <file>]'
            if is_json:
                print(json.dumps({"ok": False, "error": err_msg, "exit_code": int(ExitCode.USAGE_ERROR)}))
            else:
                console.print(f"[red]❌ {err_msg}[/]")
            return int(ExitCode.USAGE_ERROR)
        if is_dry_run and "--dry-run" not in rest:
            rest.append("--dry-run")
        return _run_metaos("plan", *rest)

    elif action == "run":
        if not rest:
            err_msg = "用法: cockpit workflow run <yaml_file>"
            if is_json:
                print(json.dumps({"ok": False, "error": err_msg, "exit_code": int(ExitCode.USAGE_ERROR)}))
            else:
                console.print(f"[red]❌ {err_msg}[/]")
            return int(ExitCode.USAGE_ERROR)
        return _run_metaos("run", *rest)

    elif action == "history":
        return _run_metaos("history", *rest)

    elif action == "approve":
        if not rest:
            err_msg = "用法: cockpit workflow approve <workflow_id>"
            if is_json:
                print(json.dumps({"ok": False, "error": err_msg, "exit_code": int(ExitCode.USAGE_ERROR)}))
            else:
                console.print(f"[red]❌ {err_msg}[/]")
            return int(ExitCode.USAGE_ERROR)
        return _run_metaos("approve", *rest)

    else:
        err_msg = f"未知操作: {action} (可选: plan, run, history, approve, ecos, mesh)"
        if is_json:
            print(json.dumps({"ok": False, "error": err_msg, "exit_code": int(ExitCode.USAGE_ERROR)}))
        else:
            console.print(f"[red]❌ {err_msg}[/]")
        return int(ExitCode.USAGE_ERROR)
