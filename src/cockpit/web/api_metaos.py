"""MetaOS API routes for Cockpit Dashboard."""

from __future__ import annotations

import sys
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Request
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/api/metaos", tags=["metaos"])

_REPO_ROOT = Path(__file__).resolve().parents[5]

# Ensure metaos src is in sys.path
_METAOS_SRC = _REPO_ROOT / "projects" / "metaos" / "src"
if str(_METAOS_SRC) not in sys.path:
    sys.path.insert(0, str(_METAOS_SRC))

from metaos.core.engine import SEngine
from metaos.core.workflow_planner import WorkflowPlanner
from metaos.core.workflow_store import WorkflowStore


def _get_engine():
    data_dir = str(Path.home() / ".metaos" / "data")
    return SEngine(data_dir=data_dir)


@router.post("/plan")
async def api_metaos_plan(request: Request):
    """🧠 动态规划任务，返回 DAG 结构以供前端绘图"""
    try:
        body = await request.json()
        task = body.get("task")
        if not task:
            return JSONResponse({"status": "error", "error": "task is required"}, status_code=400)

        engine = _get_engine()
        token = engine.register_h("metaos_system", "MetaOS Planner")
        engine.authenticate(token)

        planner = WorkflowPlanner(engine, use_llm=True)
        wf = planner.plan(task)

        # Map to frontend expected WorkflowGraph nodes/edges structure
        nodes = []
        for i, (nid, node) in enumerate(wf.nodes.items()):
            nodes.append({"id": nid, "index": i, "label": f"{nid} ({node.task_type})"})

        edges = []
        for nid, node in wf.nodes.items():
            for dep in node.depends_on:
                edges.append({"source": dep, "target": nid})

        return JSONResponse({"status": "ok", "workflow_id": wf.workflow_id, "nodes": nodes, "edges": edges})
    except Exception as e:  # defensive fallback  # noqa: BLE001
        return JSONResponse({"status": "error", "error": str(e)}, status_code=500)


def _async_execute_workflow(task_description: str):
    """Background task to plan and execute the workflow"""
    try:
        engine = _get_engine()
        token = engine.register_h("metaos_system", "MetaOS Planner")
        engine.authenticate(token)
        planner = WorkflowPlanner(engine, use_llm=True)
        wf = planner.plan(task_description)
        wf.run()
    except Exception as e:  # defensive fallback  # noqa: BLE001
        print(f"Background execution failed: {e}")


@router.post("/execute")
async def api_metaos_execute(request: Request, background_tasks: BackgroundTasks):
    """⚙️ 规划并后台异步执行任务"""
    try:
        body = await request.json()
        task = body.get("task")
        if not task:
            return JSONResponse({"status": "error", "error": "task is required"}, status_code=400)

        # Trigger execution in background to avoid client timeouts
        background_tasks.add_task(_async_execute_workflow, task)
        return JSONResponse({"status": "ok", "msg": "Task accepted and execution started in background."})
    except Exception as e:  # defensive fallback  # noqa: BLE001
        return JSONResponse({"status": "error", "error": str(e)}, status_code=500)


@router.get("/workflows")
async def api_metaos_workflows():
    """获取所有历史工作流"""
    try:
        store = WorkflowStore()
        records = store.list_workflows(50)
        return JSONResponse({"status": "ok", "workflows": records})
    except Exception as e:  # defensive fallback  # noqa: BLE001
        return JSONResponse({"status": "error", "error": str(e)}, status_code=500)


@router.get("/workflows/{workflow_id}")
async def api_metaos_workflow_detail(workflow_id: str):
    """获取工作流详细信息以及各节点状态"""
    try:
        store = WorkflowStore()
        wf_detail = store.get_workflow(workflow_id)
        if not wf_detail:
            return JSONResponse({"status": "error", "error": "Workflow not found"}, status_code=404)

        # Map nodes to support task_type parameter expected in frontend UI
        nodes = []
        for n in wf_detail.get("nodes", []):
            nodes.append(
                {
                    "id": n["id"],
                    "task_type": n["type"],
                    "type": n["type"],
                    "status": n["status"],
                    "output": n.get("output", ""),
                }
            )

        wf_detail["nodes"] = nodes
        return JSONResponse({"status": "ok", "workflow": wf_detail})
    except Exception as e:  # defensive fallback  # noqa: BLE001
        return JSONResponse({"status": "error", "error": str(e)}, status_code=500)


@router.post("/workflows/{workflow_id}/approve")
async def api_metaos_workflow_approve(workflow_id: str):
    """✅ 批准被 RED 门控暂停的节点，将其设置为 completed 状态以允许继续运行"""
    try:
        store = WorkflowStore()
        wf_detail = store.get_workflow(workflow_id)
        if not wf_detail:
            return JSONResponse({"status": "error", "error": "Workflow not found"}, status_code=404)

        awaiting = [n for n in wf_detail.get("nodes", []) if n["status"] == "awaiting_approval"]
        if not awaiting:
            return JSONResponse({"status": "error", "error": "No nodes waiting for approval"}, status_code=400)

        # Update database status directly to unlock the block
        with store._conn() as conn:
            conn.execute(
                "UPDATE workflow_nodes SET status='completed' WHERE workflow_id=? AND status='awaiting_approval'",
                (workflow_id,),
            )

        return JSONResponse({"status": "ok", "msg": f"Workflow {workflow_id} has been approved."})
    except Exception as e:  # defensive fallback  # noqa: BLE001
        return JSONResponse({"status": "error", "error": str(e)}, status_code=500)
