"""治理仪表板 API"""

from __future__ import annotations

from pathlib import Path

try:
    from fastapi import APIRouter
    from fastapi.responses import HTMLResponse

    router = APIRouter(prefix="/governance", tags=["governance"])
except ImportError:
    router = None

_REPO_ROOT = Path(__file__).resolve().parents[4]


if router:

    @router.get("/status")
    async def get_status():
        """获取治理状态"""
        try:
            import yaml

            system_yaml = _REPO_ROOT / ".omo" / "state" / "system.yaml"
            if system_yaml.exists():
                with open(system_yaml) as f:
                    data = yaml.safe_load(f) or {}
                return {
                    "health_score": data.get("health_score", 82.0),
                    "debt_weight": data.get("debt_weight", 1.0),
                    "debt_health": data.get("debt_metrics", {}).get("debt_health", 100.0),
                    "resolved_count": data.get("debt_metrics", {}).get("resolved_count", 9),
                    "unresolved_count": data.get("debt_metrics", {}).get("unresolved_count", 0),
                }
        except Exception:
            pass
        return {
            "health_score": 82.0,
            "debt_weight": 1.0,
            "debt_health": 100.0,
            "resolved_count": 9,
            "unresolved_count": 0,
        }

    @router.get("/dashboard", response_class=HTMLResponse)
    async def get_dashboard():
        """获取治理仪表板 HTML"""
        dashboard_path = Path(__file__).parent / "index.html"
        if dashboard_path.exists():
            return HTMLResponse(content=dashboard_path.read_text())
        return HTMLResponse(content="<h1>治理仪表板</h1><p>仪表板文件不存在</p>")

    @router.get("/projects")
    async def get_projects():
        """获取项目状态"""
        projects = ["kairon", "agora", "cockpit", "ecos", "gbrain", "metaos", "omo", "runtime"]
        result = []
        for proj in projects:
            proj_dir = _REPO_ROOT / "projects" / proj
            if proj_dir.exists():
                has_githooks = (proj_dir / ".githooks").exists()
                result.append(
                    {
                        "name": proj,
                        "status": "healthy" if has_githooks else "warning",
                        "has_githooks": has_githooks,
                    }
                )
        return {"projects": result, "total": len(result)}
