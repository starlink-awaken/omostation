from __future__ import annotations

import hashlib
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from reach_gateway.kems import dispatch_manifest

from scripts.kems_dispatch_receipt import build_receipt
from scripts.kems_production_preflight import run_preflight


def _source_tree(tmp_path: Path) -> Path:
    inbox = tmp_path / "_inbox"
    inbox.mkdir(parents=True)
    (inbox / "2026-auto-apple-mail.md").write_text("private source\n", encoding="utf-8")
    return inbox.parent


def _manifest(tmp_path: Path) -> Path:
    path = tmp_path / "evaluation.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": "kems.evaluation-manifest.v1",
                "dataset_id": "kems-real-fixture",
                "dataset_version": "v1",
                "redaction_status": "verified",
                "samples": [
                    {
                        "sample_id": "sample-1",
                        "source_sha256": "a" * 64,
                        "source_ref": "vault://redacted/sample-1",
                        "scenario_id": "oa-notice",
                        "split": "test",
                        "annotation_status": "adjudicated",
                        "labels": {"fixture": "notice"},
                        "annotation_version": "fixture-ann-1",
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return path


def _model_acceptance(tmp_path: Path, manifest: Path) -> Path:
    path = tmp_path / "model-acceptance.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": "kems.model-acceptance.v1",
                "candidate_model_id": "candidate-v1",
                "baseline_model_id": "naive-last-v1",
                "case_count": 2,
                "observation_count": 4,
                "model_mae": 0.5,
                "baseline_mae": 2.0,
                "relative_improvement": 0.75,
                "min_cases": 2,
                "min_relative_improvement": 0.1,
                "status": "shadow_pass",
                "promotion": "blocked_until_omo_approval",
                "dataset_id": "kems-real-fixture",
                "dataset_version": "v1",
                "evaluation_manifest_sha256": hashlib.sha256(
                    manifest.read_bytes()
                ).hexdigest(),
                "dataset_sample_count": 1,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return path


def _approved_omo(tmp_path: Path) -> Path:
    omo_root = tmp_path / "omo"
    (omo_root / "tasks" / "active").mkdir(parents=True)
    (omo_root / "workers" / "runs").mkdir(parents=True)
    (omo_root / "tasks" / "active" / "KEMS-E2E.yaml").write_text(
        "id: KEMS-E2E\nstatus: approved\n"
        "approval_ref: .omo/workers/runs/KEMS-E2E-approval.yaml\n",
        encoding="utf-8",
    )
    (omo_root / "workers" / "runs" / "KEMS-E2E-approval.yaml").write_text(
        "task_id: KEMS-E2E\napproval_status: granted\n"
        "approval_scope: task.promote_apply\n"
        "refs:\n  task_ref: .omo/tasks/active/KEMS-E2E.yaml\n",
        encoding="utf-8",
    )
    return omo_root


def test_redacted_production_lane_reaches_http_receipt(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv(
        "BOS_REACHBRIDGE_ENDPOINT", "https://reachbridge.example.test/dispatch"
    )
    monkeypatch.setenv("BOS_REACHBRIDGE_TOKEN", "fixture-token")
    manifest_path = _manifest(tmp_path)
    preflight = run_preflight(
        docs_root=_source_tree(tmp_path),
        evaluation_manifest=manifest_path,
        model_acceptance=_model_acceptance(tmp_path, manifest_path),
        omo_root=_approved_omo(tmp_path),
        task_id="KEMS-E2E",
        production=True,
    )
    assert preflight["status"] == "ready"

    received: dict[str, object] = {}

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            length = int(self.headers["Content-Length"])
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            received["payload"] = payload
            body = json.dumps(
                {"dispatch_id": payload["dispatch_id"], "status": "accepted"}
            ).encode("utf-8")
            self.send_response(202)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_args: object) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        monkeypatch.setenv(
            "BOS_REACHBRIDGE_ENDPOINT",
            f"http://127.0.0.1:{server.server_port}/dispatch",
        )
        manifest = {
            "schema": "bos.reachbridge.manifest.v1",
            "run_id": "kems-e2e",
            "documents": [
                {
                    "source_ref": "vault://redacted/sample-1",
                    "sha256": "a" * 64,
                    "bytes": 0,
                }
            ],
        }
        result = dispatch_manifest(manifest)
        receipt = build_receipt(
            manifest,
            result.as_dict() | {"status": "accepted"},
            production=True,
            recorded_at="2026-08-01T00:00:00+00:00",
        )
    finally:
        server.shutdown()
        thread.join(timeout=2)

    assert receipt["transport"] == "http"
    assert receipt["status"] == "accepted"
    request_body = json.dumps(received["payload"], ensure_ascii=False)
    assert "private source" not in request_body
    assert "fixture-token" not in request_body
    assert "content" not in request_body
