"""Real TestClient + Iris connector + SQLite Ledger tests for the W3-01A ingest.

The POST ``/api/workflow-mesh/personal-signal/ingest`` endpoint is the
server-side seam that resolves an opaque ``item_id`` through Iris's read-only
``LocalFilesConnector``, verifies the resolved file server-side, builds a
``PersonalLocalSignal`` descriptor, and delegates to OMO's real
``ingest_local_signal``.  Everything here uses the real TestClient, the real
Iris connector and a real SQLite Event Ledger — no mocks of the ledger or the
connector — and every rejected request must leave the ledger count and hash
chain untouched.
"""

from __future__ import annotations

import base64
import json
from pathlib import Path

from agora.mcp.policy_enforcement import reset_pep_provider_cache
from fastapi import FastAPI
from fastapi.testclient import TestClient
from omo.event_ledger import LedgerBroker
from omo.personal_episode import EVT_EPISODE_DECISION, EVT_SIGNAL_OBSERVED
from omo.sovereignty import SovereigntyService

from cockpit.web import api_workflow_mesh_operations


def _app() -> FastAPI:
    app = FastAPI()
    app.include_router(api_workflow_mesh_operations.router)  # type: ignore[arg-type]
    return app


def _configure_runtime(monkeypatch, tmp_path: Path) -> tuple[Path, Path, Path]:
    """Point the server at a throwaway ledger, signal dir and draft dir."""
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
    return ledger_path, signal_dir, draft_dir


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


def _item_id(rel_path: str) -> str:
    return base64.urlsafe_b64encode(rel_path.encode()).decode().rstrip("=")


def _write_item(signal_dir: Path, rel_path: str, *, title: str, body: str) -> str:
    target = signal_dir / rel_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(f"---\ntitle: {title}\n---\n\n{body}\n", encoding="utf-8")
    return _item_id(rel_path)


def _ingest_payload(item_id: str, **overrides) -> dict[str, str]:
    payload = {
        "item_id": item_id,
        "principal_id": "principal:alice",
        "role_id": "role:personal-steward",
        "responsibility_id": "responsibility:follow-up",
        "executor_id": "agent:personal-steward",
    }
    payload.update(overrides)
    return payload


def _ledger_state(ledger_path: Path) -> tuple[int, bool]:
    broker = LedgerBroker.connect(ledger_path)
    try:
        return broker.count(), broker.verify_chain()["ok"]
    finally:
        broker.close()


def _assert_fail_closed(client, ledger_path: Path, payload: dict[str, str], expected_error: str) -> None:
    count_before, chain_before = _ledger_state(ledger_path)
    response = client.post("/api/workflow-mesh/personal-signal/ingest", json=payload)
    assert response.status_code == 409
    assert response.json()["ok"] is False
    assert response.json()["error"] == expected_error
    count_after, chain_after = _ledger_state(ledger_path)
    assert (count_after, chain_after) == (count_before, chain_before)


