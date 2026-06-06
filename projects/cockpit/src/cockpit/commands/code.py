"""cockpit.commands.code — 代码与代码库分析工具链集成。"""

import argparse
import subprocess
import sys
from pathlib import Path

from cockpit.commands.base import _get_console as get_console

def cmd_code_workflow(args: argparse.Namespace) -> int:
    """执行代码分析高级工作流。"""
    console = get_console()
    workflow_cmd = args.workflow_command
    if not workflow_cmd:
        console.print("[red]请指定具体的工作流，如 impact 或 onboarding。[/red]")
        return 1
        
    kairon_path = Path("projects/kairon")
    if not kairon_path.exists():
        console.print("[red]未找到 kairon 项目目录，无法调用 codeanalyze。[/red]")
        return 1

    cmd = ["uv", "run", "--package", "codeanalyze", "codeanalyze", "workflow", workflow_cmd]
    if getattr(args, "symbol", None):
        cmd.extend([args.symbol])
    
    console.print(f"[cyan]🚀 执行工作流: {' '.join(cmd)}[/cyan]")
    try:
        subprocess.run(cmd, cwd=kairon_path, check=True)
    except subprocess.CalledProcessError as e:
        console.print(f"[red]❌ 工作流执行失败 (exit code: {e.returncode})[/red]")
        return e.returncode
        
    return 0

def cmd_code_base(args: argparse.Namespace) -> int:
    """执行基础代码分析工具。"""
    console = get_console()
    tool_cmd = args.code_command
    if not tool_cmd:
        console.print("[red]请指定具体的代码分析命令。[/red]")
        return 1
        
    kairon_path = Path("projects/kairon")
    if not kairon_path.exists():
        console.print("[red]未找到 kairon 项目目录，无法调用 codeanalyze。[/red]")
        return 1

    cmd = ["uv", "run", "--package", "codeanalyze", "codeanalyze", tool_cmd]
    if getattr(args, "query", None):
        cmd.extend([args.query])
        
    console.print(f"[cyan]🚀 执行分析: {' '.join(cmd)}[/cyan]")
    try:
        subprocess.run(cmd, cwd=kairon_path, check=True)
    except subprocess.CalledProcessError as e:
        console.print(f"[red]❌ 分析执行失败 (exit code: {e.returncode})[/red]")
        return e.returncode
        
    return 0
