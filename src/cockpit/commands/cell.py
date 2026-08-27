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
import os
import subprocess
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[5]
CELL_SCRIPTS = WORKSPACE / "projects/omo/src/omo/resident"


def _run(script: str, args: list[str]) -> int:
    """运行 Cell 脚本."""
    # PYTHONPATH needs to point to the `src` directory so `omo` module can be imported
    src_path = str(CELL_SCRIPTS.parent.parent)  # projects/omo/src
    env = {**os.environ, "PYTHONPATH": src_path}
    return subprocess.call(["python3", str(CELL_SCRIPTS / script)] + args, cwd=str(WORKSPACE), env=env)


def cmd_cell(args) -> int:
    """Agent Cell 统一入口."""
    subcmd = getattr(args, "cell_action", "help")
    cell_args = getattr(args, "cell_args", [])

    if subcmd == "help" or subcmd is None:
        print("Usage: cockpit cell <plan|execute|verify|govern|pdp|pep|memory|replay|dashboard>")
        print("")
        print("Commands:")
        print("  plan <intent>              — 生成执行计划")
        print("  execute <plan_json>        — 执行计划")
        print("  verify <result_json>       — 验证结果")
        print("  govern <action>            — 风险评估 (R0-R3)")
        print("  pdp <action>               — 策略决策评估")
        print("  pep <action>               — 策略执行 (阻断/放行)")
        print("  memory process <episode>   — 记忆处理")
        print("  memory consolidate         — 记忆整合")
        print("  replay shadow <intent>     — 影子运行")
        print("  replay eval [N]            — 评估性能")
        print("  dashboard                  — Cell Pool 监控仪表板")
        return 0

    if subcmd == "plan":
        intent = " ".join(cell_args) if cell_args else ""
        return _run("planner.py", ["--intent", intent, "--json"])
    elif subcmd == "execute":
        plan_json = " ".join(cell_args) if cell_args else "{}"
        return _run("executor.py", ["--plan", plan_json])
    elif subcmd == "verify":
        result_json = " ".join(cell_args) if cell_args else "{}"
        return _run("verifier.py", ["--result", result_json])
    elif subcmd == "govern":
        action = cell_args[0] if cell_args else ""
        target = cell_args[1] if len(cell_args) > 1 else ""
        req = json.dumps({"action": action, "target": target})
        return _run("governor.py", ["--assess", req])
    elif subcmd == "pdp":
        action = cell_args[0] if cell_args else ""
        target = cell_args[1] if len(cell_args) > 1 else ""
        return _run("pdp_pep.py", ["--action", action, "--target", target, "--json"])
    elif subcmd == "pep":
        action = cell_args[0] if cell_args else ""
        target = cell_args[1] if len(cell_args) > 1 else ""
        return _run("pdp_pep.py", ["--action", action, "--target", target, "--enforce", "--json"])
    elif subcmd == "memory":
        if not cell_args:
            print("Usage: cockpit cell memory <process|consolidate> [json]")
            return 1
        mem_action = cell_args[0]
        episode_json = " ".join(cell_args[1:]) if len(cell_args) > 1 else "{}"
        if mem_action == "process":
            return _run("memory_pipeline.py", ["--process", episode_json or "{}"])
        elif mem_action == "consolidate":
            return _run("memory_pipeline.py", ["--consolidate"])
        else:
            print(f"Unknown memory subcommand: {mem_action}")
            return 1
    elif subcmd == "replay":
        if not cell_args:
            print("Usage: cockpit cell replay <shadow|eval> [args]")
            return 1
        rep_action = cell_args[0]
        if rep_action == "shadow":
            intent = " ".join(cell_args[1:]) if len(cell_args) > 1 else ""
            intent_json = json.dumps({"goal": intent}) if intent else "{}"
            return _run("replay.py", ["--shadow", "--intent", intent_json])
        elif rep_action == "eval":
            n = cell_args[1] if len(cell_args) > 1 else "5"
            return _run("replay.py", ["--eval", "--episodes", n])
        else:
            print(f"Unknown replay subcommand: {rep_action}")
            return 1
    elif subcmd == "dashboard":
        from omo.resident.cell_pool import CellPool

        pool = CellPool()
        status = pool.get_pool_status()
        print(json.dumps(status, ensure_ascii=False, indent=2))
        return 0
    else:
        print(f"Unknown cell command: {subcmd}")
        return 1