def test_ingest_creates_causal_private_inbox_episode(monkeypatch, tmp_path):
    ledger_path, signal_dir, _ = _configure_runtime(monkeypatch, tmp_path)
    _seed_role(ledger_path)
    item_id = _write_item(
        signal_dir,
        "notes/follow-up.md",
        title="Follow up with the project team",
        body="Prepare the next step.",
    )
    client = TestClient(_app())

    response = client.post("/api/workflow-mesh/personal-signal/ingest", json=_ingest_payload(item_id))

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["status"] == "pending_confirmation"
    assert payload["episode"]["reused"] is False
    # The response exposes only pending-episode and safe signal refs.
    assert set(payload["signal"]) == {"signal_event_id", "signal_id"}
    assert set(payload["episode"]) == {"episode_id", "request_id", "summary", "reused"}
    response_text = response.text
    assert str(signal_dir) not in response_text
    assert str(ledger_path) not in response_text
    assert "Prepare the next step." not in response_text

    broker = LedgerBroker.connect(ledger_path)
    try:
        rows = broker.read()
        signal_row = next(row for row in rows if row["event_type"] == EVT_SIGNAL_OBSERVED)
        episode_row = next(row for row in rows if row["event_type"] == EVT_EPISODE_DECISION)
        signal_payload = json.loads(signal_row["payload_json"])
        episode_payload = json.loads(episode_row["payload_json"])

        # The SignalObserved event causally precedes the Inbox Episode decision.
        assert signal_row["privacy_class"] == "private"
        assert episode_row["privacy_class"] == "private"
        assert signal_row["event_id"] == payload["signal"]["signal_event_id"]
        assert episode_row["episode_id"] == payload["episode"]["episode_id"]
        assert episode_row["causation_id"] == signal_row["event_id"]
        assert episode_payload["source_signal_ref"] == signal_row["event_id"]
        assert episode_payload["summary"] == "Follow up with the project team"
        assert episode_payload["status"] == "pending_confirmation"
        assert signal_payload["signal_id"] == payload["signal"]["signal_id"]
        assert signal_payload["source_uri"] == f"iris://local-files/{item_id}"
        assert len(signal_payload["content_sha256"]) == 64
        # No absolute path and no raw file body ever reach the ledger.
        ledger_text = signal_row["payload_json"] + episode_row["payload_json"]
        assert str(signal_dir) not in ledger_text
        assert "file://" not in ledger_text
        assert "Prepare the next step." not in ledger_text
        assert broker.verify_chain()["ok"] is True
    finally:
        broker.close()

    # The causal Inbox Episode is visible in the read-only W2-04 projection.
    inbox = client.get("/api/workflow-mesh/episode-projections", params={"principal_id": "principal:alice"})
    assert inbox.status_code == 200
    snapshot = inbox.json()["projection"]
    assert any(card["episode"] == payload["episode"]["episode_id"] for card in snapshot["inbox"])
    assert snapshot["controls"]["ledger_unchanged"] is True


def test_ingest_confirms_and_drafts_never_send_with_feedback(monkeypatch, tmp_path):
    ledger_path, signal_dir, draft_dir = _configure_runtime(monkeypatch, tmp_path)
    _seed_role(ledger_path)
    item_id = _write_item(
        signal_dir,
        "notes/follow-up.md",
        title="Follow up with the project team",
        body="Prepare the next step.",
    )
    client = TestClient(_app())

    ingested = client.post("/api/workflow-mesh/personal-signal/ingest", json=_ingest_payload(item_id))
    assert ingested.status_code == 200
    episode_id = ingested.json()["episode"]["episode_id"]

    # The ingested episode is fully usable by the existing W2-05 flow.
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

    executed = client.post(
        "/api/workflow-mesh/personal-episode/execute",
        json={
            "episode_id": episode_id,
            "principal_id": "principal:alice",
            "title": "Commitment follow-up draft",
            "context": "Summarise the next step for review.",
            "deadline": "2026-08-13",
            "next_action": "Review, edit, or discard the local draft.",
        },
    )
    assert executed.status_code == 200
    executed_body = executed.json()
    assert "evidence_uri" not in executed_body
    assert "file://" not in executed.text
    assert str(draft_dir) not in executed.text
    artifacts = list(draft_dir.glob("*.json"))
    assert len(artifacts) == 1
    artifact = json.loads(artifacts[0].read_text(encoding="utf-8"))
    assert artifact["never_send"] is True

    feedback = client.post(
        "/api/workflow-mesh/personal-episode/feedback",
        json={"episode_id": episode_id, "principal_id": "principal:alice", "verdict": "accept"},
    )
    assert feedback.status_code == 200

    broker = LedgerBroker.connect(ledger_path)
    try:
        event_types = {row["event_type"] for row in broker.read(episode_id=episode_id)}
        assert {
            "Action.Started.v1",
            "Action.Succeeded.v1",
            "Evidence.LocalDraft.v1",
            "Outcome.Human.v1",
        } <= event_types
        assert broker.verify_chain()["ok"] is True
    finally:
        broker.close()


