from __future__ import annotations

import hashlib
import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[3]
TOOL = ROOT / "bin" / "gac" / "ledger-safe-insert.py"
LEDGER_CLI = ROOT / "bin" / "plan" / "bet-ledger.py"


def _load_ledger_cli():
    spec = importlib.util.spec_from_file_location("bet_ledger_test_module", LEDGER_CLI)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


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
                "campaigns: []",
                "concurrency: {}",
                "disciplines: {}",
                "gates: {}",
                "meta:",
                "  total_bets: 1",
                "milestones: []",
                "objectives: []",
                "retro: {}",
                "tracks: {}",
                "vision: {}",
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


def _run_insert(ledger: Path, entry: Path, *, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(TOOL), "--file", str(entry), "--ledger", str(ledger)],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )


def test_rejects_missing_required_root_section(tmp_path: Path) -> None:
    ledger, entry = _write_case(tmp_path)
    ledger.write_text(ledger.read_text(encoding="utf-8").replace("vision: {}\n", ""), encoding="utf-8")

    result = _run_insert(ledger, entry, cwd=tmp_path)

    assert result.returncode != 0
    assert "root missing required section: vision" in result.stderr


def test_rejects_wrong_root_section_type(tmp_path: Path) -> None:
    ledger, entry = _write_case(tmp_path)
    ledger.write_text(ledger.read_text(encoding="utf-8").replace("tracks: {}\n", "tracks: []\n"), encoding="utf-8")

    result = _run_insert(ledger, entry, cwd=tmp_path)

    assert result.returncode != 0
    assert "tracks: expected mapping" in result.stderr


def test_rejects_invalid_bet_entry_type(tmp_path: Path) -> None:
    ledger, entry = _write_case(tmp_path)
    ledger.write_text(
        ledger.read_text(encoding="utf-8").replace("  - id: BET-OLD\n    title: Old BET\n", "  - invalid\n"),
        encoding="utf-8",
    )

    result = _run_insert(ledger, entry, cwd=tmp_path)

    assert result.returncode != 0
    assert "bets[0]: expected mapping" in result.stderr


def test_rejects_duplicate_bet_id(tmp_path: Path) -> None:
    ledger, entry = _write_case(tmp_path)
    entry.write_text(entry.read_text(encoding="utf-8").replace("BET-NEW", "BET-OLD"), encoding="utf-8")

    result = _run_insert(ledger, entry, cwd=tmp_path)

    assert result.returncode != 0
    assert "duplicate BET id: BET-OLD" in result.stderr


def test_rejects_misplaced_bet_shaped_entry(tmp_path: Path) -> None:
    ledger, entry = _write_case(tmp_path)
    ledger.write_text(
        ledger.read_text(encoding="utf-8").replace(
            "campaigns: []\n",
            "campaigns:\n- id: BET-OUTSIDE\n  title: misplaced\n",
        ),
        encoding="utf-8",
    )

    result = _run_insert(ledger, entry, cwd=tmp_path)

    assert result.returncode != 0
    assert "campaigns[0] contains misplaced BET id: BET-OUTSIDE" in result.stderr


def test_reports_yaml_parse_location_and_context(tmp_path: Path) -> None:
    ledger, entry = _write_case(tmp_path)
    ledger.write_text(
        "bets:\n- id: BET-OLD\n  title: [unclosed\n",
        encoding="utf-8",
    )

    result = _run_insert(ledger, entry, cwd=tmp_path)

    assert result.returncode != 0
    assert "YAML_PARSE_ERROR" in result.stderr
    assert "line " in result.stderr and ", column " in result.stderr
    assert "context:" in result.stderr


def test_loader_uses_same_structural_contract(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ledger, _ = _write_case(tmp_path)
    module = _load_ledger_cli()
    module.LEDGER = ledger
    monkeypatch.chdir(tmp_path)

    assert module.load()["bets"][0]["id"] == "BET-OLD"

    ledger.write_text(ledger.read_text(encoding="utf-8").replace("vision: {}\n", ""), encoding="utf-8")
    with pytest.raises(SystemExit, match="root missing required section: vision"):
        module.load()


def test_loader_rejects_multiple_yaml_documents(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ledger, _ = _write_case(tmp_path)
    ledger.write_text(ledger.read_text(encoding="utf-8") + "---\nbets: []\n", encoding="utf-8")
    module = _load_ledger_cli()
    module.LEDGER = ledger
    monkeypatch.chdir(tmp_path)

    with pytest.raises(SystemExit, match="YAML_DOCUMENT_COUNT_ERROR"):
        module.load()
