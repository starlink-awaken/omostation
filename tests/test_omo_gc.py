from __future__ import annotations

import os
import time
from pathlib import Path

import yaml
from omo.omo_gc import archive_resolved_debt_items


def test_archive_resolved_debt_items_moves_only_old_resolved_entries(
    tmp_path: Path,
) -> None:
    omo_dir = tmp_path / ".omo"
    debt_dir = omo_dir / "debt" / "items"
    debt_dir.mkdir(parents=True, exist_ok=True)

    old_resolved = debt_dir / "DEBT-OLD.yaml"
    old_resolved.write_text(
        yaml.safe_dump(
            {"id": "DEBT-OLD", "resolved": True}, sort_keys=False, allow_unicode=True
        ),
        encoding="utf-8",
    )
    fresh_resolved = debt_dir / "DEBT-FRESH.yaml"
    fresh_resolved.write_text(
        yaml.safe_dump(
            {"id": "DEBT-FRESH", "resolved": True}, sort_keys=False, allow_unicode=True
        ),
        encoding="utf-8",
    )
    old_open = debt_dir / "DEBT-OPEN.yaml"
    old_open.write_text(
        yaml.safe_dump(
            {"id": "DEBT-OPEN", "resolved": False}, sort_keys=False, allow_unicode=True
        ),
        encoding="utf-8",
    )

    now = time.time()
    old_mtime = now - (8 * 24 * 3600)
    os.utime(old_resolved, (old_mtime, old_mtime))
    os.utime(old_open, (old_mtime, old_mtime))

    compacted = archive_resolved_debt_items(
        omo_dir,
        now=now,
        older_than_seconds=7 * 24 * 3600,
    )

    assert compacted == 1
    assert not old_resolved.exists()
    assert (omo_dir / "debt" / "archive" / "DEBT-OLD.yaml").exists()
    assert fresh_resolved.exists()
    assert old_open.exists()
