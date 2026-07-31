import hashlib
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


def _model_acceptance(tmp_path, manifest):
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
                "dataset_id": "real-kems",
                "dataset_version": "2026-07-31",
                "evaluation_manifest_sha256": hashlib.sha256(
                    manifest.read_bytes()
                ).hexdigest(),
                "dataset_sample_count": 1,
            }
        ),
        encoding="utf-8",
    )
    return path


def _approved_task(tmp_path):
    task_dir = tmp_path / "tasks" / "active"
    task_dir.mkdir(parents=True)
    (task_dir / "KEMS-001.yaml").write_text(
        "id: KEMS-001\nstatus: approved\napproval_ref: .omo/workers/runs/KEMS-001-approval.yaml\n",
        encoding="utf-8",
    )
    approval_dir = tmp_path / "workers" / "runs"
    approval_dir.mkdir(parents=True)
    (approval_dir / "KEMS-001-approval.yaml").write_text(
        "task_id: KEMS-001\napproval_status: granted\napproval_scope: task.promote_apply\n"
        "refs:\n  task_ref: .omo/tasks/active/KEMS-001.yaml\n",
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
    manifest = _evaluation_manifest(tmp_path)
    result = run_preflight(
        docs_root=_source_tree(tmp_path),
        evaluation_manifest=manifest,
        model_acceptance=_model_acceptance(tmp_path, manifest),
        omo_root=tmp_path / "omo",
        task_id="KEMS-001",
        production=True,
    )
    assert result["status"] == "ready"
    assert result["source_count"] == 1


def test_preflight_blocks_without_model_shadow_acceptance(tmp_path, monkeypatch):
    monkeypatch.setenv(
        "BOS_REACHBRIDGE_ENDPOINT", "https://reachbridge.example.test/dispatch"
    )
    monkeypatch.setenv("BOS_REACHBRIDGE_TOKEN", "test-token")
    _approved_task(tmp_path / "omo")
    manifest = _evaluation_manifest(tmp_path)
    result = run_preflight(
        docs_root=_source_tree(tmp_path),
        evaluation_manifest=manifest,
        omo_root=tmp_path / "omo",
        task_id="KEMS-001",
        production=True,
    )
    assert result["status"] == "blocked"
    assert any(
        item["id"] == "model_acceptance" and not item["ok"] for item in result["checks"]
    )


def test_preflight_blocks_model_acceptance_bound_to_other_manifest(
    tmp_path, monkeypatch
):
    monkeypatch.setenv(
        "BOS_REACHBRIDGE_ENDPOINT", "https://reachbridge.example.test/dispatch"
    )
    monkeypatch.setenv("BOS_REACHBRIDGE_TOKEN", "test-token")
    _approved_task(tmp_path / "omo")
    manifest = _evaluation_manifest(tmp_path)
    acceptance = _model_acceptance(tmp_path, manifest)
    payload = json.loads(acceptance.read_text(encoding="utf-8"))
    payload["evaluation_manifest_sha256"] = "b" * 64
    acceptance.write_text(json.dumps(payload), encoding="utf-8")
    result = run_preflight(
        docs_root=_source_tree(tmp_path),
        evaluation_manifest=manifest,
        model_acceptance=acceptance,
        omo_root=tmp_path / "omo",
        task_id="KEMS-001",
        production=True,
    )
    assert result["status"] == "blocked"
    assert any(
        item["id"] == "model_acceptance"
        and not item["ok"]
        and "different manifest" in item["detail"]
        for item in result["checks"]
    )


def test_preflight_writes_redacted_auditable_evidence(tmp_path, monkeypatch):
    monkeypatch.setenv(
        "BOS_REACHBRIDGE_ENDPOINT", "https://reachbridge.example.test/dispatch"
    )
    monkeypatch.setenv("BOS_REACHBRIDGE_TOKEN", "test-token")
    _approved_task(tmp_path / "omo")
    manifest = _evaluation_manifest(tmp_path)
    output = tmp_path / "evidence" / "preflight.json"
    result = run_preflight(
        docs_root=_source_tree(tmp_path),
        evaluation_manifest=manifest,
        model_acceptance=_model_acceptance(tmp_path, manifest),
        omo_root=tmp_path / "omo",
        task_id="KEMS-001",
        production=True,
        evidence_output=output,
    )

    evidence = json.loads(output.read_text(encoding="utf-8"))
    assert result["evidence_output"] == str(output.resolve())
    assert evidence["schema"] == "kems.production-preflight-evidence.v1"
    assert evidence["status"] == "ready"
    assert evidence["sources"][0]["name"] == "2026-auto-apple-mail.md"
    assert evidence["evaluation"]["dataset_id"] == "real-kems"
    assert evidence["model_acceptance"]["status"] == "shadow_pass"
    assert evidence["omo"]["approval_ref"] == ".omo/workers/runs/KEMS-001-approval.yaml"
    assert "private source" not in output.read_text(encoding="utf-8")
    assert not list(output.parent.glob(".*.tmp"))


def test_preflight_rejects_raw_evaluation_fields(tmp_path, monkeypatch):
    monkeypatch.setenv(
        "BOS_REACHBRIDGE_ENDPOINT", "https://reachbridge.example.test/dispatch"
    )
    monkeypatch.setenv("BOS_REACHBRIDGE_TOKEN", "test-token")
    _approved_task(tmp_path / "omo")
    manifest = _evaluation_manifest(tmp_path)
    model_acceptance = _model_acceptance(tmp_path, manifest)
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    payload["samples"][0]["text"] = "private"
    manifest.write_text(json.dumps(payload), encoding="utf-8")
    result = run_preflight(
        docs_root=_source_tree(tmp_path),
        evaluation_manifest=manifest,
        model_acceptance=model_acceptance,
        omo_root=tmp_path / "omo",
        task_id="KEMS-001",
        production=True,
    )
    assert result["status"] == "blocked"
    assert any(
        item["id"] == "evaluation_manifest" and not item["ok"]
        for item in result["checks"]
    )


def test_preflight_blocks_on_invalid_omo_yaml(tmp_path, monkeypatch):
    monkeypatch.setenv(
        "BOS_REACHBRIDGE_ENDPOINT", "https://reachbridge.example.test/dispatch"
    )
    monkeypatch.setenv("BOS_REACHBRIDGE_TOKEN", "test-token")
    task_dir = tmp_path / "omo" / "tasks" / "active"
    task_dir.mkdir(parents=True)
    (task_dir / "KEMS-001.yaml").write_text(
        "status: [approved\napproval_state: approved\n",
        encoding="utf-8",
    )
    result = run_preflight(
        docs_root=_source_tree(tmp_path),
        evaluation_manifest=(manifest := _evaluation_manifest(tmp_path)),
        model_acceptance=_model_acceptance(tmp_path, manifest),
        omo_root=tmp_path / "omo",
        task_id="KEMS-001",
        production=True,
    )
    assert result["status"] == "blocked"
    assert any(
        item["id"] == "omo_approval"
        and not item["ok"]
        and "invalid OMO task metadata" in item["detail"]
        for item in result["checks"]
    )


def test_preflight_rejects_ungranted_omo_promotion(tmp_path, monkeypatch):
    monkeypatch.setenv(
        "BOS_REACHBRIDGE_ENDPOINT", "https://reachbridge.example.test/dispatch"
    )
    monkeypatch.setenv("BOS_REACHBRIDGE_TOKEN", "test-token")
    _approved_task(tmp_path / "omo")
    manifest = _evaluation_manifest(tmp_path)
    approval = tmp_path / "omo" / "workers" / "runs" / "KEMS-001-approval.yaml"
    approval.write_text(
        "task_id: KEMS-001\napproval_status: requested\napproval_scope: task.promote_apply\n"
        "refs:\n  task_ref: .omo/tasks/active/KEMS-001.yaml\n",
        encoding="utf-8",
    )
    result = run_preflight(
        docs_root=_source_tree(tmp_path),
        evaluation_manifest=manifest,
        model_acceptance=_model_acceptance(tmp_path, manifest),
        omo_root=tmp_path / "omo",
        task_id="KEMS-001",
        production=True,
    )
    assert result["status"] == "blocked"
    assert any(
        item["id"] == "omo_approval"
        and not item["ok"]
        and "ungranted" in item["detail"]
        for item in result["checks"]
    )


def test_preflight_rejects_omo_task_that_is_only_active(tmp_path, monkeypatch):
    monkeypatch.setenv(
        "BOS_REACHBRIDGE_ENDPOINT", "https://reachbridge.example.test/dispatch"
    )
    monkeypatch.setenv("BOS_REACHBRIDGE_TOKEN", "test-token")
    _approved_task(tmp_path / "omo")
    task = tmp_path / "omo" / "tasks" / "active" / "KEMS-001.yaml"
    task.write_text(
        "id: KEMS-001\nstatus: active\napproval_ref: .omo/workers/runs/KEMS-001-approval.yaml\n",
        encoding="utf-8",
    )
    manifest = _evaluation_manifest(tmp_path)
    result = run_preflight(
        docs_root=_source_tree(tmp_path),
        evaluation_manifest=manifest,
        model_acceptance=_model_acceptance(tmp_path, manifest),
        omo_root=tmp_path / "omo",
        task_id="KEMS-001",
        production=True,
    )
    assert result["status"] == "blocked"
    assert any(
        item["id"] == "omo_approval"
        and not item["ok"]
        and "not approved" in item["detail"]
        for item in result["checks"]
    )


def test_preflight_rejects_incomplete_manifest_identity(tmp_path, monkeypatch):
    monkeypatch.setenv(
        "BOS_REACHBRIDGE_ENDPOINT", "https://reachbridge.example.test/dispatch"
    )
    monkeypatch.setenv("BOS_REACHBRIDGE_TOKEN", "test-token")
    _approved_task(tmp_path / "omo")
    manifest = _evaluation_manifest(tmp_path)
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    payload.pop("dataset_version")
    payload["samples"][0].pop("annotation_version")
    manifest.write_text(json.dumps(payload), encoding="utf-8")
    result = run_preflight(
        docs_root=_source_tree(tmp_path),
        evaluation_manifest=manifest,
        model_acceptance=None,
        omo_root=tmp_path / "omo",
        task_id="KEMS-001",
        production=True,
    )
    assert result["status"] == "blocked"
    assert any(
        item["id"] == "evaluation_manifest"
        and not item["ok"]
        and "dataset_version" in item["detail"]
        for item in result["checks"]
    )
