"""Cockpit Engineering Delivery Golden Journey Read-only Projection (SSOT).

Projects existing OMO, Agent Workflow, and Git/PR evidence into a unified
7-stage journey without creating a secondary task database or state machine.
"""

from __future__ import annotations

import datetime
import json
import os
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    yaml = None


@dataclass
class DeliveryStage:
    """A single stage in the engineering delivery journey."""
    name: str
    status: str  # "verified" | "running" | "pending" | "failed" | "unavailable" | "merged" | "open"
    title: str
    details: dict[str, Any] = field(default_factory=dict)
    last_updated: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DeliveryJourneySnapshot:
    """A complete engineering delivery journey snapshot."""
    id: str
    title: str
    status: str  # "live" | "stale" | "failed" | "unavailable"
    source: list[str]
    freshness: int
    last_updated: str
    stages: dict[str, dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _get_iso_now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _get_fixture_snapshot(state: str) -> DeliveryJourneySnapshot:
    """Return a safe fixture E2E snapshot for PENDING -> RUNNING -> VERIFIED -> MERGED."""
    now_iso = _get_iso_now()
    state_up = state.upper()

    if state_up == "UNAVAILABLE":
        stages_unavail = {
            s: {
                "name": s,
                "status": "unavailable",
                "title": f"{s.capitalize()} (Unavailable)",
                "details": {},
                "last_updated": now_iso,
            }
            for s in ["intent", "task", "run", "worktree", "verification", "pr", "evidence"]
        }
        return DeliveryJourneySnapshot(
            id="fixture-unavailable",
            title="Unavailable Journey",
            status="unavailable",
            source=["fixture"],
            freshness=0,
            last_updated=now_iso,
            stages=stages_unavail,
        )

    if state_up == "PENDING":
        stages = {
            "intent": {"name": "intent", "status": "pending", "title": "目标定义中", "details": {"objective": "准备执行任务包"}, "last_updated": now_iso},
            "task": {"name": "task", "status": "pending", "title": "任务待分配", "details": {}, "last_updated": now_iso},
            "run": {"name": "run", "status": "pending", "title": "待启动工作流", "details": {}, "last_updated": now_iso},
            "worktree": {"name": "worktree", "status": "pending", "title": "工作树未初始化", "details": {}, "last_updated": now_iso},
            "verification": {"name": "verification", "status": "pending", "title": "门禁检查等待中", "details": {}, "last_updated": now_iso},
            "pr": {"name": "pr", "status": "pending", "title": "PR 尚未创建", "details": {}, "last_updated": now_iso},
            "evidence": {"name": "evidence", "status": "pending", "title": "交付工件待记录", "details": {}, "last_updated": now_iso},
        }
        return DeliveryJourneySnapshot(
            id="fixture-pending-101",
            title="Fixture Task: PENDING state",
            status="live",
            source=["omo", "agent-workflow", "git"],
            freshness=1,
            last_updated=now_iso,
            stages=stages,
        )

    elif state_up == "RUNNING":
        stages = {
            "intent": {"name": "intent", "status": "verified", "title": "目标已确定", "details": {"objective": "落实 Cockpit 黄金旅程投影"}, "last_updated": now_iso},
            "task": {"name": "task", "status": "verified", "title": "任务包 C 认领", "details": {"task_id": "TASK-2026-C"}, "last_updated": now_iso},
            "run": {"name": "run", "status": "running", "title": "执行 project-code-change", "details": {"run_id": "20260801T113654Z-run-001", "profile": "engineering-agent"}, "last_updated": now_iso},
            "worktree": {"name": "worktree", "status": "running", "title": "工作树进行中", "details": {"branch": "codex/cockpit-delivery-golden-journey", "clean": False}, "last_updated": now_iso},
            "verification": {"name": "verification", "status": "pending", "title": "门禁检查执行中", "details": {"gac_local_gate": "running"}, "last_updated": now_iso},
            "pr": {"name": "pr", "status": "pending", "title": "准备创建 PR", "details": {}, "last_updated": now_iso},
            "evidence": {"name": "evidence", "status": "pending", "title": "证据链采集", "details": {}, "last_updated": now_iso},
        }
        return DeliveryJourneySnapshot(
            id="fixture-running-102",
            title="Fixture Task: RUNNING state",
            status="live",
            source=["omo", "agent-workflow", "git"],
            freshness=0,
            last_updated=now_iso,
            stages=stages,
        )

    elif state_up == "VERIFIED":
        stages = {
            "intent": {"name": "intent", "status": "verified", "title": "目标已确定", "details": {"objective": "落实 Cockpit 黄金旅程投影"}, "last_updated": now_iso},
            "task": {"name": "task", "status": "verified", "title": "任务包 C 认领", "details": {"task_id": "TASK-2026-C"}, "last_updated": now_iso},
            "run": {"name": "run", "status": "verified", "title": "工作流执行完毕", "details": {"run_id": "20260801T113654Z-run-001"}, "last_updated": now_iso},
            "worktree": {"name": "worktree", "status": "verified", "title": "工作树整洁且就绪", "details": {"branch": "codex/cockpit-delivery-golden-journey", "clean": True}, "last_updated": now_iso},
            "verification": {"name": "verification", "status": "verified", "title": "所有集成测试通过", "details": {"gac_local_gate": "PASS", "test_count": 42}, "last_updated": now_iso},
            "pr": {"name": "pr", "status": "open", "title": "PR 已开启并就绪", "details": {"pr_url": "https://github.com/starlink-awaken/omostation/pull/732", "state": "OPEN"}, "last_updated": now_iso},
            "evidence": {"name": "evidence", "status": "verified", "title": "合规与日志已固化", "details": {"evidence_id": "EV-2026-C"}, "last_updated": now_iso},
        }
        return DeliveryJourneySnapshot(
            id="fixture-verified-103",
            title="Fixture Task: VERIFIED state",
            status="live",
            source=["omo", "agent-workflow", "git", "pr"],
            freshness=0,
            last_updated=now_iso,
            stages=stages,
        )

    else:  # MERGED
        stages = {
            "intent": {"name": "intent", "status": "verified", "title": "目标已确定", "details": {"objective": "落实 Cockpit 黄金旅程投影"}, "last_updated": now_iso},
            "task": {"name": "task", "status": "verified", "title": "任务包 C 认领", "details": {"task_id": "TASK-2026-C"}, "last_updated": now_iso},
            "run": {"name": "run", "status": "verified", "title": "工作流结单", "details": {"run_id": "20260801T113654Z-run-001"}, "last_updated": now_iso},
            "worktree": {"name": "worktree", "status": "verified", "title": "工作区清理已同步", "details": {"branch": "codex/cockpit-delivery-golden-journey", "clean": True}, "last_updated": now_iso},
            "verification": {"name": "verification", "status": "verified", "title": "全量验证完成", "details": {"gac_local_gate": "PASS"}, "last_updated": now_iso},
            "pr": {"name": "pr", "status": "merged", "title": "PR 合并完成", "details": {"pr_url": "https://github.com/starlink-awaken/omostation/pull/732", "merged_at": now_iso}, "last_updated": now_iso},
            "evidence": {"name": "evidence", "status": "verified", "title": "证据链与审计封存", "details": {"evidence_id": "EV-2026-C-CLOSED"}, "last_updated": now_iso},
        }
        return DeliveryJourneySnapshot(
            id="fixture-merged-104",
            title="Fixture Task: MERGED state",
            status="live",
            source=["omo", "agent-workflow", "git", "pr"],
            freshness=0,
            last_updated=now_iso,
            stages=stages,
        )


def _try_get_git_info(root_dir: Path) -> dict[str, Any]:
    try:
        branch = subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=str(root_dir),
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
        sha = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(root_dir),
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
        status_res = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=str(root_dir),
            capture_output=True,
            text=True,
        )
        is_clean = len(status_res.stdout.strip()) == 0
        return {"branch": branch, "sha": sha, "is_clean": is_clean, "ok": True}
    except Exception:
        return {"ok": False}


