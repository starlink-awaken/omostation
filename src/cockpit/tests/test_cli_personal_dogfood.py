"""CLI HTTP tests for BET-Y1Q2-T2-02 personal dogfood.

These tests exercise the real ``cli.main()`` entry point with real CLI
args (including ``--item-id`` style options through REMAINDER). Most route
through the real ASGI app via TestClient so the OMO ledger, PEP, and Iris
connector run; one smoke test uses a real TCP listener to verify base-URL
configuration and the HTTP transport.
"""

from __future__ import annotations

import base64
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
from agora.mcp.policy_enforcement import reset_pep_provider_cache
from fastapi import FastAPI
from fastapi.testclient import TestClient
from omo.event_ledger import LedgerBroker

from cockpit.commands import workflow_mesh
from cockpit.web import api_workflow_mesh_operations


def _app() -> FastAPI:
    app = FastAPI()
    app.include_router(api_workflow_mesh_operations.router)  # type: ignore[arg-type]
    return app


def _configure_runtime(monkeypatch, tmp_path: Path) -> dict:
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
    return {
        "ledger_path": ledger_path,
        "signal_dir": signal_dir,
        "draft_dir": draft_dir,
    }


@pytest.fixture
def cli_http(monkeypatch, tmp_path):
    """Wire CLI HTTP calls through the real ASGI app via TestClient."""
    paths = _configure_runtime(monkeypatch, tmp_path)
    client = TestClient(_app())

    def _fake_post(path: str, payload: dict) -> tuple[int, dict]:
        response = client.post(path, json=payload)
        return response.status_code, response.json()

    def _fake_get(path: str, params: dict | None = None) -> tuple[int, dict]:
        response = client.get(path, params=params or {})
        return response.status_code, response.json()

    monkeypatch.setattr(workflow_mesh, "_api_post", _fake_post)
    monkeypatch.setattr(workflow_mesh, "_api_get", _fake_get)

    paths["client"] = client
    return paths


def _run_cli(monkeypatch, *argv: str) -> int:
    """Run cli.main() with the given argv and return the exit code."""
    monkeypatch.setattr(sys, "argv", ["cockpit", *argv])
    from cockpit import cli

    try:
        return cli.main()
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 1


# ── setup ──────────────────────────────────────────────────────────────


def test_cli_personal_setup_returns_zero(cli_http, monkeypatch):
    """cockpit workflow mesh personal setup succeeds (rc=0)."""
    rc = _run_cli(monkeypatch, "workflow", "mesh", "personal", "setup")
    assert rc == 0


def test_cli_personal_setup_idempotent(cli_http, monkeypatch):
    """Two setup calls both succeed."""
    assert _run_cli(monkeypatch, "workflow", "mesh", "personal", "setup") == 0
    assert _run_cli(monkeypatch, "workflow", "mesh", "personal", "setup") == 0


# ── full flow via CLI ──────────────────────────────────────────────────


def test_cli_personal_full_flow_system_draft(cli_http, monkeypatch):
    """setup → start → confirm → draft (system) → feedback, all via CLI."""
    # Setup
    assert _run_cli(monkeypatch, "workflow", "mesh", "personal", "setup") == 0

    # Start via API (CLI doesn't have a start subcommand — that's by design)
    client = cli_http["client"]
    started = client.post(
        "/api/workflow-mesh/personal-episode/start",
        json={
            "principal_id": "principal:alice",
            "role_id": "role:personal-steward",
            "responsibility_id": "responsibility:follow-up",
            "executor_id": "agent:personal-steward",
            "request_id": "cli-test-001",
            "summary": "CLI test follow-up",
            "why_now": "Testing the CLI flow",
            "deadline": "2026-08-13",
        },
    )
    assert started.status_code == 200
    episode_id = started.json()["episode"]["episode_id"]

    # Confirm via CLI
    assert _run_cli(
        monkeypatch, "workflow", "mesh", "personal", "confirm", "--episode-id", episode_id
    ) == 0

    # Draft via CLI (system mode — no draft fields)
    assert _run_cli(
        monkeypatch, "workflow", "mesh", "personal", "draft", "--episode-id", episode_id
    ) == 0

    # Verify artifact
    draft_dir = cli_http["draft_dir"]
    artifacts = list(draft_dir.glob("*.json"))
    assert len(artifacts) == 1
    import json

    artifact = json.loads(artifacts[0].read_text(encoding="utf-8"))
    assert artifact["output_origin"] == "system"
    assert artifact["never_send"] is True

    # Feedback via CLI
    assert _run_cli(
        monkeypatch,
        "workflow", "mesh", "personal", "feedback",
        "--episode-id", episode_id,
        "--verdict", "accept",
    ) == 0


