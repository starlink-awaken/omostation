from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
GAC_DIR = ROOT / "bin" / "gac"
sys.path.insert(0, str(GAC_DIR))

_spec = importlib.util.spec_from_file_location("gac_daemon", GAC_DIR / "gac-daemon.py")
assert _spec is not None and _spec.loader is not None
gac_daemon = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gac_daemon)
daemon_handle_event = gac_daemon.daemon_handle_event


def test_handle_constraint_changed() -> None:
    result = daemon_handle_event("constraint.changed", {"id": "X1-C04"})
    assert result in ("regenerated", "verified", "alerted")


def test_handle_unknown_event() -> None:
    result = daemon_handle_event("unknown.type", {})
    assert result == "unknown"
