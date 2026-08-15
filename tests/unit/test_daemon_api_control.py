from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import httpx
import pytest

from omlxc.api import create_app
from omlxc.daemon import DaemonRuntime
from omlxc.domain import (
    HealthSnapshot,
    Job,
    JobState,
    ModelSpec,
    Node,
    NodeState,
    RiskLevel,
    RouteDecision,
    RouteRequest,
)


class FakeControlService:
    def __init__(self) -> None:
        now = datetime(2026, 8, 11, tzinfo=UTC)
        self.node = Node(
            id="mbp",
            display_name="MBP",
            platform="macos",
            health=HealthSnapshot(
                state=NodeState.HEALTHY,
                observed_at=now,
                stale=False,
            ),
        )
        self.model = ModelSpec(id="local/model", role="chat", aliases=frozenset({"legacy/model"}))
        self.job = Job(
            id="job-1",
            kind="load",
            initiator="api",
            risk=RiskLevel.R1,
            state=JobState.PENDING,
            progress=0,
            created_at=now,
            updated_at=now,
        )
        self.load_calls: list[tuple[str, str]] = []
        self.unload_calls: list[tuple[str, str]] = []
        self.route_requests: list[RouteRequest] = []
        self.probe_calls: list[str] = []
        self.diagnostic_calls: list[str] = []

    async def health(self) -> dict[str, Any]:
        return {"status": "ready", "degraded": False}

    async def list_nodes(self, *, after: str | None, limit: int) -> tuple[Node, ...]:
        assert limit <= 100
        return () if after == self.node.id else (self.node,)

    async def list_models(self, *, after: str | None, limit: int) -> tuple[ModelSpec, ...]:
        assert limit <= 100
        return () if after == self.model.id else (self.model,)

    async def resolve_model(self, model_id: str) -> ModelSpec | None:
        if model_id == self.model.id or model_id in self.model.aliases:
            return self.model
        return None

    async def probe_node(self, node_id: str) -> Node | None:
        self.probe_calls.append(node_id)
        return self.node if node_id == self.node.id else None

    async def diagnose_node(self, node_id: str) -> dict[str, object] | None:
        self.diagnostic_calls.append(node_id)
        if node_id != self.node.id:
            return None
        return {
            "node": self.node,
            "outcomes": ({"code": "available", "count": 1},),
        }

    async def plan_route(self, request: RouteRequest) -> RouteDecision:
        request_id = request.request_id
        self.route_requests.append(request)
        return RouteDecision(
            request_id=request_id,
            selected_placement_id="placement-a",
            candidates=("placement-a",),
            candidate_scores={"placement-a": 1.0},
            rejected={},
            fallback_chain=("placement-a",),
            config_version="v1",
            explanation="local candidate selected",
        )

    async def list_jobs(self, *, after: str | None, limit: int) -> tuple[Job, ...]:
        assert limit <= 100
        return () if after == self.job.id else (self.job,)

    async def get_job(self, job_id: str) -> Job | None:
        return self.job if job_id == self.job.id else None

    async def load_model(self, model_id: str, *, idempotency_key: str) -> Job:
        self.load_calls.append((model_id, idempotency_key))
        return self.job

    async def unload_model(self, model_id: str, *, idempotency_key: str) -> Job:
        self.unload_calls.append((model_id, idempotency_key))
        return self.job.model_copy(update={"kind": "unload"})

    async def cancel_job(self, job_id: str) -> Job | None:
        if job_id != self.job.id:
            return None
        return self.job.model_copy(update={"state": JobState.CANCELLING})

    async def metrics_summary(self) -> dict[str, Any]:
        return {"requests": 4, "errors": 0}


@pytest.fixture
def control() -> FakeControlService:
    return FakeControlService()


@pytest.fixture
def transport(control: FakeControlService) -> httpx.ASGITransport:
    return httpx.ASGITransport(app=create_app(control=control))


@pytest.mark.asyncio
async def test_health_envelope_and_valid_client_request_id(
    transport: httpx.ASGITransport,
) -> None:
    async with httpx.AsyncClient(transport=transport, base_url="http://omlxc") as client:
        response = await client.get(
            "/api/v1/health", headers={"X-OMLXC-Request-ID": "client.req-1"}
        )

    assert response.status_code == 200
    assert response.headers["X-OMLXC-Request-ID"] == "client.req-1"
    assert response.json() == {
        "schema_version": 1,
        "request_id": "client.req-1",
        "data": {"status": "ready", "degraded": False},
    }