def test_cli_personal_draft_user_provided(cli_http, monkeypatch):
    """CLI draft with all fields → output_origin=user_provided."""
    assert _run_cli(monkeypatch, "workflow", "mesh", "personal", "setup") == 0

    client = cli_http["client"]
    started = client.post(
        "/api/workflow-mesh/personal-episode/start",
        json={
            "principal_id": "principal:alice",
            "role_id": "role:personal-steward",
            "responsibility_id": "responsibility:follow-up",
            "executor_id": "agent:personal-steward",
            "request_id": "cli-test-002",
            "summary": "User-provided draft test",
            "why_now": "",
            "deadline": "2026-08-14",
        },
    )
    episode_id = started.json()["episode"]["episode_id"]
    _run_cli(monkeypatch, "workflow", "mesh", "personal", "confirm", "--episode-id", episode_id)

    rc = _run_cli(
        monkeypatch,
        "workflow", "mesh", "personal", "draft",
        "--episode-id", episode_id,
        "--title", "My Draft",
        "--context", "My context",
        "--deadline", "2026-08-14",
        "--next-action", "Do something",
    )
    assert rc == 0

    import json

    draft_dir = cli_http["draft_dir"]
    artifacts = list(draft_dir.glob("*.json"))
    assert len(artifacts) == 1
    artifact = json.loads(artifacts[0].read_text(encoding="utf-8"))
    assert artifact["output_origin"] == "user_provided"
    assert artifact["title"] == "My Draft"


def test_cli_personal_draft_partial_rejected(cli_http, monkeypatch):
    """CLI draft with partial fields returns non-zero."""
    assert _run_cli(monkeypatch, "workflow", "mesh", "personal", "setup") == 0

    client = cli_http["client"]
    started = client.post(
        "/api/workflow-mesh/personal-episode/start",
        json={
            "principal_id": "principal:alice",
            "role_id": "role:personal-steward",
            "responsibility_id": "responsibility:follow-up",
            "executor_id": "agent:personal-steward",
            "request_id": "cli-test-003",
            "summary": "Partial test",
            "why_now": "",
            "deadline": None,
        },
    )
    episode_id = started.json()["episode"]["episode_id"]
    _run_cli(monkeypatch, "workflow", "mesh", "personal", "confirm", "--episode-id", episode_id)

    rc = _run_cli(
        monkeypatch,
        "workflow", "mesh", "personal", "draft",
        "--episode-id", episode_id,
        "--title", "Only Title",
    )
    assert rc != 0


# ── ingest via CLI ─────────────────────────────────────────────────────


def test_cli_personal_ingest_with_option_args(cli_http, monkeypatch):
    """CLI ingest with --item-id option works through REMAINDER dispatch."""
    assert _run_cli(monkeypatch, "workflow", "mesh", "personal", "setup") == 0

    # Write a local Markdown note
    signal_dir = cli_http["signal_dir"]
    note = signal_dir / "notes" / "ingest-test.md"
    note.parent.mkdir(parents=True, exist_ok=True)
    note.write_text("---\ntitle: Ingest via CLI\n---\n\nBody.\n", encoding="utf-8")
    item_id = base64.urlsafe_b64encode(b"notes/ingest-test.md").decode().rstrip("=")

    rc = _run_cli(
        monkeypatch,
        "workflow", "mesh", "personal", "ingest",
        "--item-id", item_id,
    )
    assert rc == 0


# ── status via CLI ─────────────────────────────────────────────────────