def build_delivery_journey_projection(
    root_dir: Path | None = None,
    fixture_state: str | None = None,
) -> DeliveryJourneySnapshot:
    """Build a read-only projection of the current engineering delivery journey."""
    env_fixture = os.environ.get("COCKPIT_JOURNEY_FIXTURE", "").strip()
    target_fixture = fixture_state or (env_fixture if env_fixture else None)
    if target_fixture:
        return _get_fixture_snapshot(target_fixture)

    now_iso = _get_iso_now()
    if root_dir is None:
        # Default fallback to repo root relative to this file
        root_dir = Path(__file__).resolve().parents[4]

    # Attempt to read OMO / agent-workflow runs
    runs_dir = root_dir / ".omo" / "_delivery" / "agent-workflows" / "runs"
    active_runs = []
    if runs_dir.exists() and yaml is not None:
        for fpath in runs_dir.glob("*.yaml"):
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                    if isinstance(data, dict):
                        active_runs.append(data)
            except Exception:
                continue

    # Sort runs by timestamp descending if possible
    active_runs.sort(key=lambda r: str(r.get("start_time", "")), reverse=True)
    latest_run = active_runs[0] if active_runs else None

    # Determine top-level availability
    git_info = _try_get_git_info(root_dir)
    if latest_run is None and not git_info.get("ok"):
        return _get_fixture_snapshot("UNAVAILABLE")

    run_id = str(latest_run.get("run_id", "live-session")) if latest_run else "git-live-session"
    title = str(latest_run.get("objective", "当前工程实践分支")) if latest_run else f"Git Worktree: {git_info.get('branch', 'unknown')}"

    # Stage 1: Intent
    intent_status = "verified" if latest_run and latest_run.get("objective") else ("verified" if git_info.get("ok") else "unavailable")
    intent_stage = {
        "name": "intent",
        "status": intent_status,
        "title": "意图与需求捕获" if intent_status == "verified" else "目标不可读",
        "details": {"objective": latest_run.get("objective", "")} if latest_run else {},
        "last_updated": now_iso,
    }

    # Stage 2: Task
    task_status = "verified" if latest_run else "pending"
    workflow_name = latest_run.get("workflow_id") or latest_run.get("workflow", "standard") if latest_run else "standard"
    task_stage = {
        "name": "task",
        "status": task_status,
        "title": f"任务流 ({workflow_name})" if latest_run else "自由开发会话",
        "details": {"run_id": run_id, "profile": latest_run.get("agent_profile") or latest_run.get("profile", "")} if latest_run else {},
        "last_updated": now_iso,
    }

    # Stage 3: Run
    is_closed = bool(latest_run and (latest_run.get("closed_at") or latest_run.get("end_time") or latest_run.get("status") in ["ok", "closed", "completed"]))
    run_status = "verified" if is_closed else ("running" if latest_run else "pending")
    run_stage = {
        "name": "run",
        "status": run_status,
        "title": "工作流已收口结单" if run_status == "verified" else ("Agent Workflow 活跃中" if run_status == "running" else "工作流状态"),
        "details": {
            "claimed_paths": latest_run.get("claimed_paths", []),
            "staged_files": latest_run.get("staged_files", []),
            "closed_at": latest_run.get("closed_at", "") if is_closed else "",
        } if latest_run else {},
        "last_updated": now_iso,
    }

    # Stage 4: Worktree
    worktree_status = "verified" if git_info.get("ok") else "unavailable"
    worktree_stage = {
        "name": "worktree",
        "status": worktree_status,
        "title": f"Worktree ({git_info.get('branch', 'unknown')})" if worktree_status == "verified" else "工作树不可用",
        "details": git_info if worktree_status == "verified" else {},
        "last_updated": now_iso,
    }

    # Stage 5: Verification
    ev_list = latest_run.get("evidence", []) if latest_run and isinstance(latest_run.get("evidence"), list) else []
    has_verify_ev = any("verify:" in str(e) and "ok=True" in str(e) for e in ev_list)
    verification_status = "verified" if (latest_run and (latest_run.get("verification") or has_verify_ev or is_closed)) else "pending"
    verification_stage = {
        "name": "verification",
        "status": verification_status,
        "title": "验证检查已通过" if verification_status == "verified" else "等待验证测试",
        "details": {"evidence": ev_list} if has_verify_ev else ({"verification": latest_run.get("verification")} if latest_run and latest_run.get("verification") else {}),
        "last_updated": now_iso,
    }

    # Stage 6: PR
    pr_status = "pending"
    pr_details: dict[str, Any] = {}
    if latest_run and latest_run.get("pr"):
        pr_status = "open"
        pr_details = {"pr": latest_run.get("pr")}
    pr_stage = {
        "name": "pr",
        "status": pr_status,
        "title": "Pull Request" if pr_status != "pending" else "等待创建 PR",
        "details": pr_details,
        "last_updated": now_iso,
    }

    # Stage 7: Evidence
    evidence_status = "verified" if latest_run and latest_run.get("evidence") else "pending"
    evidence_stage = {
        "name": "evidence",
        "status": evidence_status,
        "title": "审计与工件证据",
        "details": {"evidence": latest_run.get("evidence")} if latest_run and latest_run.get("evidence") else {},
        "last_updated": now_iso,
    }

    stages = {
        "intent": intent_stage,
        "task": task_stage,
        "run": run_stage,
        "worktree": worktree_stage,
        "verification": verification_stage,
        "pr": pr_stage,
        "evidence": evidence_stage,
    }

    return DeliveryJourneySnapshot(
        id=run_id,
        title=title,
        status="live",
        source=["omo", "agent-workflow", "git"],
        freshness=0,
        last_updated=now_iso,
        stages=stages,
    )
