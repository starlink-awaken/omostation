from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def _read(rel_path: str) -> str:
    return (REPO_ROOT / rel_path).read_text(encoding="utf-8")


def test_wave2_scripts_drop_user_specific_workspace_literals() -> None:
    daily_backup = _read("scripts/daily-backup.sh")
    restore_backup = _read("scripts/restore-from-backup.sh")
    kos_wrapper = _read("kos-infra/kos")
    scan_hardcoded = _read("bin/scan_hardcoded.sh")
    agora_degrade = _read("tests/integration/test-09-agora-degrade.sh")
    knowledge_pipeline = _read("tests/integration/test-08-knowledge-pipeline.sh")

    assert "/Users/xiamingxing/Workspace" not in daily_backup
    assert "/Users/xiamingxing/Workspace" not in restore_backup
    assert "/Users/xiamingxing/Workspace/Tools/kos" not in kos_wrapper
    assert "/Users/xiamingxing" not in scan_hardcoded
    assert "/Users/xiamingxing" not in agora_degrade
    assert "/Users/xiamingxing" not in knowledge_pipeline

    assert "OMOSTATION_ROOT" in daily_backup
    assert "OMOSTATION_ROOT" in restore_backup
    assert "KOS_ROOT" in kos_wrapper