def test_cli_personal_status_after_setup(cli_http, monkeypatch):
    """CLI status returns 0 after setup when projection is live."""
    _run_cli(monkeypatch, "workflow", "mesh", "personal", "setup")

    client = cli_http["client"]
    client.post(
        "/api/workflow-mesh/personal-episode/start",
        json={
            "principal_id": "principal:alice",
            "role_id": "role:personal-steward",
            "responsibility_id": "responsibility:follow-up",
            "executor_id": "agent:personal-steward",
            "request_id": "status-test",
            "summary": "Status test episode",
            "why_now": "",
            "deadline": None,
        },
    )

    rc = _run_cli(monkeypatch, "workflow", "mesh", "personal", "status")
    assert rc == 0


def test_cli_personal_status_unavailable_returns_nonzero(cli_http, monkeypatch):
    """CLI status returns non-zero when projection is unavailable (empty ledger)."""
    # No setup, no episodes — the projection endpoint will fail
    rc = _run_cli(monkeypatch, "workflow", "mesh", "personal", "status")
    assert rc != 0


# ── W3-01B extension: feedback with metrics, ignore verdict, status observation ─


def _cli_full_flow_to_episode(cli_http, monkeypatch) -> str:
    """Helper: setup → start (via API) → confirm → draft, return episode_id."""
    _run_cli(monkeypatch, "workflow", "mesh", "personal", "setup")
    client = cli_http["client"]
    started = client.post(
        "/api/workflow-mesh/personal-episode/start",
        json={
            "principal_id": "principal:alice",
            "role_id": "role:personal-steward",
            "responsibility_id": "responsibility:follow-up",
            "executor_id": "agent:personal-steward",
            "request_id": "cli-metric-test",
            "summary": "CLI metric test episode",
            "why_now": "",
            "deadline": None,
        },
    )
    episode_id = started.json()["episode"]["episode_id"]
    _run_cli(monkeypatch, "workflow", "mesh", "personal", "confirm", "--episode-id", episode_id)
    _run_cli(monkeypatch, "workflow", "mesh", "personal", "draft", "--episode-id", episode_id)
    return episode_id


def test_cli_personal_feedback_with_metrics(cli_http, monkeypatch):
    """CLI feedback with --review-duration-seconds and --estimated-time-saved-seconds."""
    episode_id = _cli_full_flow_to_episode(cli_http, monkeypatch)
    rc = _run_cli(
        monkeypatch,
        "workflow", "mesh", "personal", "feedback",
        "--episode-id", episode_id,
        "--feedback-id", "feedback:cli-metrics",
        "--verdict", "accept",
        "--review-duration-seconds", "90",
        "--estimated-time-saved-seconds", "300",
    )
    assert rc == 0


def test_cli_personal_feedback_id_supports_revisions(cli_http, monkeypatch):
    """CLI threads stable feedback IDs through replay and later revisions."""
    episode_id = _cli_full_flow_to_episode(cli_http, monkeypatch)

    def submit(feedback_id: str, verdict: str, *metrics: str) -> int:
        return _run_cli(
            monkeypatch,
            "workflow", "mesh", "personal", "feedback",
            "--episode-id", episode_id,
            "--feedback-id", feedback_id,
            "--verdict", verdict,
            *metrics,
        )

    assert submit("feedback:cli-001", "accept") == 0
    assert submit("feedback:cli-001", "accept") == 0
    assert submit("feedback:cli-002", "reject") == 0
    assert submit("feedback:cli-003", "accept") == 0
    assert submit(
        "feedback:cli-004",
        "accept",
        "--review-duration-seconds", "45",
        "--estimated-time-saved-seconds", "240",
    ) == 0

    broker = LedgerBroker.connect(cli_http["ledger_path"])
    try:
        payloads = [
            json.loads(row["payload_json"])
            for row in broker.read(episode_id=episode_id)
            if row["event_type"] == "Outcome.Human.v1"
        ]
        assert [payload["feedback_id"] for payload in payloads] == [
            "feedback:cli-001",
            "feedback:cli-002",
            "feedback:cli-003",
            "feedback:cli-004",
        ]
        assert payloads[-1]["review_duration_seconds"] == 45
        assert payloads[-1]["estimated_time_saved_seconds"] == 240
    finally:
        broker.close()