@pytest.mark.asyncio
async def test_invalid_request_id_and_validation_errors_are_sanitized(
    transport: httpx.ASGITransport,
) -> None:
    async with httpx.AsyncClient(transport=transport, base_url="http://omlxc") as client:
        invalid_id = await client.get(
            "/api/v1/health", headers={"X-OMLXC-Request-ID": "bad secret\nvalue"}
        )
        invalid_body = await client.post(
            "/api/v1/routes/plan",
            json={"model_id": "", "prompt": "must-not-echo", "unknown": "api_key=bad"},
        )

    assert invalid_id.status_code == 400
    assert invalid_body.status_code == 422
    encoded = invalid_id.text + invalid_body.text
    assert "must-not-echo" not in encoded
    assert "api_key=bad" not in encoded
    for response in (invalid_id, invalid_body):
        payload = response.json()
        assert payload["schema_version"] == 1
        assert payload["error"]["code"]
        assert "traceback" not in response.text.lower()


@pytest.mark.asyncio
async def test_control_queries_are_paginated_and_stably_shaped(
    transport: httpx.ASGITransport,
) -> None:
    async with httpx.AsyncClient(transport=transport, base_url="http://omlxc") as client:
        nodes = await client.get("/api/v1/nodes?limit=100")
        models = await client.get("/api/v1/models?limit=100")
        jobs = await client.get("/api/v1/jobs?limit=100")
        metrics = await client.get("/api/v1/metrics/summary")

    assert nodes.json()["data"]["items"][0]["id"] == "mbp"
    assert models.json()["data"]["items"][0]["id"] == "local/model"
    assert jobs.json()["data"]["items"][0]["id"] == "job-1"
    assert metrics.json()["data"] == {"requests": 4, "errors": 0}


@pytest.mark.asyncio
async def test_node_probe_returns_the_refreshed_node_or_a_safe_not_found(
    transport: httpx.ASGITransport, control: FakeControlService
) -> None:
    async with httpx.AsyncClient(transport=transport, base_url="http://omlxc") as client:
        refreshed = await client.post("/api/v1/nodes/mbp/probe")
        missing = await client.post("/api/v1/nodes/missing/probe")

    assert refreshed.status_code == 200
    assert refreshed.json()["data"]["id"] == "mbp"
    assert missing.status_code == 404
    assert missing.json()["error"] == {
        "code": "E404",
        "message": "node not found",
        "retryable": False,
    }
    assert control.probe_calls == ["mbp", "missing"]


@pytest.mark.asyncio
async def test_node_diagnostics_are_read_only_and_return_safe_aggregate_outcomes(
    transport: httpx.ASGITransport, control: FakeControlService
) -> None:
    async with httpx.AsyncClient(transport=transport, base_url="http://omlxc") as client:
        diagnosed = await client.get("/api/v1/nodes/mbp/diagnostics")
        missing = await client.get("/api/v1/nodes/missing/diagnostics")

    assert diagnosed.status_code == 200
    assert diagnosed.json()["data"] == {
        "node": {
            "id": "mbp",
            "display_name": "MBP",
            "platform": "macos",
            "tailscale_identity": None,
            "control_endpoint": None,
            "inference_endpoints": [],
            "capabilities": [],
            "memory_gb": None,
            "health": {
                "state": "healthy",
                "observed_at": "2026-08-11T00:00:00Z",
                "stale": False,
                "detail": None,
            },
            "fresh": None,
            "authorized": None,
            "available": None,
            "loaded": None,
            "ready": None,
            "last_observed_at": None,
        },
        "outcomes": [{"code": "available", "count": 1}],
    }
    assert missing.status_code == 404
    assert control.diagnostic_calls == ["mbp", "missing"]
    assert control.probe_calls == []


@pytest.mark.asyncio
async def test_load_unload_and_cancel_return_durable_job_with_202(
    transport: httpx.ASGITransport, control: FakeControlService
) -> None:
    async with httpx.AsyncClient(transport=transport, base_url="http://omlxc") as client:
        first = await client.post(
            "/api/v1/models/local%2Fmodel/load",
            headers={"Idempotency-Key": "load-1"},
        )
        repeated = await client.post(
            "/api/v1/models/local%2Fmodel/load",
            headers={"Idempotency-Key": "load-1"},
        )
        unload = await client.post(
            "/api/v1/models/local%2Fmodel/unload",
            headers={"Idempotency-Key": "unload-1"},
        )
        cancelled = await client.post("/api/v1/jobs/job-1/cancel")

    assert first.status_code == repeated.status_code == unload.status_code == 202
    assert first.json()["data"]["state"] == "pending"
    assert repeated.json()["data"]["id"] == first.json()["data"]["id"]
    assert control.load_calls == [("local/model", "load-1"), ("local/model", "load-1")]
    assert cancelled.status_code == 202
    assert cancelled.json()["data"]["state"] == "cancelling"


