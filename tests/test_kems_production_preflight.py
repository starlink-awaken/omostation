import json

from scripts.kems_production_preflight import run_preflight


def _source_tree(tmp_path):
    docs = tmp_path / "docs"
    inbox = docs / "_inbox"
    inbox.mkdir(parents=True)
    (inbox / "2026-auto-apple-mail.md").write_text("private source\n", encoding="utf-8")
    return docs


def _evaluation_manifest(tmp_path):
    path = tmp_path / "evaluation.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": "kems.evaluation-manifest.v1",
                "dataset_id": "real-kems",
                "dataset_version": "2026-07-31",
                "redaction_status": "verified",
                "samples": [
                    {
                        "sample_id": "sample-1",
                        "source_sha256": "a" * 64,
                        "source_ref": "vault://redacted/sample-1",
                        "scenario_id": "oa-notice",
                        "split": "test",
                        "annotation_status": "adjudicated",
                        "labels": {"title": "通知"},
                        "annotation_version": "ann-1",
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return path


def _approved_task(tmp_path):
    task_dir = tmp_path / "tasks" / "active"
    task_dir.mkdir(parents=True)
    (task_dir / "KEMS-001.yaml").write_text(
        "status: approved\napproval_state: approved\napproval_ref: review-001\n",
        encoding="utf-8",
    )


def test_preflight_blocks_without_external_gates(tmp_path, monkeypatch):
    monkeypatch.delenv("BOS_REACHBRIDGE_ENDPOINT", raising=False)
    monkeypatch.delenv("BOS_REACHBRIDGE_TOKEN", raising=False)
    result = run_preflight(
        docs_root=_source_tree(tmp_path),
        evaluation_manifest=None,
        omo_root=tmp_path / "omo",
        task_id=None,
        production=True,
    )
    assert result["status"] == "blocked"
    assert all(
        "private source" not in json.dumps(result, ensure_ascii=False) for _ in [0]
    )


def test_preflight_is_ready_only_when_all_production_gates_pass(tmp_path, monkeypatch):
    monkeypatch.setenv(
        "BOS_REACHBRIDGE_ENDPOINT", "https://reachbridge.example.test/dispatch"
    )
    monkeypatch.setenv("BOS_REACHBRIDGE_TOKEN", "test-token")
    _approved_task(tmp_path / "omo")
    result = run_preflight(
        docs_root=_source_tree(tmp_path),
        evaluation_manifest=_evaluation_manifest(tmp_path),
        omo_root=tmp_path / "omo",
        task_id="KEMS-001",
        production=True,
    )
    assert result["status"] == "ready"
    assert result["source_count"] == 1


def test_preflight_rejects_raw_evaluation_fields(tmp_path, monkeypatch):
    monkeypatch.setenv(
        "BOS_REACHBRIDGE_ENDPOINT", "https://reachbridge.example.test/dispatch"
    )
    monkeypatch.setenv("BOS_REACHBRIDGE_TOKEN", "test-token")
    _approved_task(tmp_path / "omo")
    manifest = _evaluation_manifest(tmp_path)
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    payload["samples"][0]["text"] = "private"
    manifest.write_text(json.dumps(payload), encoding="utf-8")
    result = run_preflight(
        docs_root=_source_tree(tmp_path),
        evaluation_manifest=manifest,
        omo_root=tmp_path / "omo",
        task_id="KEMS-001",
        production=True,
    )
    assert result["status"] == "blocked"
    assert any(
        item["id"] == "evaluation_manifest" and not item["ok"]
        for item in result["checks"]
    )
