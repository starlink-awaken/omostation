from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "bin" / "gac" / "compound-attribution-report.py"
SPEC = importlib.util.spec_from_file_location("compound_attribution_report", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
report = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(report)


def _value_snapshot() -> dict:
    return {
        "schema": "value-truth-snapshot/v1",
        "status": "collecting",
        "observed_at": "2026-08-20T04:30:00Z",
        "source": {
            "ref": "repo://runtime/omo/event-ledger.sqlite3",
            "query_digest": f"sha256:{'a' * 64}",
            "event_count": 9,
        },
        "truth_axes": {
            "engineering_delivery": "not_measured",
            "operational_proof": "proven",
            "personal_value": "collecting",
        },
        "metrics": {
            "current_week_qualifying_outcomes": 1,
            "four_week_value_gate": "collecting",
        },
    }


def test_attribution_uses_evidence_inputs_and_marks_unmeasured_claims_unprovable():
    data = report.generate_attribution_data(
        value_truth=_value_snapshot(),
        bet_summary={"total": 120, "by_status": {"done": 119, "candidate": 1}},
        observed_at="2026-08-20T04:30:00Z",
    )

    assert data["schema"] == "compound-attribution-report/v2"
    assert data["truth_axes"]["personal_value"] == "collecting"
    assert data["engineering"]["bets"] == {
        "total": 120,
        "by_status": {"done": 119, "candidate": 1},
        "source": "repo://docs/plans/3y-bet-ledger.yaml",
    }
    for key in (
        "parallel_acceleration_ratio",
        "local_tokens_substituted",
        "commercial_cost_saved_usd",
        "ttft_speedup_ratio",
        "chaos_interception_rate",
        "regulatory_violations",
        "merkle_integrity",
    ):
        assert data["unproven_claims"][key] == {"status": "unprovable", "value": None}


def test_rendered_report_does_not_restate_legacy_hardcoded_success_claims():
    data = report.generate_attribution_data(
        value_truth=_value_snapshot(),
        bet_summary={"total": 120, "by_status": {"done": 119, "candidate": 1}},
        observed_at="2026-08-20T04:30:00Z",
    )

    rendered = report.render_markdown_report(data)

    assert "个人价值轴: **collecting**" in rendered
    assert "0ms" not in rendered
    assert "12.4x" not in rendered
    assert "485,000,000" not in rendered
    assert "100.0% 清盘" not in rendered
    assert "UNPROVABLE" in rendered


def test_missing_value_receipt_cannot_generate_a_successful_report():
    data = report.generate_attribution_data(
        value_truth=None,
        bet_summary={"total": 120, "by_status": {"done": 119, "candidate": 1}},
        observed_at="2026-08-20T04:30:00Z",
    )

    assert data["truth_axes"]["operational_proof"] == "unprovable"
    assert data["truth_axes"]["personal_value"] == "unprovable"
    assert data["status"] == "unprovable"


def test_malformed_query_digest_cannot_be_used_as_value_evidence():
    malformed = _value_snapshot()
    malformed["source"]["query_digest"] = "sha256:not-a-digest"

    data = report.generate_attribution_data(
        value_truth=malformed,
        bet_summary={"total": 120, "by_status": {"done": 119, "candidate": 1}},
        observed_at="2026-08-20T04:30:00Z",
    )

    assert data["status"] == "unprovable"
    assert data["truth_axes"]["personal_value"] == "unprovable"


def test_receipt_must_match_fresh_live_remeasurement(tmp_path):
    receipt = _value_snapshot()
    receipt["truth_axes"]["personal_value"] = "passed"
    receipt["status"] = "passed"
    path = tmp_path / "receipt.json"
    path.write_text(json.dumps(receipt), encoding="utf-8")
    db_path = tmp_path / "ledger.sqlite3"
    db_path.write_bytes(b"ledger")

    verified = report.load_verified_value_truth(
        path,
        db_path=db_path,
        principal_id="principal-private",
        measure=lambda **kwargs: _value_snapshot(),
    )

    assert verified is None


def test_exact_receipt_is_accepted_only_after_live_remeasurement(tmp_path):
    receipt = _value_snapshot()
    path = tmp_path / "receipt.json"
    path.write_text(json.dumps(receipt), encoding="utf-8")
    db_path = tmp_path / "ledger.sqlite3"
    db_path.write_bytes(b"ledger")

    verified = report.load_verified_value_truth(
        path,
        db_path=db_path,
        principal_id="principal-private",
        measure=lambda **kwargs: _value_snapshot(),
    )

    assert verified == receipt


def test_report_allowlists_value_fields_instead_of_copying_arbitrary_payloads():
    snapshot = _value_snapshot()
    snapshot["source"]["absolute_path"] = "/Users/private/secret.sqlite3"
    snapshot["source"]["integrity"] = {"ok": True, "total": 9, "raw_error": "PRIVATE MEDICAL NOTE"}
    snapshot["metrics"]["raw_prompt"] = "sensitive prompt body"
    snapshot["metrics"]["weekly_samples"] = [{"raw_note": "PRIVATE MEDICAL NOTE"}]

    data = report.generate_attribution_data(
        value_truth=snapshot,
        bet_summary={"total": 1, "by_status": {"candidate": 1}},
        observed_at="2026-08-20T04:30:00Z",
    )

    rendered = json.dumps(data, ensure_ascii=False)
    assert "/Users/private" not in rendered
    assert "sensitive prompt body" not in rendered
    assert "PRIVATE MEDICAL NOTE" not in rendered


def test_cli_keeps_python39_compatible_timezone_imports():
    source = SCRIPT.read_text(encoding="utf-8")

    assert "from datetime import UTC" not in source
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), "--json"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 2
    assert json.loads(completed.stdout)["status"] == "unprovable"


def test_cli_without_explicit_output_does_not_overwrite_repository_report():
    report_path = ROOT / "docs" / "reports" / "2026-compound-attribution-report.md"
    before = report_path.read_bytes()

    completed = subprocess.run(
        [sys.executable, str(SCRIPT)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 2
    assert json.loads(completed.stdout)["status"] == "unprovable"
    assert report_path.read_bytes() == before
