"""Cockpit entrypoint for AGE-v2 Dynamic Agent Cell.

Exposes Cell capabilities through Cockpit CLI:
- cell plan: 意图解析 + 任务分解
- cell execute: 计划执行
- cell verify: 结果验证
- cell govern: 风险分级
- cell pdp / pep: 策略决策/执行
- cell memory: 记忆整合
- cell replay: 回放/影子/Eval
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[5]
CELL_SCRIPTS = WORKSPACE / "projects/omo/src/omo/resident"


def _run(script: str, args: list[str]) -> int:
    """运行 Cell 脚本."""
    return subprocess.call(["python3", str(CELL_SCRIPTS / script)] + args, cwd=str(WORKSPACE))


def cmd_cell(args) -> int:
    """Agent Cell 统一入口."""
    cell_args = getattr(args, "cell_args", None)
    if not cell_args:
        print("Usage: cockpit cell <plan|execute|verify|govern|pdp|pep|memory|replay> [args]")
        print("")
        print("Commands:")
        print("  plan <intent>           — 生成执行计划")
        print("  execute <plan_json>     — 执行计划")
        print("  verify <result_json>    — 验证结果")
        print("  govern <action>         — 风险评估")
        print("  pdp <action>            — 策略决策")
        print("  pep <action>            — 策略执行 (阻断/放行)")
        print("  memory process <episode> — 记忆处理")
        print("  memory consolidate      — 记忆整合")
        print("  replay shadow <intent>  — 影子运行")
        print("  replay eval [N]         — 评估性能")
        return 0

    subcmd = cell_args[0]
    rest = cell_args[1:]

    if subcmd == "plan":
        return _run("planner.py", ["--intent", " ".join(rest), "--json"])
    elif subcmd == "execute":
        return _run("executor.py", ["--plan", " ".join(rest), "--json"])
    elif subcmd == "verify":
        return _run("verifier.py", ["--result", " ".join(rest), "--json"])
    elif subcmd == "govern":
        req = json.dumps({"action": rest[0] if rest else "", "target": rest[1] if len(rest) > 1 else ""})
        return _run("governor.py", ["--assess", req, "--json"])
    elif subcmd == "pdp":
        req = json.dumps({"action": rest[0] if rest else "", "target": rest[1] if len(rest) > 1 else ""})
        return _run("pdp_pep.py", ["--check", req, "--json"])
    elif subcmd == "pep":
        req = json.dumps({"action": rest[0] if rest else "", "target": rest[1] if len(rest) > 1 else ""})
        return _run("pdp_pep.py", ["--enforce", req, "--json"])
    elif subcmd == "memory":
        if not rest:
            print("Usage: cockpit cell memory <process|consolidate> [json]")
            return 1
        if rest[0] == "process":
            return _run("memory_pipeline.py", ["--process", " ".join(rest[1:]), "--json"])
        elif rest[0] == "consolidate":
            return _run("memory_pipeline.py", ["--consolidate", "--json"])
        else:
            print(f"Unknown memory subcommand: {rest[0]}")
            return 1
    elif subcmd == "replay":
        if not rest:
            print("Usage: cockpit cell replay <shadow|eval> [args]")
            return 1
        if rest[0] == "shadow":
            return _run("replay.py", ["--shadow", "--intent", " ".join(rest[1:]), "--json"])
        elif rest[0] == "eval":
            n = rest[1] if len(rest) > 1 else "5"
            return _run("replay.py", ["--eval", "--episodes", n, "--json"])
        else:
            print(f"Unknown replay subcommand: {rest[0]}")
            return 1
    else:
        print(f"Unknown cell command: {subcmd}")
        return 1
