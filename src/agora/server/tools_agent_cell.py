"""Agent Cell MCP tools — AGE-v2 动态 Agent Cell 能力暴露."""

from __future__ import annotations
import json
import os
import subprocess
from pathlib import Path
from typing import Any

import structlog
from fastmcp import FastMCP

from agora.server._response import _error, _ok

logger = structlog.get_logger(__name__)


def _resolve_workspace_root() -> str:
    this_file = Path(__file__).resolve()
    default_root = this_file.parent.parent.parent.parent.parent
    return os.environ.get("WORKSPACE_AUDIT_ROOT") or str(default_root)


def _run_cell_tool(script: str, args: list[str]) -> dict[str, Any]:
    """运行 Agent Cell 工具脚本."""
    ws_root = Path(_resolve_workspace_root())
    script_path = ws_root / script
    if not script_path.exists():
        return {"ok": False, "error": f"Script not found: {script}"}
    try:
        proc = subprocess.run(
            ["python3", str(script_path)] + args,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        if proc.returncode != 0:
            return {"ok": False, "error": proc.stderr.strip()[-1000:]}
        try:
            return json.loads(proc.stdout)
        except json.JSONDecodeError:
            return {"ok": True, "text": proc.stdout.strip()[-2000:]}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def register_agent_cell_tools(mcp: FastMCP) -> None:
    """Register Agent Cell MCP tools."""

    @mcp.tool()
    async def cell_plan(intent: str, context: str = "{}") -> dict:
        """Agent Cell Planner — 意图解析 + 任务分解 → 执行计划."""
        try:
            result = _run_cell_tool(
                "projects/omo/src/omo/resident/planner.py",
                ["--intent", intent, "--json"],
            )
            return _ok(result)
        except Exception as e:
            return _error(f"Cell plan failed: {e}")

    @mcp.tool()
    async def cell_execute(plan: str) -> dict:
        """Agent Cell Executor — 按计划执行."""
        try:
            result = _run_cell_tool(
                "projects/omo/src/omo/resident/executor.py", ["--plan", plan, "--json"]
            )
            return _ok(result)
        except Exception as e:
            return _error(f"Cell execute failed: {e}")

    @mcp.tool()
    async def cell_verify(result: str, intent: str = "") -> dict:
        """Agent Cell Verifier — 结果验证 + 质量评估 + 裁决."""
        try:
            args = ["--result", result, "--json"]
            if intent:
                args.extend(["--intent", intent])
            r = _run_cell_tool("projects/omo/src/omo/resident/verifier.py", args)
            return _ok(r)
        except Exception as e:
            return _error(f"Cell verify failed: {e}")

    @mcp.tool()
    async def cell_govern(action: str, target: str = "") -> dict:
        """Agent Cell Governor — 风险分级 + 审批决策."""
        try:
            result = _run_cell_tool(
                "projects/omo/src/omo/resident/governor.py",
                [
                    "--assess",
                    json.dumps({"action": action, "target": target}),
                    "--json",
                ],
            )
            return _ok(result)
        except Exception as e:
            return _error(f"Cell govern failed: {e}")

    @mcp.tool()
    async def cell_pdp_evaluate(action: str, target: str = "") -> dict:
        """PDP 策略决策 — 基于策略评估请求."""
        try:
            result = _run_cell_tool(
                "projects/omo/src/omo/resident/pdp_pep.py",
                ["--check", json.dumps({"action": action, "target": target}), "--json"],
            )
            return _ok(result)
        except Exception as e:
            return _error(f"PDP evaluate failed: {e}")

    @mcp.tool()
    async def cell_pep_enforce(action: str, target: str = "") -> dict:
        """PEP 策略执行 — 执行 PDP 决策, 阻断或放行."""
        try:
            result = _run_cell_tool(
                "projects/omo/src/omo/resident/pdp_pep.py",
                [
                    "--enforce",
                    json.dumps({"action": action, "target": target}),
                    "--json",
                ],
            )
            return _ok(result)
        except Exception as e:
            return _error(f"PEP enforce failed: {e}")

    @mcp.tool()
    async def cell_memory_process(episode: str) -> dict:
        """Agent Cell Memory Pipeline — 从 Episode 生成候选记忆."""
        try:
            result = _run_cell_tool(
                "projects/omo/src/omo/resident/memory_pipeline.py",
                ["--process", episode, "--json"],
            )
            return _ok(result)
        except Exception as e:
            return _error(f"Memory process failed: {e}")

    @mcp.tool()
    async def cell_memory_consolidate() -> dict:
        """Agent Cell Memory Consolidation — 合并相关记忆."""
        try:
            result = _run_cell_tool(
                "projects/omo/src/omo/resident/memory_pipeline.py",
                ["--consolidate", "--json"],
            )
            return _ok(result)
        except Exception as e:
            return _error(f"Memory consolidate failed: {e}")

    @mcp.tool()
    async def cell_replay(episode: str) -> dict:
        """Agent Cell Replay — 历史 Episode 回放."""
        try:
            result = _run_cell_tool(
                "projects/omo/src/omo/resident/replay.py",
                ["--replay", episode, "--json"],
            )
            return _ok(result)
        except Exception as e:
            return _error(f"Cell replay failed: {e}")

    @mcp.tool()
    async def cell_shadow(intent: str) -> dict:
        """Agent Cell Shadow Mode — 影子运行 (无副作用)."""
        try:
            result = _run_cell_tool(
                "projects/omo/src/omo/resident/replay.py",
                ["--shadow", "--intent", intent, "--json"],
            )
            return _ok(result)
        except Exception as e:
            return _error(f"Cell shadow failed: {e}")

    @mcp.tool()
    async def cell_eval(episodes: int = 5) -> dict:
        """Agent Cell Eval — 评估 Cell 性能."""
        try:
            result = _run_cell_tool(
                "projects/omo/src/omo/resident/replay.py",
                ["--eval", "--episodes", str(episodes), "--json"],
            )
            return _ok(result)
        except Exception as e:
            return _error(f"Cell eval failed: {e}")

    @mcp.tool()
    async def cell_pool_status() -> dict:
        """Cell Pool 状态 — 查看多 Cell 并行状态."""
        try:
            result = _run_cell_tool(
                "projects/omo/src/omo/resident/cell_pool.py",
                ["--status", "--json"],
            )
            return _ok(result)
        except Exception as e:
            return _error(f"Cell pool status failed: {e}")

    @mcp.tool()
    async def cell_pool_submit(intent: str) -> dict:
        """Cell Pool 提交 — 提交 Episode 到 Cell Pool."""
        try:
            result = _run_cell_tool(
                "projects/omo/src/omo/resident/cell_pool.py",
                ["--submit", intent, "--json"],
            )
            return _ok(result)
        except Exception as e:
            return _error(f"Cell pool submit failed: {e}")

    @mcp.tool()
    async def cell_pool_scale(target: int) -> dict:
        """Cell Pool 扩缩容 — 调整 Cell 数量."""
        try:
            result = _run_cell_tool(
                "projects/omo/src/omo/resident/cell_pool.py",
                ["--scale", str(target), "--json"],
            )
            return _ok(result)
        except Exception as e:
            return _error(f"Cell pool scale failed: {e}")

    @mcp.tool()
    async def cell_config_list() -> dict:
        """Cell Config 列表 — 列出所有预设配置."""
        try:
            result = _run_cell_tool(
                "projects/omo/src/omo/resident/cell_config.py",
                ["--list", "--json"],
            )
            return _ok(result)
        except Exception as e:
            return _error(f"Cell config list failed: {e}")

    @mcp.tool()
    async def cell_config_create(cell_type: str) -> dict:
        """Cell Config 创建 — 从预设创建 Cell."""
        try:
            result = _run_cell_tool(
                "projects/omo/src/omo/resident/cell_config.py",
                ["--create", cell_type, "--json"],
            )
            return _ok(result)
        except Exception as e:
            return _error(f"Cell config create failed: {e}")
