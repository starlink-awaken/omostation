"""OMO dashboard API — cockpit 收敛 (P46 follow-up P45 W3 known issue)

P45 W3 发现: port-registry 注释 9190 (omo-dashboard) "converged to cockpit /api/..."
但 cockpit 无 /api/omos/status 端点. P46 真修.

端点 (新):
  GET /api/omos/status  → OMO dashboard status JSON (从 .omc/state/ + .omo/state/system.yaml + radar 读)
  GET /api/omos/health  → OMO health check

数据源:
- .omc/state/sessions/{sessionId}/autopilot-state.json (autopilot 状态)
- .omo/state/system.yaml (system state, health_score_ref)
- .omo/state/health.yaml (governance health, governance 治理)
"""

from __future__ import annotations

from pathlib import Path

import yaml

try:
    from fastapi import APIRouter

    router = APIRouter(prefix="/api/omos", tags=["omos"])
except ImportError:
    router = None


_REPO_ROOT = Path(__file__).resolve().parents[4]

import sys

# 统一在模块加载时注入 sys.path
for _path in (
    _REPO_ROOT / "projects" / "omo" / "src",
    _REPO_ROOT / "projects" / "bus-foundation" / "src",
):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from datetime import UTC, datetime

import bus_foundation.facade.event as bus_event
import omo.omo_ingress as omo_ingress

