import sys
from pathlib import Path

import pytest

from bin.delivery.physical_recovery import run_live_drill


def _replay_command() -> list[str]:
    return [sys.executable, "-c", "print('replay-receipt')"]


def test_live_drill_records_four_digests_and_human_reference(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "facts.txt").write_text("approved fixture\n", encoding="utf-8")
    backup = tmp_path / "backup"
    restored = tmp_path / "restored"
    evidence = tmp_path / "evidence"

    report = run_live_drill(
        source=source,
        backup_dir=backup,
        restore_dir=restored,
        human_confirmation_ref="human://operator/recovery-1",
        replay_command=_replay_command(),
        out_dir=evidence,
    )

    assert report["executed"] is True
    assert report["integrity_ok"] is True
    assert report["human_confirmed"] is True
    assert report["meets_physical_gate"] is True
    assert report["source_digest"] == report["backup_digest"] == report["restored_digest"]
    assert report["replay_digest"]
    assert Path(report["receipt_path"]).is_file()
    assert source.is_dir() and backup.is_dir() and not restored.exists()


def test_live_drill_rejects_source_or_nonempty_restore_before_write(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "facts.txt").write_text("x\n", encoding="utf-8")
    restored = tmp_path / "restored"
    restored.mkdir()
    (restored / "existing").write_text("keep\n", encoding="utf-8")
    backup = tmp_path / "backup"

    with pytest.raises(ValueError, match="restore target must be empty"):
        run_live_drill(
            source=source,
            backup_dir=backup,
            restore_dir=restored,
            human_confirmation_ref="human://operator/recovery-1",
            replay_command=_replay_command(),
        )
    assert not backup.exists()
    assert (restored / "existing").read_text(encoding="utf-8") == "keep\n"

    with pytest.raises(ValueError, match="must not overlap source"):
        run_live_drill(
            source=source,
            backup_dir=source / "backup",
            restore_dir=tmp_path / "restored-2",
            human_confirmation_ref="human://operator/recovery-1",
            replay_command=_replay_command(),
        )


def test_live_drill_without_human_confirmation_never_writes(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "facts.txt").write_text("x\n", encoding="utf-8")
    backup = tmp_path / "backup"
    restored = tmp_path / "restored"

    report = run_live_drill(
        source=source,
        backup_dir=backup,
        restore_dir=restored,
        human_confirmation_ref=None,
        replay_command=_replay_command(),
    )

    assert report["executed"] is False
    assert report["human_confirmed"] is False
    assert report["meets_physical_gate"] is False
    assert not backup.exists()
    assert not restored.exists()


def test_live_drill_replay_failure_does_not_pass_gate(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "facts.txt").write_text("x\n", encoding="utf-8")

    report = run_live_drill(
        source=source,
        backup_dir=tmp_path / "backup",
        restore_dir=tmp_path / "restored",
        human_confirmation_ref="human://operator/recovery-1",
        replay_command=[sys.executable, "-c", "raise SystemExit(7)"],
        out_dir=tmp_path / "evidence",
    )

    assert report["executed"] is False
    assert report["replay_ok"] is False
    assert report["meets_physical_gate"] is False
