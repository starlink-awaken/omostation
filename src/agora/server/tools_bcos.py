"""BCOS Business Domain MCP tools — 业务闭环系统 (W1~W4).

Exposes BCOS runtime capabilities through Agora MCP:
- bcos_evolve — 进化引擎四阶段 (observe/propose/evaluate/approve, dry-run 默认)
- bcos_signals — 统一信号路由 (W1-D2, doc/meeting/research/code)
- bcos_north_star — 北极星价值度量 v2 (排除 self-data)

Implementation delegates to `bin/bc-os/*.py` (SSOT entry point, see
docs/architecture/bcos-system-v1.md).
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


def _run_bcos(script: str, args: list[str]) -> dict[str, Any]:
    """委派到 bin/bc-os/<script>（SSOT 入口）。

    Returns parsed JSON payload; on failure returns an error-shaped dict.
    """
    ws_root = Path(_resolve_workspace_root())
    script_path = ws_root / "bin" / "bc-os" / script
    cmd = ["python3", str(script_path)] + args
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
    except (subprocess.SubprocessError, OSError) as e:
        logger.exception("bcos_exec_error")
        return {"ok": False, "detail": f"bcos exec failed: {e}"}
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


def register_bcos_tools(mcp: FastMCP) -> None:
    """Register BCOS business domain MCP tools."""

    @mcp.tool()
    async def bcos_evolve() -> dict:
        """BCOS 进化引擎四阶段 (observe/propose/evaluate/approve, dry-run 默认).

        观察 calibration/drift/consumption 数据 → 生成改进提案 → A/B 评估 →
        灰度批准 (受控可回滚)。返回 observed/proposed/evaluated/approved + dry_run。
        基于 bin/bc-os/evolution_engine.py。
        """
        try:
            data = _run_bcos("evolution_engine.py", ["--json"])
            return _ok(data)
        except (OSError, ValueError) as e:  # defensive fallback
            logger.exception("bcos_evolve_error")
            return _error(f"BCOS evolve failed: {e}")

    @mcp.tool()
    async def bcos_signals() -> dict:
        """BCOS 统一信号路由 (W1-D2)。

        扫描 inbox 信号 (公文/会议/调研/代码) 路由到对应业务场景
        (document-review/meeting-supervision/research-pipeline/engineering-delivery/
        knowledge-ingest)。返回 summary (total_routed/by_scene) + routed 列表。
        基于 bin/bc-os/signal_router.py。
        """
        try:
            data = _run_bcos("signal_router.py", ["--json"])
            return _ok(data)
        except (OSError, ValueError) as e:  # defensive fallback
            logger.exception("bcos_signals_error")
            return _error(f"BCOS signals failed: {e}")

    @mcp.tool()
    async def bcos_north_star() -> dict:
        """BCOS 北极星价值度量 v2 (排除 self-data, W3).

        度量真实价值真值 (value truth) / 消费旅程 / 完成率, 生成周报。
        返回价值真值快照 (排除自我消费的数据污染)。基于 bin/bc-os/north_star_meter_v2.py。
        """
        try:
            data = _run_bcos("north_star_meter_v2.py", ["--json"])
            return _ok(data)
        except (OSError, ValueError) as e:  # defensive fallback
            logger.exception("bcos_north_star_error")
            return _error(f"BCOS north star failed: {e}")
