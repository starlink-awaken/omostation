"""eCOS dashboard API — cockpit 收敛 (P46 follow-up P45 W3 known issue)

P45 W3 发现: port-registry 注释 9090 (ecos-dashboard) "核心功能已收敛到 cockpit /api/ecos/status"
但 cockpit 无 /api/ecos/status 端点. P46 真修.

端点 (新):
  GET /api/ecos/status  → eCOS dashboard status JSON (从 protocols/port-registry.yaml + eCOS v6 读)
  GET /api/ecos/health  → eCOS health check

数据源:
- protocols/port-registry.yaml (端口 SSOT)
- projects/ecos/src/ecos/ssot/mof/m0/snapshot.yaml (M0 runtime snapshot, eCOS v6)
"""

from __future__ import annotations

from pathlib import Path

import yaml

try:
    from fastapi import APIRouter

    router = APIRouter(prefix="/api/ecos", tags=["ecos"])
except ImportError:
    router = None


_REPO_ROOT = Path(__file__).resolve().parents[4]


if router:

    @router.get("/status")
    async def get_ecos_status():
        """获取 eCOS dashboard 状态.

        数据源 (优先级):
        1. protocols/port-registry.yaml (端口 SSOT, 23 项目端口)
        2. projects/ecos/src/ecos/ssot/mof/m0/snapshot.yaml (eCOS v6 4 Spine)
        """
        try:
            port_registry = _REPO_ROOT / "protocols" / "port-registry.yaml"
            ports_count = 0
            mcp_stdio_count = 0
            if port_registry.exists():
                with open(port_registry) as f:
                    pr = yaml.safe_load(f) or {}
                if "ports" in pr:
                    ports_count = len(pr["ports"])
                if "mcp_transport_defaults" in pr:
                    mcp_stdio_count = len(pr["mcp_transport_defaults"])

            m0_snapshot = _REPO_ROOT / "projects" / "ecos" / "src" / "ecos" / "ssot" / "mof" / "m0" / "snapshot.yaml"
            m0_status = "available" if m0_snapshot.exists() else "unavailable"

            return {
                "service": "ecos-dashboard",
                "status": "converged",
                "converged_to": "cockpit /api/ecos/status",
                "ssot": {
                    "port_registry_ports": ports_count,
                    "mcp_stdio_defaults": mcp_stdio_count,
                },
                "m0_snapshot": m0_status,
                "architecture": "eCOS v6 Core Backbone (4 Spine: Memory/Swarm/Compute/OMO)",
            }
        except Exception as e:
            return {
                "service": "ecos-dashboard",
                "status": "degraded",
                "converged_to": "cockpit /api/ecos/status",
                "error": str(e),
            }

    @router.get("/health")
    async def get_ecos_health():
        """eCOS health check."""
        return {"status": "ok", "service": "ecos-dashboard-converged", "endpoint": "/api/ecos/status"}
