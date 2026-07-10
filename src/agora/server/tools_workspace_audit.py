"""Workspace Audit MCP tools — Omostation 6 维度全方位审计 (Round 43 P1).

Provides 6 MCP tools that wrap bin/workspace-audit:
  - workspace_audit_run         跑全维度审计
  - workspace_audit_governance  治理巡检 6 项 (lint / test / debt / adr / task / agora)
  - workspace_audit_lint        .omo/debt/items/ 越权 status 字段
  - workspace_audit_radar       c2g radar 修真 (读 .omo/tasks/ 真数据)
  - workspace_audit_ssot        治理 SSOT 一致性 (CLAUDE.md/AGENTS.md/README.md/INDEX.md)
  - workspace_audit_gitlink     子项目 gitlink 同步
  - workspace_audit_ops         agora 操作审计 (默认 7d)

设计:
  - 调 bin/workspace-audit 子进程, 修真前 MCP 没有这能力, 修真后统一入口
  - 通过环境变量 WORKSPACE_AUDIT_ROOT 传入 workspace 根
  - 返回 _ok({"report": ...}) 或 _error("...") 标准格式
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import structlog
from fastmcp import FastMCP

# 修真 v2: 用 server._response 真实模块 (跟 tools_governance.py 一致)
try:
    from agora.server._response import FORMAT_VERSION, _error, _ok
except ImportError:  # pragma: no cover  - 容错
    from agora.server.response import FORMAT_VERSION, _error, _ok  # type: ignore

logger = structlog.get_logger(__name__)


# ── Path resolution ──
# workspace-audit 期望 WORKSPACE_AUDIT_ROOT 指向 workspace 根, 找不到时回退到
# 自身路径推断 (从 .../agora/src/agora/server/tools_workspace_audit.py 算起)
_THIS_FILE = Path(__file__).resolve()
_DEFAULT_ROOT = _THIS_FILE.parent.parent.parent.parent.parent  # .../Workspace


def _resolve_workspace_root() -> str:
    """从环境变量或路径推断返回 workspace 根."""
    return os.environ.get("WORKSPACE_AUDIT_ROOT") or str(_DEFAULT_ROOT)


def _resolve_audit_script(workspace_root: str) -> Path:
    """找 bin/workspace-audit 脚本绝对路径."""
    return Path(workspace_root) / "bin" / "workspace-audit"


# ── Core runner ──
def _run_audit(
    workspace_root: str,
    dim: str | None = None,
    fmt: str = "json",
    since: str = "7d",
    timeout: int = 60,
) -> dict:
    """调 bin/workspace-audit 子进程, 返 stdout/stderr/returncode 字典."""
    script = _resolve_audit_script(workspace_root)
    if not script.exists():
        return {
            "error": f"找不到 {script}",
            "stdout": "",
            "stderr": "",
            "returncode": -1,
        }

    cmd = [os.environ.get("PYTHON", "python3"), str(script)]
    if dim:
        cmd.extend(["--dim", dim])
    cmd.extend(["--format", fmt])
    cmd.extend(["--since", since])

    try:
        env = os.environ.copy()
        env["WORKSPACE_AUDIT_ROOT"] = workspace_root
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=workspace_root,
            env=env,
        )
        return {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {
            "error": f"workspace-audit 超时 ({timeout}s)",
            "stdout": "",
            "stderr": "",
            "returncode": -1,
        }
    except FileNotFoundError as exc:
        return {"error": str(exc), "stdout": "", "stderr": "", "returncode": -1}


def _parse_report(stdout: str, fmt: str) -> dict | str:
    """按 fmt 解析 stdout 为 dict (json) 或 透传 (markdown)."""
    if fmt == "json":
        try:
            return json.loads(stdout)
        except (json.JSONDecodeError, ValueError):
            return {"raw": stdout}
    return stdout


# ═══════════════════════════════════════════════════════════════
# Tool Registration
# ═══════════════════════════════════════════════════════════════


def register_workspace_audit_tools(mcp: FastMCP) -> None:
    """Register all workspace-audit MCP tools (Round 43 P1 修真)."""

    # ── workspace_audit_run ─────────────────────────────────────

    @mcp.tool()
    def workspace_audit_run(
        dim: str = "all",
        fmt: str = "json",
        since: str = "7d",
    ) -> dict:
        """跑 Omostation 6 维度全方位审计 (修真前无 MCP 入口, 修真后统一工具).

        Args:
            dim:   维度 (all/governance/lint/radar/ssot/gitlink/ops), 默认 all
            fmt:   输出格式 (json/markdown), 默认 json (适合 MCP 消费)
            since: agora ops 维度时间范围, 默认 7d

        Returns 审计报告 (dict) 或 错误信息.
        """
        ws_root = _resolve_workspace_root()
        result = _run_audit(ws_root, dim=dim, fmt=fmt, since=since)
        if "error" in result:
            return _error(result["error"])
        if result["returncode"] != 0:
            return _error(
                f"workspace-audit 退出码 {result['returncode']}: "
                f"{result['stderr'][:500]}"
            )
        return _ok(
            {
                "format_version": FORMAT_VERSION,
                "dim": dim,
                "report": _parse_report(result["stdout"], fmt),
            }
        )

    # ── workspace_audit_governance ──────────────────────────────

    @mcp.tool()
    def workspace_audit_governance() -> dict:
        """跑 omo governance 维度 (治理巡检 6 项). 修真前需手动跑, 修真后 MCP 一键."""
        ws_root = _resolve_workspace_root()
        result = _run_audit(ws_root, dim="governance", fmt="json")
        if "error" in result:
            return _error(result["error"])
        return _ok(
            {
                "format_version": FORMAT_VERSION,
                "report": _parse_report(result["stdout"], "json"),
            }
        )

    # ── workspace_audit_lint ────────────────────────────────────

    @mcp.tool()
    def workspace_audit_lint() -> dict:
        """跑 omo lint yaml-bypass 维度 (.omo/debt/items/ 越权 status 字段检查)."""
        ws_root = _resolve_workspace_root()
        result = _run_audit(ws_root, dim="lint", fmt="json")
        if "error" in result:
            return _error(result["error"])
        return _ok(
            {
                "format_version": FORMAT_VERSION,
                "report": _parse_report(result["stdout"], "json"),
            }
        )

    # ── workspace_audit_radar ───────────────────────────────────

    @mcp.tool()
    def workspace_audit_radar() -> dict:
        """跑 c2g radar 维度 (修真: 读 .omo/tasks/ 真数据, 统计 priority/risk/owner)."""
        ws_root = _resolve_workspace_root()
        result = _run_audit(ws_root, dim="radar", fmt="json")
        if "error" in result:
            return _error(result["error"])
        return _ok(
            {
                "format_version": FORMAT_VERSION,
                "report": _parse_report(result["stdout"], "json"),
            }
        )

    # ── workspace_audit_ssot ────────────────────────────────────

    @mcp.tool()
    def workspace_audit_ssot() -> dict:
        """跑治理 SSOT 一致性维度 (CLAUDE.md/AGENTS.md/README.md/INDEX.md mtime + 关键字)."""
        ws_root = _resolve_workspace_root()
        result = _run_audit(ws_root, dim="ssot", fmt="json")
        if "error" in result:
            return _error(result["error"])
        return _ok(
            {
                "format_version": FORMAT_VERSION,
                "report": _parse_report(result["stdout"], "json"),
            }
        )

    # ── workspace_audit_gitlink ─────────────────────────────────

    @mcp.tool()
    def workspace_audit_gitlink() -> dict:
        """跑子项目 gitlink 同步维度 (submodule ahead/behind vs origin)."""
        ws_root = _resolve_workspace_root()
        result = _run_audit(ws_root, dim="gitlink", fmt="json")
        if "error" in result:
            return _error(result["error"])
        return _ok(
            {
                "format_version": FORMAT_VERSION,
                "report": _parse_report(result["stdout"], "json"),
            }
        )

    # ── workspace_audit_ops ─────────────────────────────────────

    @mcp.tool()
    def workspace_audit_ops(since: str = "7d") -> dict:
        """跑 agora 操作审计维度 (默认最近 7d 操作).

        Args:
            since: 时间范围 (如 7d, 30d, 2026-05-01T00:00:00Z)
        """
        ws_root = _resolve_workspace_root()
        result = _run_audit(ws_root, dim="ops", fmt="json", since=since)
        if "error" in result:
            return _error(result["error"])
        return _ok(
            {
                "format_version": FORMAT_VERSION,
                "since": since,
                "report": _parse_report(result["stdout"], "json"),
            }
        )
