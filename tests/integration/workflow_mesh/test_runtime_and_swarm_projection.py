from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
for source in (
    ROOT / "projects" / "omo" / "src",
    ROOT / "projects" / "runtime" / "src",
    ROOT / "projects" / "aetherforge" / "packages" / "swarm" / "src",
):
    if str(source) not in sys.path:
        sys.path.insert(0, str(source))


def test_runtime_and_swarm_events_project_into_omo(tmp_path: Path) -> None:
    from omo.workflow_mesh import WorkflowMeshStore
    from runtime.executor.engine import AgentRuntime
    from runtime.workflow_admission import admission_proof
    from swarm_engine.graph_workflow import GraphWorkflow

    def grant(run_id: str, step_run_ids: list[str], backend: str) -> dict:
        value = {
            "admission_id": f"adm-{run_id}",
            "status": "admitted",
            "workflow_run_id": run_id,
            "trace_id": run_id,
            "backend": backend,
            "step_run_ids": step_run_ids,
            "capabilities": ["execute"],
            "policy_digest": "integration-policy",
            "issued_at": datetime.now(UTC).isoformat(),
            "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
        }
        value["proof"] = admission_proof(value)
        return value

    store = WorkflowMeshStore(tmp_path)

    runtime = AgentRuntime()
    runtime._call_llm = lambda *args, **kwargs: {  # type: ignore[method-assign]
        "content": "runtime done",
        "tool_calls": [],
        "finish_reason": "stop",
        "usage": {"total_tokens": 1},
    }
    runtime_result = runtime.run_task(
        "runtime integration",
        workflow_run_id="integration-runtime",
        event_sink=store.sink(),
        admission=grant("integration-runtime", ["integration-runtime:runtime"], "runtime"),
    )

    workflow = GraphWorkflow()

    @workflow.node("compute")
    def compute(_state: dict) -> dict:
        return {"output": "swarm done"}

    workflow.set_entry("compute")
    swarm_result = workflow.run(
        {},
        workflow_run_id="integration-swarm",
        event_sink=store.sink(),
        admission=grant("integration-swarm", ["integration-swarm:compute"], "aetherforge"),
    )

    assert runtime_result["result"] == "runtime done"
    assert swarm_result["output"] == "swarm done"
    snapshots = {snapshot["workflow_run_id"]: snapshot for snapshot in store.snapshots()}
    assert snapshots["integration-runtime"]["state"] == "succeeded"
    assert snapshots["integration-swarm"]["state"] == "succeeded"
    assert snapshots["integration-runtime"]["event_count"] == 7
    assert snapshots["integration-swarm"]["event_count"] == 7
    assert snapshots["integration-runtime"]["checkpoints"]
    assert snapshots["integration-swarm"]["checkpoints"]
