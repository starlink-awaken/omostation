import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
from gac_daemon import daemon_handle_event


def test_handle_constraint_changed():
    result = daemon_handle_event("constraint.changed", {"id": "X1-C04"})
    assert result in ("regenerated", "verified", "alerted")


def test_handle_unknown_event():
    result = daemon_handle_event("unknown.type", {})
    assert result == "unknown"