if router:

    @router.get("/status")
    async def get_omos_status():
        """获取 OMO dashboard 状态.

        数据源 (优先级):
        1. .omo/state/system.yaml (system state)
        2. .omo/state/health.yaml (governance health)
        3. .omc/state/sessions/ (autopilot 状态)
        """
        try:
            state = {}
            system_yaml = _REPO_ROOT / ".omo" / "state" / "system.yaml"
            if system_yaml.exists():
                with open(system_yaml) as f:
                    state.update(yaml.safe_load(f) or {})

            health_yaml = _REPO_ROOT / ".omo" / "state" / "health.yaml"
            health = {}
            if health_yaml.exists():
                with open(health_yaml) as f:
                    health = yaml.safe_load(f) or {}

            return {
                "service": "omo-dashboard",
                "status": "converged",
                "converged_to": "cockpit /api/omos/status",
                "system": {
                    "current_phase": state.get("current_phase"),
                    "health_score": state.get("health_score"),
                    "completed_tasks": state.get("completed_tasks"),
                    "active_tasks": state.get("active_tasks"),
                    "blocked_tasks": state.get("blocked_tasks"),
                },
                "governance": {
                    "health_score": health.get("health_score"),
                    "anomaly_count": health.get("anomaly_count"),
                    "total_tasks": health.get("total_tasks"),
                    "done": health.get("done"),
                    "planned": health.get("planned"),
                },
            }
        except Exception as e:
            return {
                "service": "omo-dashboard",
                "status": "degraded",
                "converged_to": "cockpit /api/omos/status",
                "error": str(e),
            }

    @router.get("/health")
    async def get_omos_health():
        """OMO health check."""
        return {"status": "ok", "service": "omo-dashboard-converged", "endpoint": "/api/omos/status"}

    @router.get("/quests")
    async def get_quests():
        """列出家庭 Quests 和家庭排行榜"""
        try:
            db_path = _REPO_ROOT / "family-hub" / "family_hub.db"
            if not db_path.exists():
                return {"error": f"family_hub.db not found at {db_path}"}

            import sqlite3

            conn = sqlite3.connect(str(db_path))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("SELECT * FROM quests ORDER BY id DESC")
            quests = [dict(row) for row in cursor.fetchall()]

            cursor.execute("SELECT role, name, level, wisdomPoints, responsibilityPoints, inventory FROM profiles")
            profiles = [dict(row) for row in cursor.fetchall()]

            cursor.execute("SELECT * FROM logs ORDER BY id DESC LIMIT 10")
            logs = [dict(row) for row in cursor.fetchall()]

            conn.close()
            return {"status": "ok", "quests": quests, "profiles": profiles, "logs": logs}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    @router.post("/quests")
    async def create_quest_api(title: str, q_type: str, reward: int, assignee: str):
        """新建一个 Quest，同时在 SQLite 和 OMO 中建立任务"""
        try:
            db_path = _REPO_ROOT / "family-hub" / "family_hub.db"
            if not db_path.exists():
                return {"error": "family_hub.db not found"}

            import sqlite3

            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO quests (title, type, reward, completed, assignee) VALUES (?, ?, ?, 0, ?)",
                (title, q_type, reward, assignee),
            )
            quest_id = cursor.lastrowid
            conn.commit()
            conn.close()

            def _utc_now() -> str:
                return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")

            task_id = f"QUEST-{quest_id}"
            omo_dir = _REPO_ROOT / ".omo"

            task_data = {
                "id": task_id,
                "title": title,
                "description": f"游戏化任务: 奖励 {reward} 积分, 归属于 {assignee}",
                "status": "candidate",
                "task_type": "quest",
                "risk_level": "L0",
                "depends_on": [],
                "source_docs": [".omo/tasks/planned/quest_template.yaml"],
                "deliverables": [f"完成 Quest: {title}"],
                "imported_via": "cockpit_quest_api",
                "context_uri": f"bos://governance/tasks/planned/{task_id}",
                "assigned_to": None,
                "dispatch_id": None,
                "run_ref": None,
                "approval_ref": None,
                "review_ref": None,
                "knowledge_refs": [],
                "handoff_refs": [],
                "governance_refs": [
                    ".omo/standards/omo-governance-surfaces.md",
                    ".omo/_truth/x1-governance-policies.yaml",
                ],
                "entry_gate": [],
                "evidence_required": [f"由 {assignee} 在家庭枢纽标记完成"],
                "test_plan": ["omo check-quest"],
                "allowed_operation_level": "L0",
                "human_approval_required": False,
                "metadata": {
                    "quest_id": quest_id,
                    "assignee": assignee,
                    "reward": reward,
                    "type": q_type,
                    "created_via": "cockpit quest api",
                    "created_at": _utc_now(),
                },
            }

            omo_ingress.create_planned_task(
                omo_dir,
                task_data=task_data,
                ingress_plane="projects/cockpit",
                source_ref=f"cockpit:quest:create:{task_id}",
            )

            return {"status": "ok", "quest_id": quest_id, "task_id": task_id}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    @router.post("/quests/{quest_id}/complete")
    async def complete_quest_api(quest_id: int):
        """将 Quest 标记为完成：归档 OMO 任务并发布事件进行清算"""
        try:
            db_path = _REPO_ROOT / "family-hub" / "family_hub.db"
            if not db_path.exists():
                return {"error": "family_hub.db not found"}

            import sqlite3

            conn = sqlite3.connect(str(db_path))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            quest = cursor.execute("SELECT * FROM quests WHERE id = ? AND completed = 0", (quest_id,)).fetchone()
            conn.close()

            if not quest:
                return {"status": "error", "error": "Quest not found or already completed"}

            task_id = f"QUEST-{quest_id}"
            omo_dir = _REPO_ROOT / ".omo"

            def _utc_now() -> str:
                return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")

            omo_ingress.complete_task(
                omo_dir,
                task_id=task_id,
                actor="projects/cockpit",
                source_ref=f"cockpit:quest:done:{task_id}",
                now=_utc_now(),
                evidence_paths=[f"sqlite://family-hub/quests/{quest_id}"],
            )

            bus_event.publish(
                topic="QuestCompleted",
                payload={
                    "quest_id": quest_id,
                    "task_id": task_id,
                    "assignee": quest["assignee"],
                    "reward": quest["reward"],
                    "type": quest["type"],
                },
                source_uri="bos://governance/cockpit/quests",
            )

            return {"status": "ok", "task_id": task_id, "event_published": True}
        except Exception as e:
            return {"status": "error", "error": str(e)}