def test_ingest_exact_replay_returns_same_ids_and_no_new_events(monkeypatch, tmp_path):
    ledger_path, signal_dir, _ = _configure_runtime(monkeypatch, tmp_path)
    _seed_role(ledger_path)
    item_id = _write_item(
        signal_dir,
        "notes/follow-up.md",
        title="Follow up with the project team",
        body="Prepare the next step.",
    )
    client = TestClient(_app())
    payload = _ingest_payload(item_id)

    first = client.post("/api/workflow-mesh/personal-signal/ingest", json=payload)
    second = client.post("/api/workflow-mesh/personal-signal/ingest", json=payload)

    assert first.status_code == second.status_code == 200
    assert second.json()["episode"]["reused"] is True
    assert second.json()["signal"]["signal_event_id"] == first.json()["signal"]["signal_event_id"]
    assert second.json()["signal"]["signal_id"] == first.json()["signal"]["signal_id"]
    assert second.json()["episode"]["episode_id"] == first.json()["episode"]["episode_id"]
    # role assignment + one SignalObserved + one Episode.Decision only.
    assert _ledger_state(ledger_path) == (3, True)


def test_ingest_changed_file_digest_creates_a_new_causal_pair(monkeypatch, tmp_path):
    ledger_path, signal_dir, _ = _configure_runtime(monkeypatch, tmp_path)
    _seed_role(ledger_path)
    item_id = _write_item(
        signal_dir,
        "notes/follow-up.md",
        title="Follow up with the project team",
        body="Prepare the next step.",
    )
    client = TestClient(_app())
    payload = _ingest_payload(item_id)

    first = client.post("/api/workflow-mesh/personal-signal/ingest", json=payload)
    assert first.status_code == 200

    # Same item_id, changed file content -> new digest -> new causal pair.
    _write_item(
        signal_dir,
        "notes/follow-up.md",
        title="Follow up with the project team",
        body="The commitment is now overdue.",
    )
    second = client.post("/api/workflow-mesh/personal-signal/ingest", json=payload)

    assert second.status_code == 200
    assert second.json()["episode"]["reused"] is False
    assert second.json()["signal"]["signal_event_id"] != first.json()["signal"]["signal_event_id"]
    assert second.json()["signal"]["signal_id"] != first.json()["signal"]["signal_id"]
    assert second.json()["episode"]["episode_id"] != first.json()["episode"]["episode_id"]

    broker = LedgerBroker.connect(ledger_path)
    try:
        assert len(broker.read(event_type=EVT_SIGNAL_OBSERVED)) == 2
        assert len(broker.read(event_type=EVT_EPISODE_DECISION)) == 2
        assert broker.verify_chain()["ok"] is True
    finally:
        broker.close()


def test_ingest_rejects_missing_server_config_without_touching_ledger(monkeypatch, tmp_path):
    ledger_path, _signal_dir, _draft_dir = _configure_runtime(monkeypatch, tmp_path)
    _seed_role(ledger_path)
    monkeypatch.delenv("PERSONAL_SIGNAL_DIR")
    client = TestClient(_app())

    _assert_fail_closed(
        client,
        ledger_path,
        _ingest_payload(_item_id("notes/follow-up.md")),
        "missing_config",
    )


def test_ingest_rejects_unknown_item_id_without_touching_ledger(monkeypatch, tmp_path):
    ledger_path, _signal_dir, _draft_dir = _configure_runtime(monkeypatch, tmp_path)
    _seed_role(ledger_path)
    client = TestClient(_app())

    _assert_fail_closed(
        client,
        ledger_path,
        _ingest_payload(_item_id("notes/does-not-exist.md")),
        "item_not_found",
    )


def test_ingest_rejects_traversal_item_id_without_touching_ledger(monkeypatch, tmp_path):
    ledger_path, signal_dir, _draft_dir = _configure_runtime(monkeypatch, tmp_path)
    _seed_role(ledger_path)
    # A file that shares the allowed directory's string prefix so the
    # connector's own prefix guard would be fooled; the server re-verifies.
    outside = tmp_path / "signals-outside.md"
    outside.write_text("---\ntitle: Outside\n---\n\nsecret\n", encoding="utf-8")
    client = TestClient(_app())

    # ../signals-outside.md resolves next to the allowed directory.
    _assert_fail_closed(client, ledger_path, _ingest_payload(_item_id("../signals-outside.md")), "item_not_found")


