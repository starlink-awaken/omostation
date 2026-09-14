import json
import stat
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2] / "scripts"))

from kems_build_annotation_handoff import build_handoff, write_packet  # type: ignore[reportMissingImports]
from kos.kems import AdjudicationStore


def _database(tmp_path: Path) -> Path:
    database = tmp_path / "adjudication.sqlite"
    store = AdjudicationStore(database)
    store.ingest_queue(
        [
            {
                "sample_id": "sample-1",
                "source_sha256": "a" * 64,
                "source_ref": "vault://redacted/one.md",
                "scenario_id": "private-source-review-v1",
                "split": "shadow",
            }
        ]
    )
    return database


def test_build_handoff_contains_only_redacted_metadata(tmp_path: Path) -> None:
    packet = build_handoff(_database(tmp_path))
    assert packet["schema"] == "kems.annotation-handoff.v1"
    assert packet["database"]["sample_count"] == 1
    assert packet["samples"][0]["next_action"] == "claim_and_submit_independent_annotation"
    assert "body" not in json.dumps(packet)
    assert "content" not in json.dumps(packet)


def test_write_packet_is_atomic_and_private(tmp_path: Path) -> None:
    packet = build_handoff(_database(tmp_path))
    output = tmp_path / "evidence" / "handoff.json"
    write_packet(packet, output)
    assert json.loads(output.read_text(encoding="utf-8"))["schema"] == "kems.annotation-handoff.v1"
    assert stat.S_IMODE(output.stat().st_mode) == 0o600
    assert not list(output.parent.glob(".*.tmp"))
