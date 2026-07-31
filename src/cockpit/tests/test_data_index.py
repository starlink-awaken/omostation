from __future__ import annotations

import time
from pathlib import Path

from cockpit.data_index import build_data_index, sweep_tmp_data


def _seed_workspace_root(root: Path) -> None:
    (root / ".omo").mkdir()
    (root / "spaces").mkdir()
    (root / "data" / "db").mkdir(parents=True)
    (root / "data" / "backups").mkdir(parents=True)
    (root / "data" / "imports").mkdir(parents=True)
    (root / "data" / "tmp").mkdir(parents=True)
    (root / "runtime" / "logs").mkdir(parents=True)
    (root / "spaces" / "registry.yaml").write_text(
        "\n".join(
            [
                "apiVersion: omo/v1",
                "kind: SpaceRegistry",
                "spaces:",
                "  - id: system-space",
                "    roots:",
                "      data: data",
                "      runtime: runtime",
            ]
        )
        + "\n"
    )
    (root / "data" / "db" / "workspace.sqlite").write_text("db")
    (root / "data" / "backups" / "snapshot.tar").write_text("backup")
    (root / "data" / "imports" / "seed.json").write_text("{}")


def test_build_data_index_creates_metadata_catalog_and_seed_types(tmp_path: Path) -> None:
    _seed_workspace_root(tmp_path)

    result = build_data_index(tmp_path)

    catalog_path = tmp_path / "data" / "_index" / "catalog.json"
    types_path = tmp_path / "data" / "_index" / "types.json"
    policy_path = tmp_path / "data" / "_index" / "gc-policy.json"

    assert catalog_path.exists()
    assert types_path.exists()
    assert policy_path.exists()
    assert result["registry_ref"] == "spaces/registry.yaml"
    assert "data/db" in result["directories"]
    assert "data/backups" in result["directories"]
    assert len(result["types"]) >= 5
    assert {item["id"] for item in result["types"]} >= {
        "sqlite_database",
        "backup_archive",
        "json_document",
        "runtime_log",
        "temporary_artifact",
    }


def test_sweep_tmp_data_only_deletes_expired_files_inside_data_tmp(tmp_path: Path) -> None:
    _seed_workspace_root(tmp_path)
    build_data_index(tmp_path)
    tmp_root = tmp_path / "data" / "tmp"
    old_tmp = tmp_root / "old.tmp"
    fresh_tmp = tmp_root / "fresh.tmp"
    outside_tmp = tmp_path / "runtime" / "logs" / "keep.log"
    old_tmp.write_text("old")
    fresh_tmp.write_text("fresh")
    outside_tmp.write_text("keep")

    stale_time = time.time() - 3 * 24 * 60 * 60
    fresh_time = time.time() - 60
    for candidate, timestamp in ((old_tmp, stale_time), (fresh_tmp, fresh_time), (outside_tmp, stale_time)):
        Path(candidate).touch()
        import os

        os.utime(candidate, (timestamp, timestamp))

    result = sweep_tmp_data(tmp_path, max_age_seconds=24 * 60 * 60)

    assert result["deleted_paths"] == ["data/tmp/old.tmp"]
    assert old_tmp.exists() is False
    assert fresh_tmp.exists() is True
    assert outside_tmp.exists() is True