def test_cli_personal_feedback_rejects_invalid_burden_without_http(cli_http, monkeypatch):
    """CLI rejects negative, NaN, and infinity before issuing an HTTP request."""
    calls: list[tuple[str, dict]] = []

    def _unexpected_post(path: str, payload: dict) -> tuple[int, dict]:
        calls.append((path, payload))
        return 200, {"ok": True}

    monkeypatch.setattr(workflow_mesh, "_api_post", _unexpected_post)
    for option, value in (
        ("--review-duration-seconds", "-1"),
        ("--review-duration-seconds", "nan"),
        ("--estimated-time-saved-seconds", "inf"),
    ):
        rc = _run_cli(
            monkeypatch,
            "workflow", "mesh", "personal", "feedback",
            "--episode-id", "episode:test",
            "--verdict", "accept",
            option, value,
        )
        assert rc != 0
    assert calls == []


def test_cli_personal_feedback_ignore_verdict(cli_http, monkeypatch):
    """CLI feedback with --verdict ignore succeeds."""
    episode_id = _cli_full_flow_to_episode(cli_http, monkeypatch)
    rc = _run_cli(
        monkeypatch,
        "workflow", "mesh", "personal", "feedback",
        "--episode-id", episode_id,
        "--verdict", "ignore",
    )
    assert rc == 0


def test_cli_personal_status_shows_observation(cli_http, monkeypatch):
    """CLI status after a completed episode with feedback shows readiness."""
    episode_id = _cli_full_flow_to_episode(cli_http, monkeypatch)
    _run_cli(
        monkeypatch,
        "workflow", "mesh", "personal", "feedback",
        "--episode-id", episode_id,
        "--verdict", "accept",
    )
    rc = _run_cli(monkeypatch, "workflow", "mesh", "personal", "status")
    assert rc == 0


def test_cli_personal_status_observation_unavailable_returns_nonzero(cli_http, monkeypatch):
    """CLI propagates an unavailable OMO observation as a failed command."""
    monkeypatch.setattr(
        workflow_mesh,
        "_api_get",
        lambda path, params=None: (
            503,
            {
                "ok": False,
                "status": "unavailable",
                "error": "personal_episode_observation_failed",
            },
        ),
    )
    rc = _run_cli(monkeypatch, "workflow", "mesh", "personal", "status")
    assert rc != 0


# ── no subcommand prints help ──────────────────────────────────────────


def test_cli_personal_no_subcommand_returns_zero(cli_http, monkeypatch):
    """Bare 'cockpit workflow mesh personal' prints help and returns 0."""
    rc = _run_cli(monkeypatch, "workflow", "mesh", "personal")
    assert rc == 0


# ── connection failure ─────────────────────────────────────────────────


def test_cli_personal_connection_failure_returns_nonzero(monkeypatch):
    """CLI returns non-zero on HTTP connection failure (no server running)."""
    # Point at a port that's definitely not listening
    monkeypatch.setenv("COCKPIT_API_URL", "http://127.0.0.1:1")

    # Restore the real _api_post (not the TestClient mock from cli_http fixture)
    import importlib

    importlib.reload(workflow_mesh)

    rc = _run_cli(monkeypatch, "workflow", "mesh", "personal", "setup")
    assert rc != 0


def test_cli_personal_setup_uses_configured_api_url_over_real_http(monkeypatch):
    """COCKPIT_API_URL controls the real HTTP transport used by the CLI."""
    received: list[tuple[str, dict]] = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
            received.append((self.path, json.loads(body)))
            payload = json.dumps({"ok": True, "status": "assigned"}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, format: str, *args: object) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        monkeypatch.setenv(
            "COCKPIT_API_URL", f"http://127.0.0.1:{server.server_port}"
        )
        import importlib

        importlib.reload(workflow_mesh)
        rc = _run_cli(monkeypatch, "workflow", "mesh", "personal", "setup")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)

    assert rc == 0
    assert received == [
        (
            "/api/workflow-mesh/personal-episode/setup",
            {
                "principal_id": "principal:alice",
                "role_id": "role:personal-steward",
                "role_name": "Personal Steward",
                "scope": "personal",
                "responsibilities": ["responsibility:follow-up"],
            },
        )
    ]
