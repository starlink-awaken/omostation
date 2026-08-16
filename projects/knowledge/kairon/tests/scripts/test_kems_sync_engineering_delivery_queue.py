from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "kos" / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from kems_sync_engineering_delivery_queue import sync_queue  # type: ignore[reportMissingImports]
from kos.kems import AdjudicationStore
from test_kems_build_engineering_delivery_queue import projection


def test_sync_queue_is_idempotent_and_persists_redacted_metadata(tmp_path: Path) -> None:
    input_path = tmp_path / "review.json"
    input_path.write_text(json.dumps(projection()), encoding="utf-8")
    database = tmp_path / "adjudication.sqlite"
    evidence = tmp_path / "evidence" / "engineering.jsonl"

    first = sync_queue(input_path, database, evidence)
    second = sync_queue(input_path, database, evidence)

    assert first["sample_count"] == 1
    assert first["inserted_count"] == 1
    assert second["inserted_count"] == 0
    assert (
        AdjudicationStore(database).list_items(status="pending")[0]["scenario_id"] == "engineering-delivery-review-v1"
    )
    assert "delivery-1" not in evidence.read_text(encoding="utf-8")
