from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[3]
TOOL = ROOT / "bin" / "gac" / "ledger-safe-insert.py"


def _write_case(root: Path, *, item_indent: str = "  ") -> tuple[Path, Path]:
    spec = root / "specs" / "new-bet.md"
    spec.parent.mkdir()
    spec.write_text("# New BET\n", encoding="utf-8")
    digest = "sha256:" + hashlib.sha256(spec.read_bytes()).hexdigest()
    ledger = root / "docs" / "plans" / "3y-bet-ledger.yaml"
    ledger.parent.mkdir(parents=True)
    ledger.write_text(
        "\n".join(
            [
                "version: 1",
                "bets:",
                f"{item_indent}- id: BET-OLD",
                f"{item_indent}  title: Old BET",
                "meta:",
                "  total_bets: 1",
                "",
            ]
        ),
        encoding="utf-8",
    )
    entry = root / "entry.yaml"
    entry.write_text(
        yaml.safe_dump(
            {
                "accepted_specifications": [
                    {
                        "spec_ref": "repo://specs/new-bet.md",
                        "spec_version": "1.0.0",
                        "content_digest": digest,
                        "decision_ref": "decision://accepted/BET-NEW",
                    }
                ],
                "completion_evidence": {
                    "axes": {
                        "engineering": {"evidence": {}, "status": "NOT_STARTED"},
                        "operational": {"evidence": {}, "status": "NOT_PROVEN"},
                        "value": {"evidence": {}, "status": "NOT_PROVEN"},
                    },
                    "overall_state": "evaluating",
                    "schema_version": "completion-evidence-matrix/v1",
                },
                "id": "BET-NEW",
                "title": "New BET",
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    return ledger, entry


@pytest.mark.parametrize("item_indent", ["", "  "])
def test_inserts_mapping_as_bets_list_item_and_updates_count(tmp_path: Path, item_indent: str) -> None:
    ledger, entry = _write_case(tmp_path, item_indent=item_indent)

    result = subprocess.run(
        [sys.executable, str(TOOL), "--file", str(entry), "--ledger", str(ledger)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=True,
    )

    data = yaml.safe_load(ledger.read_text(encoding="utf-8"))
    assert [bet["id"] for bet in data["bets"]] == ["BET-OLD", "BET-NEW"]
    assert "id" not in data
    assert data["meta"]["total_bets"] == 2
    assert "bets now 2" in result.stdout


def test_dry_run_does_not_modify_ledger(tmp_path: Path) -> None:
    ledger, entry = _write_case(tmp_path)
    before = ledger.read_bytes()

    subprocess.run(
        [sys.executable, str(TOOL), "--file", str(entry), "--ledger", str(ledger), "--dry-run"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=True,
    )

    assert ledger.read_bytes() == before
