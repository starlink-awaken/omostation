"""Real-ledger public-boundary tests for the W2-05 personal draft slice."""

from __future__ import annotations

import json
from pathlib import Path

from agora.mcp import policy_enforcement
from agora.mcp.policy_enforcement import reset_pep_provider_cache
from fastapi import FastAPI
from fastapi.testclient import TestClient
from omo.event_ledger import LedgerBroker
from omo.sovereignty import SovereigntyService

from cockpit.web import api_workflow_mesh_operations


def _app() -> FastAPI:
    app = FastAPI()
    app.include_router(api_workflow_mesh_operations.router)  # type: ignore[arg-type]
    return app


def _seed_role(ledger_path: Path) -> None:
    broker = LedgerBroker.connect(ledger_path)
    try:
        SovereigntyService(broker).assign(
            "principal:alice",
            "role:personal-steward",
            role_name="Personal Steward",
            scope="personal",
            responsibilities=["follow-up"],
        )
    finally:
        broker.close()


def _start_payload() -> dict[str, str]:
    return {
        "principal_id": "principal:alice",
        "role_id": "role:personal-steward",
        "responsibility_id": "responsibility:follow-up",
        "executor_id": "agent:personal-steward",
        "request_id": "follow-up-001",
        "summary": "Prepare the commitment follow-up",
        "why_now": "The family commitment needs review",
        "deadline": "2026-08-13",
    }


def _draft_payload(episode_id: str) -> dict[str, str]:
    return {
        "episode_id": episode_id,
        "principal_id": "principal:alice",
        "title": "Commitment follow-up draft",
        "context": "Summarise the next step for review.",
        "deadline": "2026-08-13",
        "next_action": "Review, edit, or discard the local draft.",
    }


def _configure_real_local_runtime(monkeypatch, tmp_path: Path) -> tuple[Path, Path]:
    ledger_path = tmp_path / "event-ledger.sqlite3"
    draft_dir = tmp_path / "personal-drafts"
    monkeypatch.setenv("OMO_EVENT_LEDGER_DB", str(ledger_path))
    monkeypatch.setenv("PERSONAL_DRAFT_DIR", str(draft_dir))
    monkeypatch.setenv("AGORA_PEP_PROVIDER", "omo.sovereignty.enforcement:AgoraPepProvider")
    reset_pep_provider_cache()
    return ledger_path, draft_dir


