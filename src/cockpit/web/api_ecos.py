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


_REPO_ROOT = Path(__file__).resolve().parents[5]


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
        except Exception as e:  # defensive fallback  # noqa: BLE001
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

    # ── Workflow endpoints ──

    @router.get("/workflow/list")
    async def list_workflows():
        """列出所有 ecos L0 工作流"""
        try:
            from ecos.workflow import list_workflows

            wfs = list_workflows()
            # 去掉 Python 对象中不可 JSON 序列化的字段
            safe = []
            for w in wfs:
                safe.append(
                    {k: v for k, v in w.items() if isinstance(v, (str, int, float, bool, list, dict)) or v is None}
                )
            return {"workflows": safe, "total": len(safe)}
        except Exception as e:  # defensive fallback  # noqa: BLE001
            return {"error": str(e), "workflows": [], "total": 0}

    @router.post("/workflow/run")
    async def run_workflow(name: str, dry_run: bool = False):
        """执行 ecos L0 工作流

        Args:
            name: 工作流名称 (M1 ID 或 definitions 名称)
            dry_run: 干跑模式
        """
        try:
            from ecos.workflow import execute_m1_workflow

            result = execute_m1_workflow(name, dry_run=dry_run)
            # 确保可 JSON 序列化
            safe = {}
            for k, v in result.items():
                try:
                    import json

                    json.dumps(v)
                    safe[k] = v
                except (TypeError, ValueError):
                    safe[k] = str(v)
            return safe
        except Exception as e:  # defensive fallback  # noqa: BLE001
            return {"error": str(e), "workflow": name, "passed": 0, "failed": 0}

    @router.get("/workflow/describe/{name}")
    async def describe_workflow(name: str):
        """查看 ecos L0 工作流定义"""
        try:
            from ecos.workflow import load_workflow

            wf = load_workflow(name)
            if not wf:
                return {"error": f"工作流不存在: {name}"}
            return wf
        except Exception as e:  # defensive fallback  # noqa: BLE001
            return {"error": str(e)}

    @router.get("/workflow/backends")
    async def list_backends():
        """列出所有已注册 workflow backend"""
        try:
            from ecos.workflow import list_backends

            return {"backends": list_backends()}
        except Exception as e:  # defensive fallback  # noqa: BLE001
            return {"error": str(e), "backends": []}

    @router.get("/workflow/actions")
    async def list_workflow_actions():
        """列出所有已注册 workflow action"""
        try:
            from ecos.workflow.actions import list_actions

            return {"actions": list_actions()}
        except Exception as e:  # defensive fallback  # noqa: BLE001
            return {"error": str(e), "actions": []}

    @router.get("/workflow/validate/{name}")
    async def validate_workflow_api(name: str):
        """验证工作流定义（X1-X4 约束检查）"""
        try:
            from ecos.workflow import load_workflow
            from ecos.workflow.validator import validate_workflow

            wf = load_workflow(name)
            if not wf:
                return {"error": f"工作流不存在: {name}"}
            violations = validate_workflow(wf)
            errors = [v for v in violations if v.get("severity") == "error"]
            warnings = [v for v in violations if v.get("severity") != "error"]
            return {
                "name": name,
                "valid": len(errors) == 0,
                "errors": errors,
                "warnings": warnings,
                "total_violations": len(violations),
            }
        except Exception as e:  # defensive fallback  # noqa: BLE001
            return {"error": str(e)}

    @router.get("/workflow/logs")
    async def list_workflow_logs(recent: int = 10, status: str = ""):
        """查询工作流运行历史（M0 快照）"""
        try:
            from ecos.cli.workflow_runs import _load_all_runs

            runs = _load_all_runs()
            if status:
                runs = [r for r in runs if r.get("status") == status]
            runs = runs[:recent]
            safe = []
            for r in runs:
                safe.append(
                    {k: v for k, v in r.items() if isinstance(v, (str, int, float, bool, list, dict)) or v is None}
                )
            return {"runs": safe, "total": len(safe)}
        except Exception as e:  # defensive fallback  # noqa: BLE001
            return {"error": str(e), "runs": []}

    @router.post("/workflow/test")
    async def test_workflow_api(name: str):
        """测试工作流编排（mock action，不执行真实脚本）"""
        try:
            from ecos.workflow.executor import test_workflow

            result = test_workflow(name)
            safe = {}
            for k, v in result.items():
                try:
                    import json

                    json.dumps(v)
                    safe[k] = v
                except (TypeError, ValueError):
                    safe[k] = str(v)
            return safe
        except Exception as e:  # defensive fallback  # noqa: BLE001
            return {"error": str(e)}

    @router.get("/skills")
    async def list_skills():
        """列出系统中定义的所有技能 (Custom Skills)"""
        try:
            from fastapi.responses import JSONResponse

            skills = []

            # 1. 扫描 Workspace 技能
            ws_skills_dir = _REPO_ROOT / ".agents" / "skills"
            if ws_skills_dir.exists():
                for d in ws_skills_dir.iterdir():
                    if d.is_dir() and (d / "SKILL.md").exists():
                        skills.append({"name": d.name, "source": "workspace", "path": str(d / "SKILL.md")})

            # 2. 扫描全局技能
            global_plugins_dir = Path.home() / ".gemini" / "config" / "plugins"
            if global_plugins_dir.exists():
                for plugin_dir in global_plugins_dir.iterdir():
                    if plugin_dir.is_dir():
                        skills_dir = plugin_dir / "skills"
                        if skills_dir.exists():
                            for d in skills_dir.iterdir():
                                if d.is_dir() and (d / "SKILL.md").exists():
                                    skills.append(
                                        {
                                            "name": d.name,
                                            "source": f"plugin:{plugin_dir.name}",
                                            "path": str(d / "SKILL.md"),
                                        }
                                    )

            # 3. 补充内置技能
            builtin_skills_dir = Path.home() / ".gemini" / "antigravity-cli" / "builtin" / "skills"
            if builtin_skills_dir.exists():
                for d in builtin_skills_dir.iterdir():
                    if d.is_dir() and (d / "SKILL.md").exists():
                        skills.append({"name": d.name, "source": "builtin", "path": str(d / "SKILL.md")})

            # 解析 Frontmatter YAML
            parsed_skills = []
            for s in skills:
                try:
                    content = Path(s["path"]).read_text(encoding="utf-8")
                    desc = ""
                    name = s["name"]
                    if content.startswith("---"):
                        parts = content.split("---", 2)
                        if len(parts) >= 3:
                            yaml_content = yaml.safe_load(parts[1]) or {}
                            name = yaml_content.get("name", name)
                            desc = yaml_content.get("description", desc)
                    parsed_skills.append(
                        {"id": s["name"], "name": name, "description": desc, "source": s["source"], "path": s["path"]}
                    )
                except Exception:  # defensive fallback  # noqa: BLE001
                    parsed_skills.append(
                        {
                            "id": s["name"],
                            "name": s["name"],
                            "description": "自定义开发辅助技能",
                            "source": s["source"],
                            "path": s["path"],
                        }
                    )

            return JSONResponse(content={"status": "ok", "skills": parsed_skills})
        except Exception as e:  # defensive fallback  # noqa: BLE001
            return JSONResponse(content={"status": "error", "error": str(e)}, status_code=500)