def test_ingest_rejects_outside_symlink_without_touching_ledger(monkeypatch, tmp_path):
    ledger_path, signal_dir, _draft_dir = _configure_runtime(monkeypatch, tmp_path)
    _seed_role(ledger_path)
    outside = tmp_path / "outside-secret.md"
    outside.write_text("---\ntitle: Outside\n---\n\nsecret\n", encoding="utf-8")
    (signal_dir / "escape.md").symlink_to(outside)
    client = TestClient(_app())

    _assert_fail_closed(client, ledger_path, _ingest_payload(_item_id("escape.md")), "item_not_found")


def test_ingest_rejects_source_that_escapes_allowed_dir_without_touching_ledger(monkeypatch, tmp_path):
    ledger_path, signal_dir, _draft_dir = _configure_runtime(monkeypatch, tmp_path)
    _seed_role(ledger_path)
    item_id = _item_id("notes/follow-up.md")

    # A real connector whose get_item returns a Note whose source_path points
    # outside PERSONAL_SIGNAL_DIR — the server must re-verify and fail closed.
    from iris.models import Note

    connector = api_workflow_mesh_operations.LocalFilesConnector()

    def _escaping_get_item(_id):
        return Note(
            id=item_id,
            title="Follow up with the project team",
            platform="local_files",
            content="some content",
            source_path=str(tmp_path / "elsewhere" / "leak.md"),
            platform_notebook="elsewhere",
        )

    connector.get_item = _escaping_get_item  # type: ignore[method-assign]
    monkeypatch.setattr(api_workflow_mesh_operations, "_local_files_connector", lambda _dir: connector)
    client = TestClient(_app())

    _assert_fail_closed(client, ledger_path, _ingest_payload(item_id), "source_outside_allowed_dir")


def test_ingest_rejects_non_markdown_without_touching_ledger(monkeypatch, tmp_path):
    ledger_path, signal_dir, _draft_dir = _configure_runtime(monkeypatch, tmp_path)
    _seed_role(ledger_path)
    target = signal_dir / "notes" / "plain.txt"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("not markdown\n", encoding="utf-8")
    client = TestClient(_app())

    _assert_fail_closed(client, ledger_path, _ingest_payload(_item_id("notes/plain.txt")), "not_markdown")


def test_ingest_rejects_empty_title_without_touching_ledger(monkeypatch, tmp_path):
    ledger_path, signal_dir, _draft_dir = _configure_runtime(monkeypatch, tmp_path)
    _seed_role(ledger_path)
    target = signal_dir / "notes" / "blank.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("---\ntitle: \"   \"\n---\n\nEmpty title.\n", encoding="utf-8")
    client = TestClient(_app())

    _assert_fail_closed(client, ledger_path, _ingest_payload(_item_id("notes/blank.md")), "empty_title")


def test_ingest_rejects_bad_role_and_responsibility_without_touching_ledger(monkeypatch, tmp_path):
    ledger_path, signal_dir, _draft_dir = _configure_runtime(monkeypatch, tmp_path)
    _seed_role(ledger_path)
    item_id = _write_item(
        signal_dir,
        "notes/follow-up.md",
        title="Follow up with the project team",
        body="Prepare the next step.",
    )
    client = TestClient(_app())

    _assert_fail_closed(
        client,
        ledger_path,
        _ingest_payload(item_id, role_id="role:someone-else"),
        "role_not_active",
    )
    _assert_fail_closed(
        client,
        ledger_path,
        _ingest_payload(item_id, responsibility_id="responsibility:other-duty"),
        "responsibility_not_active",
    )


def test_ingest_rejects_caller_supplied_content_fields_without_touching_ledger(monkeypatch, tmp_path):
    ledger_path, signal_dir, _draft_dir = _configure_runtime(monkeypatch, tmp_path)
    _seed_role(ledger_path)
    item_id = _write_item(
        signal_dir,
        "notes/follow-up.md",
        title="Follow up with the project team",
        body="Prepare the next step.",
    )
    client = TestClient(_app())

    for forbidden in ("summary", "content", "path", "source_uri", "digest", "scene"):
        _assert_fail_closed(
            client,
            ledger_path,
            _ingest_payload(item_id, **{forbidden: "caller-controlled"}),
            "invalid_request",
        )
