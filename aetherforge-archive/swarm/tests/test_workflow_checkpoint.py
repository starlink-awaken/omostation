from __future__ import annotations

from datetime import UTC, datetime, timedelta

from swarm_engine.graph_workflow import GraphWorkflow
from swarm_engine.workflow_admission import admission_proof
from swarm_engine.workflow_checkpoint import WorkflowCheckpointStore


def _grant(run_id: str, nodes: list[str]) -> dict:
    grant = {
        "admission_id": f"adm-{run_id}",
        "status": "admitted",
        "workflow_run_id": run_id,
        "trace_id": run_id,
        "backend": "aetherforge",
        "step_run_ids": [f"{run_id}:{node}" for node in nodes],
        "capabilities": ["execute"],
        "policy_digest": "policy-test",
        "issued_at": datetime.now(UTC).isoformat(),
        "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
    }
    grant["proof"] = admission_proof(grant)
    return grant


def test_graph_workflow_resumes_from_durable_checkpoint(tmp_path) -> None:
    store = WorkflowCheckpointStore(tmp_path / "swarm-checkpoints.jsonl")
    calls: list[str] = []

    first = GraphWorkflow()

    @first.node("prepare")
    def prepare(_state: dict) -> dict:
        calls.append("prepare")
        return {"prepared": True}

    @first.node("execute")
    def execute(_state: dict) -> dict:
        calls.append("execute")
        raise RuntimeError("temporary failure")

    first.add_edge("prepare", "execute")
    first.set_entry("prepare")
    failed = first.run(
        {},
        workflow_run_id="swarm-resume",
        checkpoint_store=store,
        admission=_grant("swarm-resume", ["prepare", "execute"]),
    )
    assert failed["_errors"]

    second = GraphWorkflow()

    @second.node("prepare")
    def prepare_again(_state: dict) -> dict:
        calls.append("prepare-again")
        return {"prepared": True}

    @second.node("execute")
    def execute_again(_state: dict) -> dict:
        calls.append("execute-again")
        return {"output": "recovered"}

    second.add_edge("prepare", "execute")
    second.set_entry("prepare")
    recovered = second.run(
        {},
        workflow_run_id="swarm-resume",
        checkpoint_store=store,
        admission=_grant("swarm-resume", ["prepare", "execute"]),
    )

    assert recovered["output"] == "recovered"
    assert calls == ["prepare", "execute", "execute-again"]
