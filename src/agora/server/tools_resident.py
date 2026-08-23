"""Resident Agent System MCP tools — resident 常驻 Agent 体系 (WP-A~I / ADR-0396).

Exposes resident runtime status and role configuration through Agora MCP:
- resident_status — 运行状态快照 (daemon/events/sediment/alert/ledger)
- resident_roles — 五类角色配置 (sediment/decision/execute/monitor/heartbeat)

Implementation delegates to `omo resident status/roles` (SSOT entry point,
see docs/architecture/resident-agent-system-v1.md).
"""

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


def _run_omo_resident(args: list[str]) -> dict[str, Any]:
    """委派到 omo.cli resident（SSOT 入口）。

    Returns parsed JSON payload; on failure returns an error-shaped dict.
    """
    ws_root = Path(_resolve_workspace_root())
    omo_project = ws_root / "projects" / "omo"
    cmd = [
        "uv",
        "run",
        "--directory",
        str(omo_project),
        "python",
        "-W",
        "ignore::DeprecationWarning",
        "-m",
        "omo.cli",
        "resident",
    ] + args
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
    except (subprocess.SubprocessError, OSError) as e:
        logger.exception("resident_exec_error")
        return {"ok": False, "detail": f"resident exec failed: {e}"}
    if proc.returncode != 0:
        return {
            "ok": False,
            "detail": proc.stderr.strip()[-2000:] or proc.stdout.strip()[-2000:],
        }
    try:
        data = json.loads(proc.stdout)
        return data if isinstance(data, dict) else {"ok": True, "payload": data}
    except json.JSONDecodeError:
        return {"ok": True, "text": proc.stdout.strip()[-2000:]}


def register_resident_tools(mcp: FastMCP) -> None:
    """Register resident system MCP tools."""

    @mcp.tool()
    async def resident_status() -> dict:
        """Resident 常驻 Agent 体系运行状态快照。

        返回 daemon (byte_offset 水位活性) / events (事件流规模) / sediment
        (知识沉淀计数) / alert (告警转发水位) / ledger (event-ledger 哈希链完整性)
        五组件 + health (recovered/degraded)。基于 omo resident status。
        """
        try:
            data = _run_omo_resident(["status"])
            return _ok(data)
        except (OSError, ValueError) as e:  # defensive fallback
            logger.exception("resident_status_error")
            return _error(f"Resident status failed: {e}")

    @mcp.tool()
    async def resident_roles() -> dict:
        """Resident 五类常驻角色配置 (M4.3)。

        返回 sediment (记忆沉淀) / decision (大脑决策) / execute (手执行) /
        monitor (眼睛监控) / heartbeat (心脏心跳) 五角色, 各含 projector /
        topic_filter / handler。基于 omo resident roles。
        """
        try:
            data = _run_omo_resident(["roles", "--json"])
            return _ok(data)
        except (OSError, ValueError) as e:  # defensive fallback
            logger.exception("resident_roles_error")
            return _error(f"Resident roles failed: {e}")
