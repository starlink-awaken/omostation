"""Swarm Observatory API endpoints.

提供 swarm 体系可观测数据聚合: agent-workflow runs + 协同 window + branch claims + compliance.
设计参考 api_health.py (subprocess 拉数据 + 显式降级, 不伪造满分).

数据源策略 (KISS): agent-workflow status --json 一次拿全 workflow/compliance/claim_coverage,
再叠加 swarm window-status (协同窗口) + branch-claims 目录 (D2 占用明细).

Routes:
    GET /api/swarm/status   → swarm 全景 (runs + window + claims 摘要 + compliance SLO)
    GET /api/swarm/claims   → 活跃 branch claim 明细
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from fastapi import APIRouter

from cockpit.compat import WORKSPACE_ROOT

router = APIRouter()

WORKSPACE_DIR = WORKSPACE_ROOT
AGENT_WORKFLOW = WORKSPACE_DIR / "bin" / "agent-workflow.py"
SWARM_DISCIPLINE = WORKSPACE_DIR / "bin" / "gac" / "swarm-discipline-cli.py"
BRANCH_CLAIMS_DIR = WORKSPACE_DIR / ".omo" / "_delivery" / "branch-claims"


def _run_cli_json(script: Path, args: list[str] | None = None, timeout: int = 30) -> dict | None:
    """跑 CLI 脚本拿 JSON, 失败/超时返回 None (降级, 不崩)."""
    if not script.exists():
        return None
    cmd = [sys.executable, str(script), *(args or [])]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except (subprocess.TimeoutExpired, OSError):
        return None
    if result.returncode != 0 or not result.stdout.strip():
        return None
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return None


def _load_branch_claims() -> list[dict]:
    """读 .omo/_delivery/branch-claims/*.json, 返回活跃 claim 列表.

    PASW worktree 环境 .omo 可能不完整 → 返回空 (生产 cockpit web 在主仓跑, 路径正确).
    """
    claims: list[dict] = []
    if not BRANCH_CLAIMS_DIR.is_dir():
        return claims
    for path in sorted(BRANCH_CLAIMS_DIR.glob("*.json")):
        try:
            data = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        if isinstance(data, dict):
            data.setdefault("_source", path.name)
            claims.append(data)
    return claims


@router.get("/api/swarm/status")
async def get_swarm_status():
    """获取 swarm 全景可观测数据 (runs + window + claims 摘要 + compliance SLO)."""
    degraded: list[str] = []

    workflow_status = _run_cli_json(AGENT_WORKFLOW, ["status", "--json"])
    if workflow_status is None:
        degraded.append("agent-workflow status unavailable")

    window = _run_cli_json(SWARM_DISCIPLINE, ["window-status"])
    if window is None:
        degraded.append("swarm window-status unavailable")

    claims = _load_branch_claims()
    active_runs = workflow_status.get("active_runs", []) if workflow_status else []
    compliance_block = workflow_status.get("compliance", {}) if workflow_status else {}
    sources_available = sum(1 for src in (workflow_status, window) if src is not None)
    data_quality = (
        "complete" if sources_available == 2 else "partial" if sources_available else "unavailable"
    )

    return {
        "workflow": {
            "active_runs": active_runs,
            "active_count": len(active_runs),
            "run_count": workflow_status.get("run_count", 0) if workflow_status else 0,
            "lock_count": workflow_status.get("lock_count", 0) if workflow_status else 0,
            "stale_locks": workflow_status.get("stale_locks", 0) if workflow_status else 0,
            "current_run_id": workflow_status.get("current_run_id") if workflow_status else None,
        },
        "window": {
            "verdict": window.get("m1_conflict_zero_verdict") if window else None,
            "elapsed_hours": window.get("elapsed_hours") if window else None,
            "conflict_count": window.get("conflict_count") if window else None,
            "started": window.get("window_start") if window else None,
        },
        "claims": {
            "active_count": len(claims),
            "sessions": [claim.get("session", claim.get("_source", "?")) for claim in claims],
        },
        "compliance": {
            "ok": compliance_block.get("ok"),
            "decision": compliance_block.get("decision"),
            "slo": compliance_block.get("slo", {}),
        },
        "claim_coverage": workflow_status.get("claim_coverage", {}) if workflow_status else {},
        "recommended_next": workflow_status.get("recommended_next") if workflow_status else None,
        "data_quality": data_quality,
        "degraded_reasons": degraded,
    }


@router.get("/api/swarm/claims")
async def get_swarm_claims():
    """获取活跃 branch claim 明细."""
    claims = _load_branch_claims()
    return {"active_count": len(claims), "claims": claims}