@pytest.mark.asyncio
async def test_route_plan_resolves_alias_to_canonical_model(
    transport: httpx.ASGITransport, control: FakeControlService
) -> None:
    async with httpx.AsyncClient(transport=transport, base_url="http://omlxc") as client:
        planned = await client.post(
            "/api/v1/routes/plan",
            json={
                "model_id": "legacy/model",
                "profile": "quality",
                "required_capabilities": ["embedding"],
                "context_tokens": 0,
                "thinking_requested": False,
            },
        )

    assert planned.status_code == 200
    assert planned.json()["data"]["selected_placement_id"] == "placement-a"
    assert control.route_requests[0].model_id == "local/model"


@pytest.mark.asyncio
async def test_load_and_unload_resolve_aliases_and_unknown_model_is_404(
    transport: httpx.ASGITransport, control: FakeControlService
) -> None:
    async with httpx.AsyncClient(transport=transport, base_url="http://omlxc") as client:
        loaded = await client.post(
            "/api/v1/models/legacy%2Fmodel/load",
            headers={"Idempotency-Key": "load-1"},
        )
        unloaded = await client.post(
            "/api/v1/models/legacy%2Fmodel/unload",
            headers={"Idempotency-Key": "unload-1"},
        )
        missing_route = await client.post("/api/v1/routes/plan", json={"model_id": "missing/model"})
        missing_load = await client.post(
            "/api/v1/models/missing%2Fmodel/load",
            headers={"Idempotency-Key": "missing"},
        )

    assert loaded.status_code == 202
    assert unloaded.status_code == 202
    assert loaded.json()["data"]["id"] == "job-1"
    assert unloaded.json()["data"]["kind"] == "unload"
    assert control.load_calls == [("local/model", "load-1")]
    assert control.unload_calls == [("local/model", "unload-1")]
    assert missing_route.status_code == 404
    assert missing_load.status_code == 404
    assert missing_route.json()["error"]["code"] == "E404"
    assert missing_load.json()["error"]["code"] == "E404"
    assert missing_route.json()["error"]["message"] == "model not configured"
    assert missing_load.json()["error"]["message"] == "model not configured"


@pytest.mark.asyncio
async def test_missing_job_and_page_limit_have_typed_status(
    transport: httpx.ASGITransport,
) -> None:
    async with httpx.AsyncClient(transport=transport, base_url="http://omlxc") as client:
        missing = await client.get("/api/v1/jobs/missing")
        excessive = await client.get("/api/v1/nodes?limit=101")

    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "E204"
    assert excessive.status_code == 422


class LifecycleStep:
    def __init__(self, name: str, calls: list[str], *, fail: bool = False) -> None:
        self.name = name
        self.calls = calls
        self.fail = fail

    async def start(self) -> None:
        self.calls.append(f"start:{self.name}")
        if self.fail:
            raise RuntimeError("secret startup detail")

    async def close(self) -> None:
        self.calls.append(f"close:{self.name}")


@pytest.mark.asyncio
async def test_runtime_startup_and_shutdown_are_ordered_idempotent_and_fail_closed() -> None:
    calls: list[str] = []
    runtime = DaemonRuntime(
        config_runtime=LifecycleStep("config", calls),
        recovery=LifecycleStep("recovery", calls),
        event_runtime=LifecycleStep("events", calls),
    )
    await runtime.start()
    assert runtime.ready
    await runtime.close()
    await runtime.close()
    assert calls == [
        "start:config",
        "start:recovery",
        "start:events",
        "close:events",
        "close:recovery",
        "close:config",
    ]

    failed_calls: list[str] = []
    failed = DaemonRuntime(
        config_runtime=LifecycleStep("config", failed_calls),
        recovery=LifecycleStep("recovery", failed_calls, fail=True),
        event_runtime=LifecycleStep("events", failed_calls),
    )
    with pytest.raises(RuntimeError, match="daemon runtime startup failed"):
        await failed.start()
    assert not failed.ready
    assert failed.diagnostic == "runtime_startup_failed"
    assert failed_calls == ["start:config", "start:recovery", "close:config"]
