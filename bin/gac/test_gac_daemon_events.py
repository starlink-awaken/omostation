import importlib.util
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

_spec = importlib.util.spec_from_file_location(
    "gac_daemon",
    os.path.join(os.path.dirname(__file__), "gac-daemon.py"),
)
gac_daemon = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gac_daemon)
daemon_handle_event = gac_daemon.daemon_handle_event


def test_handle_constraint_changed():
    result = daemon_handle_event("constraint.changed", {"id": "X1-C04"})
    assert result in ("regenerated", "verified", "alerted")


def test_handle_unknown_event():
    result = daemon_handle_event("unknown.type", {})
    assert result == "unknown"
