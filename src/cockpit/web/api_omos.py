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
