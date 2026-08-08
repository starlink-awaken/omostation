"""ADR-0375 G5: gac-ingest-legacy check_drift container-semantics tests.

Locks the P79-container behavior: each legacy source FILE (X1/X2/X4
policies + L0 constraints) must be covered by ≥1 indexed container rule
(CR-*-SSOT) whose source_ref points at it. The old per-rule set-diff
always reported 104 missing + 4 ghost (index container id ≠ rule id
inside the source file).
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "bin" / "gac" / "gac-ingest-legacy.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("gac_ingest_legacy_test", SCRIPT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def gil():
    import sys as _sys

    bin_gac = str(ROOT / "bin" / "gac")
    if bin_gac not in _sys.path:
        _sys.path.insert(0, bin_gac)
    return _load_module()


def test_live_registry_has_no_legacy_drift(gil) -> None:
    """G5 live check: all 4 legacy sources covered, no ghosts."""
    drift = gil.check_drift()
    assert drift["ok"] is True, f"unexpected drift: {drift}"
    assert drift["source_count"] == 4
    assert len(drift["covered_files"]) == 4
    assert drift["missing"] == []
    assert drift["ghost"] == []


def test_all_legacy_sources_are_known(gil) -> None:
    """G5: LEGACY_SOURCES covers the 4 canonical SSOT files."""
    files = {s["file"] for s in gil.LEGACY_SOURCES}
    assert files == {
        ".omo/_truth/x1-governance-policies.yaml",
        ".omo/_truth/x2-freshness-rules.yaml",
        ".omo/_truth/x4-consistency-rules.yaml",
        "projects/ecos/src/ecos/ssot/registry/L0-constraints.yaml",
    }


def test_container_rule_covers_file(gil, monkeypatch, tmp_path) -> None:
    """G5 unit: an indexed rule whose source_ref points at the file covers it."""
    monkeypatch.setattr(gil, "WORKSPACE", tmp_path)
    src_file = ".omo/_truth/x1-policies.yaml"
    full = tmp_path / src_file
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text("policies:\n- policy_id: X1-C01\n", encoding="utf-8")
    monkeypatch.setattr(gil, "LEGACY_SOURCES", [{
        "file": src_file,
        "sections": ["policies"],
        "id_key": "policy_id",
        "dimension": "X1",
        "layer": "meta",
    }])

    fake_registry = tmp_path / "registry.yaml"
    fake_registry.write_text(
        "gac:\n  rules:\n"
        "  - id: CR-X1-POLICIES-SSOT\n"
        "    source_type: indexed\n"
        f"    source_ref: {src_file}::policies\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(gil, "REGISTRY", fake_registry)

    drift = gil.check_drift()
    assert drift["ok"] is True
    assert src_file in drift["covered_files"]


def test_missing_container_rule_flags_source(gil, monkeypatch, tmp_path) -> None:
    """G5 unit: legacy source with NO covering indexed rule → missing."""
    monkeypatch.setattr(gil, "WORKSPACE", tmp_path)
    src_file = ".omo/_truth/x2-rules.yaml"
    full = tmp_path / src_file
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text("rules:\n- rule_id: X2-FRESH-ADR-DRIFT\n", encoding="utf-8")
    monkeypatch.setattr(gil, "LEGACY_SOURCES", [{
        "file": src_file,
        "sections": ["rules"],
        "id_key": "rule_id",
        "dimension": "X2",
        "layer": "meta",
    }])

    fake_registry = tmp_path / "registry.yaml"
    # No indexed rule covers src_file
    fake_registry.write_text(
        "gac:\n  rules:\n  - id: CR-UNRELATED\n    source_type: native\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(gil, "REGISTRY", fake_registry)

    drift = gil.check_drift()
    assert drift["ok"] is False
    assert src_file in drift["missing"]


def test_ghost_container_for_deleted_source(gil, monkeypatch, tmp_path) -> None:
    """G5 unit: indexed rule points at a legacy file that no longer exists → ghost."""
    monkeypatch.setattr(gil, "WORKSPACE", tmp_path)
    deleted_path = ".omo/_truth/x4-gone.yaml"  # does NOT exist under tmp WORKSPACE
    monkeypatch.setattr(gil, "LEGACY_SOURCES", [{
        "file": deleted_path,
        "sections": ["rules"],
        "id_key": "rule_id",
        "dimension": "X4",
        "layer": "meta",
    }])

    fake_registry = tmp_path / "registry.yaml"
    fake_registry.write_text(
        "gac:\n  rules:\n"
        "  - id: CR-X4-CONSISTENCY-SSOT\n"
        "    source_type: indexed\n"
        f"    source_ref: {deleted_path}::rules\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(gil, "REGISTRY", fake_registry)

    drift = gil.check_drift()
    assert drift["ok"] is False
    assert "CR-X4-CONSISTENCY-SSOT" in drift["ghost"]


def test_cli_check_exits_zero_on_clean(gil) -> None:
    """G5 end-to-end: --check --json exits 0 on the live registry."""
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--check", "--json"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert result.returncode == 0, (result.stdout, result.stderr)
    payload = json.loads(result.stdout)
    assert payload["ok"] is True


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
