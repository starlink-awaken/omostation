from agora.workflow_health import build_capability_health_snapshot


def test_capability_health_projects_green_worker() -> None:
    result = build_capability_health_snapshot(
        ["runtime", "workflow.execute"],
        agents=[
            {
                "agent_id": "worker-1",
                "capabilities": ["runtime", "workflow.execute"],
                "status": "active",
            }
        ],
    )

    assert result["status"] == "healthy"
    assert result["capabilities"]["runtime"]["available"] is True
    assert result["capabilities"]["runtime"]["sources"][0]["id"] == "worker-1"


def test_capability_health_keeps_degraded_worker_available() -> None:
    result = build_capability_health_snapshot(
        ["runtime"],
        nodes=[
            {
                "node_id": "node-1",
                "capabilities": {"runtime": {}},
                "status": "yellow",
            }
        ],
    )

    assert result["status"] == "degraded"
    assert result["capabilities"]["runtime"] == {
        "available": True,
        "health": "yellow",
        "sources": [{"source": "swarm_node", "id": "node-1", "health": "yellow"}],
    }


def test_capability_health_marks_missing_capability_unhealthy() -> None:
    result = build_capability_health_snapshot(["runtime"], agents=[])

    assert result["status"] == "unhealthy"
    assert result["capabilities"]["runtime"]["available"] is False