def test_personal_episode_real_ledger_to_local_draft_to_feedback(monkeypatch, tmp_path):
    ledger_path, draft_dir = _configure_real_local_runtime(monkeypatch, tmp_path)
    _seed_role(ledger_path)
    client = TestClient(_app())

    started = client.post("/api/workflow-mesh/personal-episode/start", json=_start_payload())
    assert started.status_code == 200
    episode_id = started.json()["episode"]["episode_id"]

    inbox = client.get("/api/workflow-mesh/episode-projections", params={"principal_id": "principal:alice"})
    assert inbox.status_code == 200
    assert inbox.json()["ok"] is True
    assert any(card["episode"] == episode_id for card in inbox.json()["projection"]["inbox"])

    confirmed = client.post(
        "/api/workflow-mesh/personal-episode/confirm",
        json={
            "episode_id": episode_id,
            "principal_id": "principal:alice",
            "executor_id": "agent:personal-steward",
            "human_confirmed": True,
        },
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["confirmation"]["mandate_id"].startswith("mandate:personal-")

    executed = client.post("/api/workflow-mesh/personal-episode/execute", json=_draft_payload(episode_id))
    assert executed.status_code == 200
    evidence_uri = executed.json()["evidence_uri"]
    assert evidence_uri.startswith("file://")
    artifacts = list(draft_dir.glob("*.json"))
    assert len(artifacts) == 1
    artifact = json.loads(artifacts[0].read_text(encoding="utf-8"))
    assert artifact == {
        "title": "Commitment follow-up draft",
        "context": "Summarise the next step for review.",
        "deadline": "2026-08-13",
        "next_action": "Review, edit, or discard the local draft.",
        "never_send": True,
    }

    feedback = client.post(
        "/api/workflow-mesh/personal-episode/feedback",
        json={"episode_id": episode_id, "principal_id": "principal:alice", "verdict": "accept"},
    )
    assert feedback.status_code == 200

    projection = client.get("/api/workflow-mesh/episode-projections", params={"principal_id": "principal:alice"})
    assert projection.status_code == 200
    snapshot = projection.json()["projection"]
    episode = next(item for item in snapshot["episodes"] if item["episode_id"] == episode_id)
    member_payloads = [member["payload"] for member in episode["contains_event_refs"]]
    assert any(payload.get("evidence_uri") == evidence_uri for payload in member_payloads)
    assert any(payload.get("verdict") == "accept" for payload in member_payloads)
    assert snapshot["controls"]["ledger_unchanged"] is True
    assert snapshot["controls"]["chain_after"]["ok"] is True

    broker = LedgerBroker.connect(ledger_path)
    try:
        event_types = {row["event_type"] for row in broker.read(episode_id=episode_id)}
        assert {"Action.Started.v1", "Action.Succeeded.v1", "Evidence.LocalDraft.v1", "Outcome.Human.v1"} <= event_types
        assert broker.verify_chain()["ok"] is True
    finally:
        broker.close()


def test_personal_episode_execute_requires_confirmation_and_creates_no_file(monkeypatch, tmp_path):
    ledger_path, draft_dir = _configure_real_local_runtime(monkeypatch, tmp_path)
    _seed_role(ledger_path)
    client = TestClient(_app())
    started = client.post("/api/workflow-mesh/personal-episode/start", json=_start_payload())
    episode_id = started.json()["episode"]["episode_id"]

    response = client.post("/api/workflow-mesh/personal-episode/execute", json=_draft_payload(episode_id))

    assert response.status_code == 409
    assert response.json()["ok"] is False
    assert list(draft_dir.glob("*.json")) == [] if draft_dir.exists() else True


def test_personal_episode_repeated_start_uses_fresh_closed_request_brokers(monkeypatch, tmp_path):
    ledger_path, _draft_dir = _configure_real_local_runtime(monkeypatch, tmp_path)
    _seed_role(ledger_path)
    client = TestClient(_app())

    first = client.post("/api/workflow-mesh/personal-episode/start", json=_start_payload())
    second = client.post("/api/workflow-mesh/personal-episode/start", json=_start_payload())

    assert first.status_code == second.status_code == 200
    assert first.json()["episode"]["episode_id"] == second.json()["episode"]["episode_id"]
    assert second.json()["episode"]["reused"] is True


def test_personal_episode_missing_provider_binding_replaces_cached_none(monkeypatch, tmp_path):
    ledger_path, _draft_dir = _configure_real_local_runtime(monkeypatch, tmp_path)
    _seed_role(ledger_path)
    client = TestClient(_app())
    started = client.post("/api/workflow-mesh/personal-episode/start", json=_start_payload())
    episode_id = started.json()["episode"]["episode_id"]
    confirmed = client.post(
        "/api/workflow-mesh/personal-episode/confirm",
        json={
            "episode_id": episode_id,
            "principal_id": "principal:alice",
            "executor_id": "agent:personal-steward",
            "human_confirmed": True,
        },
    )
    assert confirmed.status_code == 200

    monkeypatch.delenv("AGORA_PEP_PROVIDER")
    monkeypatch.setattr(policy_enforcement, "_provider_cache", None)
    executed = client.post("/api/workflow-mesh/personal-episode/execute", json=_draft_payload(episode_id))

    assert executed.status_code == 200
    assert executed.json()["ok"] is True
    assert policy_enforcement.get_pep_provider() is not None


def test_personal_episode_pep_failure_creates_no_file(monkeypatch, tmp_path):
    ledger_path, draft_dir = _configure_real_local_runtime(monkeypatch, tmp_path)
    _seed_role(ledger_path)
    client = TestClient(_app())
    started = client.post("/api/workflow-mesh/personal-episode/start", json=_start_payload())
    episode_id = started.json()["episode"]["episode_id"]
    confirmed = client.post(
        "/api/workflow-mesh/personal-episode/confirm",
        json={
            "episode_id": episode_id,
            "principal_id": "principal:alice",
            "executor_id": "agent:personal-steward",
            "human_confirmed": True,
        },
    )
    assert confirmed.status_code == 200

    monkeypatch.setenv("AGORA_PEP_PROVIDER", "not.a.real.provider:Provider")
    reset_pep_provider_cache()
    response = client.post("/api/workflow-mesh/personal-episode/execute", json=_draft_payload(episode_id))

    assert response.status_code == 409
    assert response.json()["ok"] is False
    assert list(draft_dir.glob("*.json")) == [] if draft_dir.exists() else True
