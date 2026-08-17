from __future__ import annotations

import json
from pathlib import Path

from kos.kems import evaluate_candidate

from scripts.kems_record_model_acceptance import main


def _report() -> dict[str, object]:
    return evaluate_candidate(
        [{"case_id": "case-1", "predictions": [2, 2], "actual": [2, 3], "baseline_value": 4}],
        candidate_model_id="moving-average-v1",
    )


def test_recorder_is_idempotent_and_persists_redacted_report(tmp_path: Path, capsys) -> None:
    report_path = tmp_path / "acceptance.json"
    database_path = tmp_path / "acceptance.sqlite"
    report_path.write_text(json.dumps(_report()), encoding="utf-8")

    assert main(["--report", str(report_path), "--run-id", "run-1", "--database", str(database_path)]) == 0
    assert main(["--report", str(report_path), "--run-id", "run-1", "--database", str(database_path)]) == 0

    output = capsys.readouterr().out
    assert '"inserted": true' in output
    assert '"inserted": false' in output


def test_recorder_rejects_raw_content_and_promotion(tmp_path: Path, capsys) -> None:
    report_path = tmp_path / "acceptance.json"
    report_path.write_text(json.dumps(_report() | {"metadata": {"text": "private"}}), encoding="utf-8")
    assert main(["--report", str(report_path), "--run-id", "run-raw", "--database", str(tmp_path / "db")]) == 1
    assert "raw content" in capsys.readouterr().out

    report_path.write_text(json.dumps(_report() | {"promotion": "approved"}), encoding="utf-8")
    assert main(["--report", str(report_path), "--run-id", "run-approved", "--database", str(tmp_path / "db")]) == 1
    assert "cannot authorize" in capsys.readouterr().out
