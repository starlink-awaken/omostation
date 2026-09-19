import importlib.util
import contextlib
import json
import io
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "bin/ssot/value-recorder.py"


def _module():
    spec = importlib.util.spec_from_file_location("value_recorder_test", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _authority():
    return "sha256:" + "a" * 64


def _baseline(module, tmp_path, baseline_id="baseline-2026q3"):
    return module.freeze_baseline(
        baseline_id=baseline_id,
        metrics={"manual_minutes": 12, "revision_count": 3},
        output_dir=tmp_path / "baselines",
        frozen_at="2026-09-18T00:00:00+00:00",
    )


def _record(module, baseline):
    return module.record_episode(
        review_seconds=30,
        saved_seconds=120,
        verdict="accepted",
        run_id="run-value-001",
        scene_id="scene-value-001",
        decision_id="decision-value-001",
        principal_id="principal:xiamingxing",
        authority_receipt_digest=_authority(),
        baseline_id=baseline["baseline_id"],
        baseline=baseline,
        recorded_at="2026-09-18T01:00:00+00:00",
    )


def test_freeze_baseline_is_digest_bound_and_loadable(tmp_path) -> None:
    module = _module()
    baseline = _baseline(module, tmp_path)
    path = tmp_path / "baselines" / f"{baseline['baseline_id']}.json"
    loaded = json.loads(path.read_text())

    assert loaded["schema"] == "value-baseline/v1"
    assert loaded["digest"] == baseline["digest"]
    assert module.load_baseline(baseline["baseline_id"], tmp_path / "baselines")[0] == baseline

    tampered = dict(loaded)
    tampered["metrics"]["manual_minutes"] = 1
    path.write_text(json.dumps(tampered))
    assert module.load_baseline(
        baseline["baseline_id"], tmp_path / "baselines"
    )[1] == f"baseline digest mismatch: {path}"


def test_v2_record_qualifies_only_with_authority_lineage_and_real_gain(tmp_path) -> None:
    module = _module()
    baseline = _baseline(module, tmp_path)
    episode = _record(module, baseline)

    assert episode["schema"] == "value-evidence/v2"
    assert episode["qualifying"] is True
    assert episode["net_saved_seconds"] == 90
    assert episode["source_class"] == "real_human"
    assert episode["authority_receipt_digest"].startswith("sha256:")

    nonqualifying = module.record_episode(
        review_seconds=120,
        saved_seconds=120,
        verdict="accepted",
        run_id="run-value-001",
        scene_id="scene-value-001",
        decision_id="decision-value-001",
        principal_id="principal:xiamingxing",
        authority_receipt_digest=_authority(),
        baseline_id=baseline["baseline_id"],
        baseline=baseline,
    )
    assert nonqualifying["qualifying"] is False
    assert nonqualifying["net_saved_seconds"] == 0


def test_validate_evidence_accepts_v2_and_ignores_legacy_nonqualifying(tmp_path) -> None:
    module = _module()
    baseline = _baseline(module, tmp_path)
    episode = _record(module, baseline)
    evidence = tmp_path / "value-evidence.jsonl"
    evidence.write_text(
        json.dumps({"schema": module.EVIDENCE_SCHEMA_V1, "qualifying": False}) + "\n" +
        json.dumps(episode) + "\n",
        encoding="utf-8",
    )

    report = module.validate_evidence(evidence, tmp_path / "baselines")

    assert report["ok"] is True
    assert report["records"] == 2
    assert report["v2_records"] == 1
    assert report["qualifying"] == 1
    assert report["remaining_to_target"] == 29


def test_validate_evidence_excludes_legacy_qualifying_from_v2_target(tmp_path) -> None:
    module = _module()
    baseline = _baseline(module, tmp_path)
    episode = _record(module, baseline)
    legacy_qualifying = {
        "schema": module.EVIDENCE_SCHEMA_V1,
        "qualifying": True,
        "net_saved_seconds": 90,
        "run_id": "legacy-run-001",
    }
    evidence = tmp_path / "value-evidence.jsonl"
    evidence.write_text(
        json.dumps(legacy_qualifying) + "\n" +
        json.dumps(episode) + "\n",
        encoding="utf-8",
    )

    report = module.validate_evidence(evidence, tmp_path / "baselines")

    assert report["ok"] is True
    assert report["records"] == 2
    assert report["v2_records"] == 1
    assert report["legacy_records"] == 1
    assert report["legacy_qualifying"] == 1
    assert report["qualifying"] == 1
    assert report["remaining_to_target"] == 29


def test_validate_evidence_does_not_count_legacy_only_as_target_progress(tmp_path) -> None:
    module = _module()
    legacy_qualifying = {
        "schema": module.EVIDENCE_SCHEMA_V1,
        "qualifying": True,
        "net_saved_seconds": 90,
        "run_id": "legacy-run-001",
    }
    evidence = tmp_path / "value-evidence.jsonl"
    evidence.write_text(json.dumps(legacy_qualifying) + "\n", encoding="utf-8")

    report = module.validate_evidence(evidence, tmp_path / "baselines")

    assert report["ok"] is True
    assert report["v2_records"] == 0
    assert report["legacy_qualifying"] == 1
    assert report["qualifying"] == 0
    assert report["remaining_to_target"] == 30


def test_validate_evidence_reports_missing_baseline_binding(tmp_path) -> None:
    module = _module()
    baseline = _baseline(module, tmp_path)
    episode = _record(module, baseline)
    episode["baseline_digest"] = "sha256:" + "b" * 64
    evidence = tmp_path / "value-evidence.jsonl"
    evidence.write_text(json.dumps(episode) + "\n", encoding="utf-8")

    report = module.validate_evidence(evidence, tmp_path / "baselines")

    assert report["ok"] is False
    assert report["issues"] == [{"line": "1", "reason": "baseline digest binding mismatch"}]


def test_validate_evidence_rejects_record_before_baseline_freeze(tmp_path) -> None:
    module = _module()
    baseline = _baseline(module, tmp_path)
    episode = _record(module, baseline)
    episode["timestamp"] = "2026-09-18T00:00:00+00:00"
    evidence = tmp_path / "value-evidence.jsonl"
    evidence.write_text(json.dumps(episode) + "\n", encoding="utf-8")

    report = module.validate_evidence(evidence, tmp_path / "baselines")

    assert report["ok"] is False
    assert report["issues"] == [{
        "line": "1",
        "reason": "record timestamp must be after baseline frozen_at",
    }]


def test_record_episode_rejects_record_at_baseline_freeze(tmp_path) -> None:
    module = _module()
    baseline = _baseline(module, tmp_path)

    try:
        module.record_episode(
            review_seconds=30,
            saved_seconds=120,
            verdict="accepted",
            run_id="run-value-001",
            scene_id="scene-value-001",
            decision_id="decision-value-001",
            principal_id="principal:xiamingxing",
            authority_receipt_digest=_authority(),
            baseline_id=baseline["baseline_id"],
            baseline=baseline,
            recorded_at="2026-09-18T00:00:00+00:00",
        )
    except ValueError as exc:
        assert str(exc) == "record timestamp must be after baseline frozen_at"
    else:
        raise AssertionError("pre-window record was accepted")


def test_validate_cli_accepts_explicit_runtime_paths(tmp_path, monkeypatch) -> None:
    module = _module()
    evidence = tmp_path / "value-evidence.jsonl"
    baseline_dir = tmp_path / "baselines"
    seen = {}

    def fake_validate(path, directory):
        seen["evidence"] = path
        seen["baseline_dir"] = directory
        return {
            "schema": "value-evidence-validation/v2",
            "ok": True,
            "records": 0,
            "v2_records": 0,
            "qualifying": 0,
            "target": 30,
            "remaining_to_target": 30,
            "issues": [],
        }

    monkeypatch.setattr(module, "validate_evidence", fake_validate)
    monkeypatch.setattr(module.sys, "argv", [
        "value-recorder.py", "validate",
        "--evidence", str(evidence),
        "--baseline-dir", str(baseline_dir),
    ])

    assert module.main() == 0
    assert seen["evidence"] == evidence
    assert seen["baseline_dir"] == baseline_dir


def test_validate_cli_can_emit_machine_readable_json(tmp_path, monkeypatch) -> None:
    module = _module()
    report = {
        "schema": "value-evidence-validation/v2",
        "ok": True,
        "records": 0,
        "v2_records": 0,
        "qualifying": 0,
        "target": 30,
        "remaining_to_target": 30,
        "issues": [],
    }
    monkeypatch.setattr(module, "validate_evidence", lambda *_: report)
    monkeypatch.setattr(module.sys, "argv", [
        "value-recorder.py", "validate",
        "--evidence", str(tmp_path / "value-evidence.jsonl"),
        "--baseline-dir", str(tmp_path / "baselines"),
        "--json",
    ])
    output = io.StringIO()

    with contextlib.redirect_stdout(output):
        assert module.main() == 0

    assert json.loads(output.getvalue()) == report
