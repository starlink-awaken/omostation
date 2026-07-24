"""MetaOS workflow backend adapter — fabric 侧适配 (ADR-0181 Phase 2).

不直接把 metaos.core.workflow.Workflow.run 注册为 backend（那是实例方法）。
本适配器:
1. 强制 preflight（防绕过 ecos 治理管线）
2. 将 M1 steps 映射为 MetaOS DAG 并执行
3. metaos 不可用时明确失败（不静默 default）
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from ecos.workflow.preflight import assert_preflight

logger = logging.getLogger("ecos.workflow.backends.metaos")

__all__ = ["execute"]


def execute(m1_node: dict, params: dict | None = None) -> dict:
    """Backend entrypoint: (m1_node, params) -> result dict."""
    params = params or {}
    wf_name = str(m1_node.get("name") or m1_node.get("id") or "metaos-workflow")

    # Signature-only verify (workflow id may differ between loader name and M1 display name)
    blocked = assert_preflight(params, workflow=None)
    if blocked is not None:
        logger.warning("MetaOS backend blocked: %s", blocked.get("error"))
        return blocked

    try:
        from metaos.core.engine import SEngine
        from metaos.core.workflow import Workflow, WorkflowNode
    except ImportError as e:
        return {
            "steps": [],
            "passed": 0,
            "failed": 1,
            "error": f"metaos_unavailable: {e}",
            "preflight_ok": True,
        }

    steps = m1_node.get("steps") or []
    if not steps:
        return {
            "steps": [],
            "passed": 0,
            "failed": 0,
            "warning": "no_steps",
            "preflight_ok": True,
        }

    engine = SEngine()
    # Ensure an H session so gate/engine can run
    try:
        token = engine.register_h("ecos-fabric", "ecos workflow fabric")
        engine.authenticate(token)
    except Exception as e:
        logger.debug("metaos session bootstrap: %s", e)

    wf_id = str(m1_node.get("id") or wf_name)
    workflow = Workflow(wf_id, engine)

    for i, step in enumerate(steps):
        name = step.get("name") or f"step-{i + 1}"
        action = step.get("action") or "task"
        prompt = step.get("description") or step.get("input") or action
        deps = list(step.get("depends_on") or [])
        workflow.add_node(
            WorkflowNode(
                node_id=name,
                task_type=action,
                input_prompt=str(prompt),
                depends_on=deps,
            )
        )

    # Prefer lightweight sync path for fabric: run each ready node via SEngine.process
    # Full async DAG is available when METAOS_WF_ASYNC=1
    if __import__("os").environ.get("METAOS_WF_ASYNC", "0") == "1":
        try:
            asyncio.run(workflow.run(task_description=wf_name, dag_dict=m1_node))
        except RuntimeError:
            # nested event loop
            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(
                    workflow.run(task_description=wf_name, dag_dict=m1_node)
                )
            finally:
                loop.close()
        return _collect_from_workflow(workflow)

    return _execute_sync_layers(workflow, engine)


def _execute_sync_layers(workflow: Any, engine: Any) -> dict[str, Any]:
    """拓扑分层同步执行，避免测试/CLI 中 asyncio 复杂性。"""
    from metaos.core.types import Task

    results: dict[str, Any] = {
        "steps": [],
        "passed": 0,
        "failed": 0,
        "preflight_ok": True,
    }
    # simple multi-pass until no progress
    safety = 0
    while safety < 100:
        safety += 1
        executable = workflow._get_executable_nodes()
        if not executable:
            pending = [n for n in workflow.nodes.values() if n.status == "pending"]
            if pending:
                for n in pending:
                    n.status = "failed"
                    n.output = "unresolved_dependency"
                    results["steps"].append(
                        {"name": n.node_id, "status": "failed", "error": n.output}
                    )
                    results["failed"] += 1
            break
        for node in executable:
            node.status = "running"
            try:
                task = Task(input=node.input_prompt, task_type=node.task_type)
                out = engine.process(task)
                node.output = (
                    str(out.get("output", out)) if isinstance(out, dict) else str(out)
                )
                node.status = "completed"
                results["steps"].append(
                    {"name": node.node_id, "status": "ok", "result": out}
                )
                results["passed"] += 1
            except Exception as e:
                node.status = "failed"
                node.output = str(e)
                results["steps"].append(
                    {"name": node.node_id, "status": "error", "error": str(e)}
                )
                results["failed"] += 1
                workflow._cascade_fail(node.node_id)
    return results


def _collect_from_workflow(workflow: Any) -> dict[str, Any]:
    results: dict[str, Any] = {
        "steps": [],
        "passed": 0,
        "failed": 0,
        "preflight_ok": True,
    }
    for node in workflow.nodes.values():
        ok = node.status == "completed"
        results["steps"].append(
            {
                "name": node.node_id,
                "status": "ok" if ok else node.status,
                "output": node.output,
            }
        )
        if ok:
            results["passed"] += 1
        else:
            results["failed"] += 1
    return results
