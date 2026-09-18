"""Canonical runtime projection selection for state freshness checks."""
from __future__ import annotations

import importlib.util
from datetime import UTC, datetime, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
SCRIPT = REPO / "bin/gac/state-freshness-check.py"


def _module():
    spec = importlib.util.spec_from_file_location("state_freshness_canonical", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_check_file_prefers_canonical_and_falls_back_to_legacy(
    tmp_path, monkeypatch
) -> None:
    module = _module()
    monkeypatch.setattr(module, "WORKSPACE", tmp_path)
    now = datetime.now(UTC)
    legacy = tmp_path / ".omo/state/system_health.yaml"
    canonical = tmp_path / ".omo/state/runtime/system_health.yaml"
    legacy.parent.mkdir(parents=True)
    canonical.parent.mkdir(parents=True)
    legacy.write_text(f"last_scan: {(now - timedelta(hours=100)).timestamp()}\n")
    canonical.write_text(f"last_scan: {(now - timedelta(hours=1)).timestamp()}\n")

    result = module.check_file(".omo/state/system_health.yaml", now=now)
    assert result["checked_path"] == ".omo/state/runtime/system_health.yaml"
    assert result["source"] == "canonical"
    assert result["ok"] is True

    canonical.unlink()
    legacy.write_text(f"last_scan: {(now - timedelta(hours=1)).timestamp()}\n")
    result = module.check_file(".omo/state/system_health.yaml", now=now)
    assert result["checked_path"] == ".omo/state/system_health.yaml"
    assert result["source"] == "legacy"
    assert result["ok"] is True
