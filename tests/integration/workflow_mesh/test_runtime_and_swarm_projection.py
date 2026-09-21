from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]

# swarm_engine 现位于 agora 内嵌的 aetherforge packages 下
# (projects/agora/projects/aetherforge/packages/swarm/src); 旧布局的
# projects/aetherforge/packages/swarm/src 保留为兜底。
_SWARM_CANDIDATES = (
    ROOT / "projects" / "agora" / "projects" / "aetherforge" / "packages" / "swarm" / "src",
    ROOT / "projects" / "aetherforge" / "packages" / "swarm" / "src",
)
for source in (
    ROOT / "projects" / "omo" / "src",
    ROOT / "projects" / "runtime" / "src",
    *[p for p in _SWARM_CANDIDATES if p.is_dir()],
):
    if str(source) not in sys.path:
        sys.path.insert(0, str(source))

# 仓库根同时存在 `bin/runtime/` 与 `runtime/`, 当 `bin` 在 sys.path 上时 Python 会把
# `runtime` 解析成**命名空间包** (无 __file__) 并缓存 —— 之后即便插入真实路径,
# `runtime.executor` 仍无法解析 (实测: 全量收集时报 ModuleNotFoundError)。
# 故导入真实包前清掉该伪条目。
_cached_runtime = sys.modules.get("runtime")
if _cached_runtime is not None and getattr(_cached_runtime, "__file__", None) is None:
    del sys.modules["runtime"]

# runtime / swarm_engine 来自子模块。未物化时 pytest 会因模块级 import 缺失直接
# 中断运行 —— 缺依赖时优雅跳过 (与 tests/test_scene_outcome_episode_bridge.py 同模式)。
pytest.importorskip("runtime.executor.engine", reason="需 projects/runtime 子模块")
pytest.importorskip("swarm_engine.graph_workflow", reason="需 projects/aetherforge 子模块")


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
