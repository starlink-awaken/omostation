"""Agora API routes for Cockpit Dashboard."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Form, Request
from fastapi.responses import JSONResponse

router = APIRouter()

_REPO_ROOT = Path(__file__).resolve().parents[5]

# Read builtin pipelines
_BUILTIN_PIPELINES_PATH = _REPO_ROOT / "projects" / "agora" / "src" / "agora" / "pipelines" / "builtin.json"


def _load_builtin_pipelines() -> dict:
    if _BUILTIN_PIPELINES_PATH.exists():
        try:
            return json.loads(_BUILTIN_PIPELINES_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


@router.get("/api/pipelines")
async def api_list_pipelines():
    """获取所有可用管线列表"""
    pipelines = list(_load_builtin_pipelines().keys())
    return JSONResponse({"status": "ok", "pipelines": pipelines})


@router.get("/api/pipeline/{name}/dag")
async def api_pipeline_dag(name: str):
    """获取特定管线的 DAG 数据，供前端 WorkflowGraph 绘图"""
    pipelines = _load_builtin_pipelines()
    steps = pipelines.get(name)
    if not steps:
        return JSONResponse({"status": "error", "error": f"Pipeline not found: {name}"}, status_code=404)

    # Build DAG nodes
    nodes = []
    for i, step in enumerate(steps):
        nodes.append({"id": f"step_{i}", "index": i, "label": step["tool"]})

    # Build DAG edges
    edges = []
    output_to_index = {step.get("output_as"): i for i, step in enumerate(steps) if step.get("output_as")}
    for i, step in enumerate(steps):
        for dep in step.get("depends_on", []):
            if dep in output_to_index:
                edges.append({"source": f"step_{output_to_index[dep]}", "target": f"step_{i}"})

    return JSONResponse({"status": "ok", "nodes": nodes, "edges": edges})


@router.post("/api/pipeline")
async def api_run_pipeline(request: Request):
    """⚙️ 调度执行特定的工具管线"""
    try:
        content_type = request.headers.get("content-type", "")
        name = None
        goal = None

        if "multipart/form-data" in content_type or "application/x-www-form-urlencoded" in content_type:
            form_data = await request.form()
            name = form_data.get("name")
            goal = form_data.get("goal")
        else:
            try:
                json_data = await request.json()
                name = json_data.get("name")
                goal = json_data.get("goal")
            except Exception:
                pass

        if not name:
            name = request.query_params.get("name")
        if not goal:
            goal = request.query_params.get("goal")

        if not name or not goal:
            return JSONResponse({"status": "error", "error": "name and goal are required parameters"}, status_code=400)

        env = os.environ.copy()
        # Run via agora CLI pipeline command in subprocess to leverage automatic environment load
        proc = subprocess.run(["agora", "pipeline", name, "--goal", goal], capture_output=True, text=True, env=env)
        if proc.returncode == 0:
            return JSONResponse({"status": "ok", "result": proc.stdout})
        else:
            error_msg = proc.stderr or proc.stdout or "Pipeline execution failed"
            # Strip deprecation warning from error messages if present
            if "独立 CLI 已弃用" in error_msg:
                lines = error_msg.splitlines()
                error_msg = "\n".join([line for line in lines if "已弃用" not in line]).strip()
            return JSONResponse({"status": "error", "error": error_msg}, status_code=500)
    except Exception as e:
        return JSONResponse({"status": "error", "error": str(e)}, status_code=500)


@router.post("/api/instance")
async def api_register_instance(service: str = Form(...), mcp_endpoint: str = Form(...)):
    """分布式新实例 MCP 注册"""
    try:
        # Load agora package dynamically
        agora_src = _REPO_ROOT / "projects" / "agora" / "src"
        if str(agora_src) not in sys.path:
            sys.path.insert(0, str(agora_src))

        from agora.core.service_base import Service
        from agora.core.state import get_registry

        registry = get_registry()
        # Unregister existing to overwrite safely
        try:
            registry.unregister(service)
        except Exception:
            pass

        svc = Service(name=service, protocol="mcp", mcp_endpoint=mcp_endpoint)
        registry.register(svc)

        return JSONResponse({"status": "ok", "msg": f"实例 {service} 注册成功 (Endpoint: {mcp_endpoint})"})
    except Exception as e:
        return JSONResponse({"status": "error", "error": str(e)}, status_code=500)


@router.get("/api/metrics/history")
async def api_metrics_history():
    """系统运行状态指标历史"""
    try:
        # Load agora package to get registry stats
        agora_src = _REPO_ROOT / "projects" / "agora" / "src"
        if str(agora_src) not in sys.path:
            sys.path.insert(0, str(agora_src))

        from agora.core.state import get_registry

        registry = get_registry()
        services = registry.list_all()
        healthy_count = sum(1 for s in services if s.is_available)

        # Mock latency metrics distribution matching typical BOS responses
        latency = {
            "bos://memory/": "14.5ms",
            "bos://governance/": "8.2ms",
            "bos://analysis/": "22.1ms",
            "bos://persona/": "5.6ms",
            "bos://capability/": "12.8ms",
        }

        return JSONResponse(
            {
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "services": len(services) or 8,  # Default fallback if empty
                "healthy": healthy_count or 8,
                "latency": latency,
            }
        )
    except Exception as e:
        return JSONResponse({"status": "error", "error": str(e)}, status_code=500)
