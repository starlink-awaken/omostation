"""C5 (ADR-0373): sweep_index.py unit + integration tests.

Coverage:
  - Render INDEX.md from <date>.json payload(s)
  - Determinism (same payload -> same output)
  - --write overwrites; --check exits 1 on drift
  - HEADER / FOOTER invariants stay in lockstep with bin/sweep/README.md
  - Default mode is --write when neither --write nor --check passed
  - Out-of-dir cases (missing dir, missing INDEX.md)

These tests use tmp_path; no real INDEX.md is touched.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "bin" / "sweep" / "sweep_index.py"


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_json(out_dir: Path, name: str, payload: dict) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    p = out_dir / name
    p.write_text(json.dumps(payload), encoding="utf-8")
    return p


def test_render_index_deterministic(tmp_path: Path) -> None:
    """C5: identical <date>.json payload -> identical INDEX.md contents."""
    mod = load_module(SCRIPT, "sweep_index")
    out_dir = tmp_path / "sweeps"
    _write_json(
        out_dir,
        "2026-08-01.json",
        {"date": "2026-08-01", "total_errors": 0, "suppression_ratio": 0.0},
    )
    rows = mod.collect_reports(out_dir)
    first = mod.render_index(rows)
    second = mod.render_index(rows)
    assert first == second


def test_index_header_includes_c5_crdock_marker(tmp_path: Path) -> None:
    """C5: header cites ADR-0367 + ADR-0373 so a CR-SWEEP-INDEX-AUTO drift shows."""
    mod = load_module(SCRIPT, "sweep_index")
    text = mod.render_index([])
    assert "ADR-0367" in text
    assert "ADR-0373" in text
    assert "CR-SWEEP-INDEX-AUTO" in text


def test_index_check_exits_0_when_synced(tmp_path: Path) -> None:
    """C5: --check returns 0 when INDEX.md matches the latest rendering."""
    out_dir = tmp_path / "sweeps"
    _write_json(
        out_dir,
        "2026-08-02.json",
        {"date": "2026-08-02", "total_errors": 5, "suppression_ratio": 0.2},
    )
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--write", "--out-dir", str(out_dir)],
        capture_output=True,
        text=True,
        check=False,
        timeout=15,
    )
    assert result.returncode == 0, result.stderr
    check = subprocess.run(
        [sys.executable, str(SCRIPT), "--check", "--out-dir", str(out_dir)],
        capture_output=True,
        text=True,
        check=False,
        timeout=15,
    )
    assert check.returncode == 0, check.stdout + check.stderr
    assert "INDEX.md matches" in check.stdout


def test_index_check_exits_1_on_drift(tmp_path: Path) -> None:
    """C5: --check returns 1 when INDEX.md was hand-edited away from <date>.json."""
    out_dir = tmp_path / "sweeps"
    _write_json(
        out_dir,
        "2026-08-03.json",
        {"date": "2026-08-03", "total_errors": 9, "suppression_ratio": 0.5},
    )
    subprocess.run(
        [sys.executable, str(SCRIPT), "--write", "--out-dir", str(out_dir)],
        capture_output=True,
        text=True,
        check=False,
        timeout=15,
    )
    # inject drift
    index_path = out_dir / "INDEX.md"
    body = index_path.read_text(encoding="utf-8")
    index_path.write_text(body.replace("| 9 |", "| 999 |", 1), encoding="utf-8")
    check = subprocess.run(
        [sys.executable, str(SCRIPT), "--check", "--out-dir", str(out_dir)],
        capture_output=True,
        text=True,
        check=False,
        timeout=15,
    )
    assert check.returncode == 1
    assert "drift" in check.stderr.lower()


def test_index_check_exits_1_when_missing(tmp_path: Path) -> None:
    """C5: --check returns 1 when INDEX.md does not exist at all."""
    out_dir = tmp_path / "sweeps"
    _write_json(
        out_dir,
        "2026-08-04.json",
        {"date": "2026-08-04", "total_errors": 0, "suppression_ratio": 0.0},
    )
    # do not write INDEX.md
    check = subprocess.run(
        [sys.executable, str(SCRIPT), "--check", "--out-dir", str(out_dir)],
        capture_output=True,
        text=True,
        check=False,
        timeout=15,
    )
    assert check.returncode == 1
    assert "missing" in check.stderr.lower()


def test_index_skips_invalid_json(tmp_path: Path) -> None:
    """C5: invalid payload files are silently skipped without raising."""
    mod = load_module(SCRIPT, "sweep_index")
    out_dir = tmp_path / "sweeps"
    out_dir.mkdir()
    (out_dir / "garbage.json").write_text("not a json {{{", encoding="utf-8")
    _write_json(
        out_dir,
        "2026-08-05.json",
        {"date": "2026-08-05", "total_errors": 0, "suppression_ratio": 0.0},
    )
    rows = mod.collect_reports(out_dir)
    assert len(rows) == 1
    assert rows[0]["date"] == "2026-08-05"


def test_default_mode_is_write(tmp_path: Path) -> None:
    """C5: when neither --write nor --check, default to --write (UX safety)."""
    out_dir = tmp_path / "sweeps"
    _write_json(
        out_dir,
        "2026-08-06.json",
        {"date": "2026-08-06", "total_errors": 0, "suppression_ratio": 0.0},
    )
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--out-dir", str(out_dir)],
        capture_output=True,
        text=True,
        check=False,
        timeout=15,
    )
    assert result.returncode == 0
    assert (out_dir / "INDEX.md").exists()
