"""Real-ledger public-boundary tests for the W2-05 personal draft slice."""

from __future__ import annotations

import hashlib
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
    executed_body = executed.json()
    assert executed_body["local_draft_recorded"] is True
    assert "evidence_uri" not in executed_body
    artifacts = list(draft_dir.glob("*.json"))
    assert len(artifacts) == 1
    candidate_digest = hashlib.sha256(artifacts[0].read_bytes()).hexdigest()
    evidence_uri = f"evidence://personal-draft/sha256:{candidate_digest}"
    artifact = json.loads(artifacts[0].read_text(encoding="utf-8"))
    assert artifact == {
        "title": "Commitment follow-up draft",
        "context": "Summarise the next step for review.",
        "deadline": "2026-08-13",
        "next_action": "Review, edit, or discard the local draft.",
        "never_send": True,
        "output_origin": "user_provided",
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
    assert any(payload.get("verdict") == "accept" for payload in member_payloads)
    projection_text = json.dumps(snapshot)
    assert evidence_uri not in projection_text
    assert str(draft_dir) not in projection_text
    assert "file://" not in projection_text
    assert snapshot["controls"]["ledger_unchanged"] is True
    assert snapshot["controls"]["chain_after"]["ok"] is True

    broker = LedgerBroker.connect(ledger_path)
    try:
        event_types = {row["event_type"] for row in broker.read(episode_id=episode_id)}
        assert {"Action.Started.v1", "Action.Succeeded.v1", "Evidence.LocalDraft.v1", "Outcome.Human.v1"} <= event_types
        evidence_rows = [
            json.loads(row["payload_json"])
            for row in broker.read(episode_id=episode_id)
            if row["event_type"] == "Evidence.LocalDraft.v1"
        ]
        assert len(evidence_rows) == 1
        assert evidence_rows[0]["evidence_uri"] == evidence_uri
        assert evidence_rows[0]["output_origin"] == "user_provided"
        assert evidence_rows[0]["action_id"].startswith("action:personal-")
        rows = broker.read(episode_id=episode_id)
        serialized_rows = json.dumps(rows)
        assert str(tmp_path) not in serialized_rows
        assert "file://" not in serialized_rows
        outcome_payload = next(
            json.loads(row["payload_json"]) for row in rows if row["event_type"] == "Outcome.Human.v1"
        )
        assert outcome_payload["outcome_feedback_schema"] == "outcome-feedback/v1"
        assert outcome_payload["revision_receipt"] == {
            "schema": "revision-receipt/v1",
            "candidate_ref": evidence_uri,
            "revision_digest": f"sha256:{candidate_digest}",
            "changed_fields": [],
        }
        assert broker.verify_chain()["ok"] is True
    finally:
        broker.close()


def test_feedback_edit_without_revision_receipt_fails_closed(monkeypatch, tmp_path):
    ledger_path, _ = _configure_real_local_runtime(monkeypatch, tmp_path)
    client = TestClient(_app())
    episode_id = _full_flow_episode(client, ledger_path)

    broker = LedgerBroker.connect(ledger_path)
    count_before = broker.count()
    broker.close()

    feedback = client.post(
        "/api/workflow-mesh/personal-episode/feedback",
        json={
            "episode_id": episode_id,
            "principal_id": "principal:alice",
            "verdict": "edit",
        },
    )

    assert feedback.status_code == 409
    assert feedback.json()["error"] == "revision_receipt_required"
    broker = LedgerBroker.connect(ledger_path)
    try:
        assert broker.count() == count_before
        assert not [row for row in broker.read(episode_id=episode_id) if row["event_type"] == "Outcome.Human.v1"]
    finally:
        broker.close()


# ── W3-01B extension: optional burden metrics, ignore verdict, status observation ─


def _full_flow_episode(client, ledger_path) -> str:
    """Run setup → start → confirm → execute and return episode_id."""
    _seed_role(ledger_path)
    started = client.post("/api/workflow-mesh/personal-episode/start", json=_start_payload())
    assert started.status_code == 200
    episode_id = started.json()["episode"]["episode_id"]
    assert (
        client.post(
            "/api/workflow-mesh/personal-episode/confirm",
            json={
                "episode_id": episode_id,
                "principal_id": "principal:alice",
                "executor_id": "agent:personal-steward",
                "human_confirmed": True,
            },
        ).status_code
        == 200
    )
    assert (
        client.post("/api/workflow-mesh/personal-episode/execute", json=_draft_payload(episode_id)).status_code == 200
    )
    return episode_id


def test_feedback_with_optional_burden_metrics(monkeypatch, tmp_path):
    """Feedback with review_duration_seconds and estimated_time_saved_seconds persists."""
    ledger_path, _ = _configure_real_local_runtime(monkeypatch, tmp_path)
    client = TestClient(_app())
    episode_id = _full_flow_episode(client, ledger_path)

    feedback = client.post(
        "/api/workflow-mesh/personal-episode/feedback",
        json={
            "episode_id": episode_id,
            "principal_id": "principal:alice",
            "verdict": "accept",
            "review_duration_seconds": 120.0,
            "estimated_time_saved_seconds": 600.0,
        },
    )
    assert feedback.status_code == 200
    assert feedback.json()["ok"] is True

    # Verify the burden values are in the ledger event payload.
    broker = LedgerBroker.connect(ledger_path)
    try:
        outcome_rows = [row for row in broker.read(episode_id=episode_id) if row["event_type"] == "Outcome.Human.v1"]
        assert len(outcome_rows) == 1
        payload = json.loads(outcome_rows[0]["payload_json"])
        assert payload["review_duration_seconds"] == 120.0
        assert payload["estimated_time_saved_seconds"] == 600.0
    finally:
        broker.close()


def test_feedback_id_revisions_are_idempotent_and_latest_is_effective(monkeypatch, tmp_path):
    """Stable request IDs dedupe replays while newer feedback revises the outcome."""
    ledger_path, _ = _configure_real_local_runtime(monkeypatch, tmp_path)
    client = TestClient(_app())
    episode_id = _full_flow_episode(client, ledger_path)

    def submit(feedback_id: str, verdict: str, **metrics):
        return client.post(
            "/api/workflow-mesh/personal-episode/feedback",
            json={
                "episode_id": episode_id,
                "principal_id": "principal:alice",
                "feedback_id": feedback_id,
                "verdict": verdict,
                **metrics,
            },
        )

    first = submit("feedback:http-001", "accept")
    replay = submit("feedback:http-001", "accept")
    rejected = submit("feedback:http-002", "reject")
    accepted = submit("feedback:http-003", "accept")
    supplemented = submit(
        "feedback:http-004",
        "accept",
        review_duration_seconds=30,
        estimated_time_saved_seconds=300,
    )

    assert [response.status_code for response in (first, replay, rejected, accepted, supplemented)] == [
        200,
        200,
        200,
        200,
        200,
    ]
    assert replay.json()["sequence"] == first.json()["sequence"]

    broker = LedgerBroker.connect(ledger_path)
    try:
        outcome_payloads = [
            json.loads(row["payload_json"])
            for row in broker.read(episode_id=episode_id)
            if row["event_type"] == "Outcome.Human.v1"
        ]
        raw_ids = [f"feedback:http-00{index}" for index in range(1, 5)]
        assert [payload["feedback_id"] for payload in outcome_payloads] == [
            f"feedback://sha256:{hashlib.sha256(value.encode()).hexdigest()}" for value in raw_ids
        ]
        assert all(value not in json.dumps(outcome_payloads) for value in raw_ids)
    finally:
        broker.close()

    status = client.get(
        "/api/workflow-mesh/personal-episode/status",
        params={"principal_id": "principal:alice"},
    )
    observation = status.json()["observation"]
    assert observation["verdict_distribution"] == {"accept": 1}
    assert observation["weekly_samples"][0]["complete_burden_episodes"] == 1
    assert observation["weekly_samples"][0]["summed_review_seconds"] == 30
    assert observation["weekly_samples"][0]["summed_saved_seconds"] == 300


def test_feedback_id_invalid_value_fails_closed_without_write(monkeypatch, tmp_path):
    ledger_path, _ = _configure_real_local_runtime(monkeypatch, tmp_path)
    client = TestClient(_app())
    episode_id = _full_flow_episode(client, ledger_path)

    broker = LedgerBroker.connect(ledger_path)
    count_before = broker.count()
    broker.close()

    response = client.post(
        "/api/workflow-mesh/personal-episode/feedback",
        json={
            "episode_id": episode_id,
            "principal_id": "principal:alice",
            "feedback_id": "   ",
            "verdict": "accept",
        },
    )

    assert response.status_code == 409
    broker = LedgerBroker.connect(ledger_path)
    try:
        assert broker.count() == count_before
    finally:
        broker.close()


def test_feedback_id_conflicting_replay_returns_409_without_write(monkeypatch, tmp_path):
    ledger_path, _ = _configure_real_local_runtime(monkeypatch, tmp_path)
    client = TestClient(_app())
    episode_id = _full_flow_episode(client, ledger_path)
    request = {
        "episode_id": episode_id,
        "principal_id": "principal:alice",
        "feedback_id": "feedback:http-conflict",
        "verdict": "accept",
        "review_duration_seconds": 10,
        "estimated_time_saved_seconds": 100,
    }
    first = client.post("/api/workflow-mesh/personal-episode/feedback", json=request)

    broker = LedgerBroker.connect(ledger_path)
    count_before = broker.count()
    broker.close()
    conflicting = client.post(
        "/api/workflow-mesh/personal-episode/feedback",
        json={**request, "verdict": "reject"},
    )

    assert first.status_code == 200
    assert conflicting.status_code == 409
    broker = LedgerBroker.connect(ledger_path)
    try:
        assert broker.count() == count_before
    finally:
        broker.close()


def test_feedback_ignore_verdict(monkeypatch, tmp_path):
    """The 'ignore' verdict is accepted and persisted."""
    ledger_path, _ = _configure_real_local_runtime(monkeypatch, tmp_path)
    client = TestClient(_app())
    episode_id = _full_flow_episode(client, ledger_path)

    feedback = client.post(
        "/api/workflow-mesh/personal-episode/feedback",
        json={"episode_id": episode_id, "principal_id": "principal:alice", "verdict": "ignore"},
    )
    assert feedback.status_code == 200
    assert feedback.json()["ok"] is True

    broker = LedgerBroker.connect(ledger_path)
    try:
        outcome_rows = [row for row in broker.read(episode_id=episode_id) if row["event_type"] == "Outcome.Human.v1"]
        assert len(outcome_rows) == 1
        payload = json.loads(outcome_rows[0]["payload_json"])
        assert payload["verdict"] == "ignore"
    finally:
        broker.close()


def test_feedback_omitted_metrics_persisted_as_null(monkeypatch, tmp_path):
    """When metrics are omitted, the ledger payload stores null for both."""
    ledger_path, _ = _configure_real_local_runtime(monkeypatch, tmp_path)
    client = TestClient(_app())
    episode_id = _full_flow_episode(client, ledger_path)

    feedback = client.post(
        "/api/workflow-mesh/personal-episode/feedback",
        json={"episode_id": episode_id, "principal_id": "principal:alice", "verdict": "accept"},
    )
    assert feedback.status_code == 200

    broker = LedgerBroker.connect(ledger_path)
    try:
        outcome_rows = [row for row in broker.read(episode_id=episode_id) if row["event_type"] == "Outcome.Human.v1"]
        assert len(outcome_rows) == 1
        payload = json.loads(outcome_rows[0]["payload_json"])
        assert payload["review_duration_seconds"] is None
        assert payload["estimated_time_saved_seconds"] is None
    finally:
        broker.close()


def test_feedback_invalid_metric_no_write(monkeypatch, tmp_path):
    """Negative, NaN, inf, or non-numeric burden values do not write to the ledger."""
    ledger_path, _ = _configure_real_local_runtime(monkeypatch, tmp_path)
    client = TestClient(_app())
    episode_id = _full_flow_episode(client, ledger_path)

    broker = LedgerBroker.connect(ledger_path)
    count_before = broker.count()
    broker.close()

    # Exercise all boundary classes, including Python's non-standard JSON
    # NaN/Infinity values accepted by the test transport.
    invalid_values = [
        {"review_duration_seconds": -1.0},
        {"review_duration_seconds": True},
        {"estimated_time_saved_seconds": -5.0},
        {"estimated_time_saved_seconds": "not-a-number"},
    ]
    for invalid in invalid_values:
        body = {"episode_id": episode_id, "principal_id": "principal:alice", "verdict": "accept"}
        body.update(invalid)
        resp = client.post("/api/workflow-mesh/personal-episode/feedback", json=body)
        assert resp.status_code == 409
        assert resp.json()["ok"] is False

    # The regular HTTP client rejects non-standard JSON before the route; send
    # raw JSON so the server boundary itself proves NaN/Infinity are blocked.
    for invalid in (float("nan"), float("inf"), float("-inf")):
        body = {
            "episode_id": episode_id,
            "principal_id": "principal:alice",
            "verdict": "accept",
            "review_duration_seconds": invalid,
        }
        resp = client.post(
            "/api/workflow-mesh/personal-episode/feedback",
            content=json.dumps(body, allow_nan=True),
            headers={"content-type": "application/json"},
        )
        assert resp.status_code == 409
        assert resp.json()["ok"] is False

    broker = LedgerBroker.connect(ledger_path)
    try:
        assert broker.count() == count_before
        outcome_rows = [row for row in broker.read(episode_id=episode_id) if row["event_type"] == "Outcome.Human.v1"]
        assert len(outcome_rows) == 0
        assert broker.verify_chain()["ok"] is True
    finally:
        broker.close()


def test_status_returns_omo_observation(monkeypatch, tmp_path):
    """GET /status includes OMO read-only observation with readiness and gaps."""
    ledger_path, _ = _configure_real_local_runtime(monkeypatch, tmp_path)
    client = TestClient(_app())
    episode_id = _full_flow_episode(client, ledger_path)

    # Record one outcome to seed the observation
    client.post(
        "/api/workflow-mesh/personal-episode/feedback",
        json={"episode_id": episode_id, "principal_id": "principal:alice", "verdict": "accept"},
    )

    status = client.get(
        "/api/workflow-mesh/personal-episode/status",
        params={"principal_id": "principal:alice"},
    )
    assert status.status_code == 200
    body = status.json()
    assert body["ok"] is True
    assert "observation" in body
    obs = body["observation"]
    assert obs["principal_id"] == "principal:alice"
    assert obs["readiness"] in ("not_ready", "collecting", "passed")
    assert obs["total_episodes"] >= 1
    assert isinstance(obs["verdict_distribution"], dict)
    assert "accept" in obs["verdict_distribution"]
    assert isinstance(obs["gate_gaps"], list)
    assert isinstance(obs["weekly_samples"], list)
    # Privacy: no raw content, paths, or source URIs in observation
    obs_text = json.dumps(obs)
    assert "file://" not in obs_text
    assert "iris://" not in obs_text


def test_status_ledger_unchanged(monkeypatch, tmp_path):
    """GET /status must not mutate the ledger — count and tail hash stay the same."""
    ledger_path, _ = _configure_real_local_runtime(monkeypatch, tmp_path)
    client = TestClient(_app())
    _full_flow_episode(client, ledger_path)

    broker = LedgerBroker.connect(ledger_path)
    count_before = broker.count()
    rows_before = broker.read()
    tail_hash_before = rows_before[-1]["event_hash"] if rows_before else None
    chain_ok_before = broker.verify_chain()["ok"]
    broker.close()

    status = client.get(
        "/api/workflow-mesh/personal-episode/status",
        params={"principal_id": "principal:alice"},
    )
    assert status.status_code == 200

    broker = LedgerBroker.connect(ledger_path)
    try:
        assert broker.count() == count_before
        rows_after = broker.read()
        tail_hash_after = rows_after[-1]["event_hash"] if rows_after else None
        assert tail_hash_after == tail_hash_before
        assert broker.verify_chain()["ok"] == chain_ok_before
    finally:
        broker.close()


def test_status_observation_failure_is_unavailable(monkeypatch, tmp_path):
    """OMO observation failure is never reported as a live successful status."""
    ledger_path, _ = _configure_real_local_runtime(monkeypatch, tmp_path)
    client = TestClient(_app())
    _full_flow_episode(client, ledger_path)
    monkeypatch.setattr(api_workflow_mesh_operations, "PersonalEpisodeService", None)

    status = client.get(
        "/api/workflow-mesh/personal-episode/status",
        params={"principal_id": "principal:alice"},
    )
    assert status.status_code == 503
    assert status.json() == {
        "ok": False,
        "status": "unavailable",
        "error": "personal_episode_observation_unavailable",
        "principal_id": "principal:alice",
        "read_only": True,
        "workflow_state_mutation": False,
        "provider_invocation": False,
        "automatic_promotion": False,
    }


def test_status_missing_observation_builder_is_unavailable(monkeypatch, tmp_path):
    """A runtime without observe_principal fails closed instead of claiming live."""
    from contextlib import contextmanager

    ledger_path, _ = _configure_real_local_runtime(monkeypatch, tmp_path)
    client = TestClient(_app())
    _full_flow_episode(client, ledger_path)

    @contextmanager
    def _service_without_observation():
        yield object()

    monkeypatch.setattr(
        api_workflow_mesh_operations,
        "_personal_episode_service",
        _service_without_observation,
    )
    status = client.get(
        "/api/workflow-mesh/personal-episode/status",
        params={"principal_id": "principal:alice"},
    )
    assert status.status_code == 503
    assert status.json()["ok"] is False
    assert status.json()["status"] == "unavailable"
    assert status.json()["error"] == "personal_episode_observation_failed"


def test_status_privacy_no_raw_content(monkeypatch, tmp_path):
    """Status response must never contain raw content, paths, digests, or source URIs."""
    ledger_path, _ = _configure_real_local_runtime(monkeypatch, tmp_path)
    client = TestClient(_app())
    episode_id = _full_flow_episode(client, ledger_path)
    client.post(
        "/api/workflow-mesh/personal-episode/feedback",
        json={"episode_id": episode_id, "principal_id": "principal:alice", "verdict": "accept"},
    )

    status = client.get(
        "/api/workflow-mesh/personal-episode/status",
        params={"principal_id": "principal:alice"},
    )
    status_text = status.text
    # No filesystem paths
    assert str(tmp_path) not in status_text
    assert str(ledger_path) not in status_text
    # No source URIs
    assert "iris://local-files/" not in status_text
    # No content hashes (64-char hex digests)
    assert "content_sha256" not in status_text


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
    assert executed.json()["local_draft_recorded"] is True
    assert "evidence_uri" not in executed.json()
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


# ── BET-Y1Q2-T2-02: setup, system draft, status ─────────────────────────


def _configure_runtime_no_seed(monkeypatch, tmp_path: Path) -> tuple[Path, Path]:
    """Like _configure_real_local_runtime but does NOT seed the role."""
    ledger_path = tmp_path / "event-ledger.sqlite3"
    draft_dir = tmp_path / "personal-drafts"
    monkeypatch.setenv("OMO_EVENT_LEDGER_DB", str(ledger_path))
    monkeypatch.setenv("PERSONAL_DRAFT_DIR", str(draft_dir))
    monkeypatch.setenv("AGORA_PEP_PROVIDER", "omo.sovereignty.enforcement:AgoraPepProvider")
    reset_pep_provider_cache()
    return ledger_path, draft_dir


def _setup_payload() -> dict:
    return {
        "principal_id": "principal:alice",
        "role_id": "role:personal-steward",
        "role_name": "Personal Steward",
        "scope": "personal",
        "responsibilities": ["follow-up"],
    }


def test_personal_setup_creates_role_idempotent(monkeypatch, tmp_path):
    """POST /setup creates the assignment; a second call with same params is idempotent."""
    ledger_path, _ = _configure_runtime_no_seed(monkeypatch, tmp_path)
    client = TestClient(_app())

    first = client.post("/api/workflow-mesh/personal-episode/setup", json=_setup_payload())
    assert first.status_code == 200
    assert first.json()["ok"] is True
    assert first.json()["status"] == "assigned"

    broker = LedgerBroker.connect(ledger_path)
    try:
        events_before = broker.read()
        count_before = broker.count()
        tail_hash_before = events_before[-1]["event_hash"]
        assert broker.verify_chain()["ok"] is True
    finally:
        broker.close()

    second = client.post("/api/workflow-mesh/personal-episode/setup", json=_setup_payload())
    assert second.status_code == 200
    assert second.json()["ok"] is True
    assert second.json()["status"] == "already_active"

    broker = LedgerBroker.connect(ledger_path)
    try:
        events_after = broker.read()
        assert broker.count() == count_before
        assert events_after[-1]["event_hash"] == tail_hash_before
        assert broker.verify_chain()["ok"] is True
    finally:
        broker.close()


def test_personal_setup_blocks_conflicting_scope(monkeypatch, tmp_path):
    """An already-active assignment with a different scope must not silently succeed."""
    _configure_runtime_no_seed(monkeypatch, tmp_path)
    client = TestClient(_app())

    client.post("/api/workflow-mesh/personal-episode/setup", json=_setup_payload())

    conflict = _setup_payload()
    conflict["scope"] = "work"
    response = client.post("/api/workflow-mesh/personal-episode/setup", json=conflict)
    assert response.status_code == 409
    assert response.json()["ok"] is False
    assert response.json()["error"] == "scope_conflict"


def test_personal_setup_blocks_conflicting_role_name(monkeypatch, tmp_path):
    """A different role_name on an active assignment is blocked."""
    _configure_runtime_no_seed(monkeypatch, tmp_path)
    client = TestClient(_app())

    client.post("/api/workflow-mesh/personal-episode/setup", json=_setup_payload())

    conflict = _setup_payload()
    conflict["role_name"] = "Different Name"
    response = client.post("/api/workflow-mesh/personal-episode/setup", json=conflict)
    assert response.status_code == 409
    assert response.json()["error"] == "role_name_conflict"


def test_personal_setup_then_full_flow_user_provided(monkeypatch, tmp_path):
    """Setup → Start → Confirm → Execute (full draft) → output_origin=user_provided."""
    _configure_runtime_no_seed(monkeypatch, tmp_path)
    client = TestClient(_app())

    assert client.post("/api/workflow-mesh/personal-episode/setup", json=_setup_payload()).status_code == 200

    started = client.post("/api/workflow-mesh/personal-episode/start", json=_start_payload())
    assert started.status_code == 200
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

    executed = client.post("/api/workflow-mesh/personal-episode/execute", json=_draft_payload(episode_id))
    assert executed.status_code == 200
    assert executed.json()["output_origin"] == "user_provided"
    assert executed.json()["local_draft_recorded"] is True
    assert "evidence_uri" not in executed.json()


def test_personal_execute_system_draft_from_snapshot(monkeypatch, tmp_path):
    """Omitted draft fields → server builds from Episode snapshot, output_origin=system."""
    ledger_path, draft_dir = _configure_runtime_no_seed(monkeypatch, tmp_path)
    client = TestClient(_app())

    client.post("/api/workflow-mesh/personal-episode/setup", json=_setup_payload())
    started = client.post("/api/workflow-mesh/personal-episode/start", json=_start_payload())
    episode_id = started.json()["episode"]["episode_id"]
    client.post(
        "/api/workflow-mesh/personal-episode/confirm",
        json={
            "episode_id": episode_id,
            "principal_id": "principal:alice",
            "executor_id": "agent:personal-steward",
            "human_confirmed": True,
        },
    )

    executed = client.post(
        "/api/workflow-mesh/personal-episode/execute",
        json={"episode_id": episode_id, "principal_id": "principal:alice"},
    )
    assert executed.status_code == 200
    assert executed.json()["ok"] is True
    assert executed.json()["output_origin"] == "system"
    assert executed.json()["local_draft_recorded"] is True
    assert "evidence_uri" not in executed.json()

    artifacts = list(draft_dir.glob("*.json"))
    assert len(artifacts) == 1
    artifact = json.loads(artifacts[0].read_text(encoding="utf-8"))
    assert artifact["never_send"] is True
    assert artifact["output_origin"] == "system"
    assert artifact["title"] == "Prepare the commitment follow-up"

    broker = LedgerBroker.connect(ledger_path)
    try:
        evidence_rows = [
            json.loads(row["payload_json"])
            for row in broker.read(episode_id=episode_id)
            if row["event_type"] == "Evidence.LocalDraft.v1"
        ]
        assert len(evidence_rows) == 1
        digest = hashlib.sha256(artifacts[0].read_bytes()).hexdigest()
        assert evidence_rows[0]["evidence_uri"] == f"evidence://personal-draft/sha256:{digest}"
        assert evidence_rows[0]["output_origin"] == "system"
        assert evidence_rows[0]["action_id"].startswith("action:personal-")
    finally:
        broker.close()


def test_personal_execute_partial_draft_rejected(monkeypatch, tmp_path):
    """Partial draft fields (some but not all) are rejected — all-or-nothing."""
    _configure_runtime_no_seed(monkeypatch, tmp_path)
    client = TestClient(_app())

    client.post("/api/workflow-mesh/personal-episode/setup", json=_setup_payload())
    started = client.post("/api/workflow-mesh/personal-episode/start", json=_start_payload())
    episode_id = started.json()["episode"]["episode_id"]
    client.post(
        "/api/workflow-mesh/personal-episode/confirm",
        json={
            "episode_id": episode_id,
            "principal_id": "principal:alice",
            "executor_id": "agent:personal-steward",
            "human_confirmed": True,
        },
    )

    response = client.post(
        "/api/workflow-mesh/personal-episode/execute",
        json={"episode_id": episode_id, "principal_id": "principal:alice", "title": "Partial"},
    )
    assert response.status_code == 409
    assert response.json()["ok"] is False
    assert response.json()["error"] == "invalid_request"


def test_personal_status_read_only_summary(monkeypatch, tmp_path):
    """GET /status returns a read-only summary with no side effects."""
    _configure_runtime_no_seed(monkeypatch, tmp_path)
    client = TestClient(_app())

    client.post("/api/workflow-mesh/personal-episode/setup", json=_setup_payload())
    client.post("/api/workflow-mesh/personal-episode/start", json=_start_payload())

    status = client.get(
        "/api/workflow-mesh/personal-episode/status",
        params={"principal_id": "principal:alice"},
    )
    assert status.status_code == 200
    body = status.json()
    assert body["ok"] is True
    summary = body["summary"]
    assert summary["total_episodes"] >= 1
    assert summary["pending_confirmation"] >= 1
    assert body["controls"]["read_only"] is True
    assert body["controls"]["workflow_state_mutation"] is False


def test_personal_setup_ingest_system_draft_e2e(monkeypatch, tmp_path):
    """Setup → Ingest (local signal) → Confirm → System Draft works end-to-end."""
    import base64

    ledger_path = tmp_path / "event-ledger.sqlite3"
    signal_dir = tmp_path / "signals"
    signal_dir.mkdir(parents=True, exist_ok=True)
    draft_dir = tmp_path / "personal-drafts"
    monkeypatch.setenv("OMO_EVENT_LEDGER_DB", str(ledger_path))
    monkeypatch.setenv("PERSONAL_SIGNAL_DIR", str(signal_dir))
    monkeypatch.setenv("PERSONAL_DRAFT_DIR", str(draft_dir))
    monkeypatch.setenv("IRIS_LOCAL_FILES_DIRECTORY", str(signal_dir))
    monkeypatch.setenv("AGORA_PEP_PROVIDER", "omo.sovereignty.enforcement:AgoraPepProvider")
    reset_pep_provider_cache()

    note = signal_dir / "notes" / "follow-up.md"
    note.parent.mkdir(parents=True, exist_ok=True)
    note.write_text("---\ntitle: Follow up with team\n---\n\nImportant.\n", encoding="utf-8")
    item_id = base64.urlsafe_b64encode(b"notes/follow-up.md").decode().rstrip("=")

    client = TestClient(_app())

    assert client.post("/api/workflow-mesh/personal-episode/setup", json=_setup_payload()).status_code == 200

    ingested = client.post(
        "/api/workflow-mesh/personal-signal/ingest",
        json={
            "item_id": item_id,
            "principal_id": "principal:alice",
            "role_id": "role:personal-steward",
            "responsibility_id": "responsibility:follow-up",
            "executor_id": "agent:personal-steward",
        },
    )
    assert ingested.status_code == 200
    episode_id = ingested.json()["episode"]["episode_id"]

    assert (
        client.post(
            "/api/workflow-mesh/personal-episode/confirm",
            json={
                "episode_id": episode_id,
                "principal_id": "principal:alice",
                "executor_id": "agent:personal-steward",
                "human_confirmed": True,
            },
        ).status_code
        == 200
    )

    executed = client.post(
        "/api/workflow-mesh/personal-episode/execute",
        json={"episode_id": episode_id, "principal_id": "principal:alice"},
    )
    assert executed.status_code == 200
    assert executed.json()["output_origin"] == "system"
    assert executed.json()["local_draft_recorded"] is True
    assert "evidence_uri" not in executed.json()

    artifacts = list(draft_dir.glob("*.json"))
    assert len(artifacts) == 1
    artifact = json.loads(artifacts[0].read_text(encoding="utf-8"))
    assert artifact["title"] == "Follow up with team"
    assert artifact["never_send"] is True
    assert artifact["output_origin"] == "system"
    assert "Important." not in json.dumps(artifact)

    status = client.get(
        "/api/workflow-mesh/personal-episode/status",
        params={"principal_id": "principal:alice"},
    )
    assert status.status_code == 200
    status_text = status.text
    assert "iris://local-files/" not in status_text
    assert "content_sha256" not in status_text
    assert str(signal_dir) not in status_text
    assert "Important." not in status_text
