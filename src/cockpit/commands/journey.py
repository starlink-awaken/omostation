"""
cockpit.commands.journey — 业务场景旅程 (Journey State Graph) 控制面

封装下游 bin/ssot/journey-runner.py，提供结构化状态检验、执行与预检能力。
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from cockpit.domain.exit_codes import ExitCode
from rich.console import Console

console = Console()


def cmd_journey(args: argparse.Namespace) -> int:
    as_json = getattr(args, "json", False) or getattr(args, "global_output", "text") == "json"
    is_dry_run = getattr(args, "dry_run", False)
    subcmd = getattr(args, "journey_subcommand", None)
    raw_args = list(getattr(args, "journey_args", []))

    ws_root = Path(__file__).resolve().parents[5]
    runner = ws_root / "bin" / "ssot" / "journey-runner.py"

    if not runner.is_file():
        if as_json:
            print(json.dumps({"ok": False, "error": f"journey-runner.py not found at {runner}"}))
        else:
            console.print(f"[red]❌ 找不到 journey-runner 核心执行器: {runner}[/]")
        return ExitCode.RESOURCE_NOT_FOUND

    # 预检模式
    if is_dry_run:
        specs_dir = ws_root / "docs" / "journey-specs"
        specs = list(specs_dir.glob("*.yaml")) if specs_dir.is_dir() else []
        payload = {
            "dry_run": True,
            "runner_exists": runner.is_file(),
            "journey_specs_count": len(specs),
            "journey_specs": [s.name for s in specs],
            "ready": True,
        }
        if as_json:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            console.print(f"[bold cyan]🔍 [Dry-Run] 预检 Journey 状态机环境[/]")
            console.print(f"  • 执行器: [green]就绪[/] ({runner.name})")
            console.print(f"  • 已发现旅程规范: [cyan]{len(specs)}[/] 个")
            for s in specs[:5]:
                console.print(f"    - {s.name}")
            if len(specs) > 5:
                console.print(f"    ... 以及其他 {len(specs) - 5} 个")
        return ExitCode.SUCCESS

    # 组织命令
    cmd = [sys.executable, str(runner)]
    if not subcmd and not raw_args:
        cmd.append("validate")
        if as_json:
            cmd.append("--json")
    elif subcmd:
        cmd.append(subcmd)
        if as_json and "--json" not in raw_args:
            cmd.append("--json")
        cmd.extend(raw_args)
    else:
        cmd.extend(raw_args)
        if as_json and "--json" not in raw_args:
            cmd.append("--json")

    res = subprocess.run(cmd, cwd=str(ws_root), capture_output=as_json, text=True)

    if as_json:
        stdout = res.stdout.strip()
        try:
            parsed = json.loads(stdout)
            print(json.dumps({"ok": res.returncode == 0, "result": parsed}, ensure_ascii=False, indent=2))
        except Exception:
            print(json.dumps({"ok": res.returncode == 0, "raw_output": stdout}, ensure_ascii=False))
        return ExitCode.SUCCESS if res.returncode == 0 else ExitCode.GENERAL_FAILURE

    return res.returncode
