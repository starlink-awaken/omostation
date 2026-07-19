"""Drive network_path helpers (no reimplementation)."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DELIVERY = ROOT / "bin" / "delivery"


def _load():
    path = DELIVERY / "network_path.py"
    name = "delivery_network_path"
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader
    sys.path.insert(0, str(DELIVERY))
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_classify_iface_unknown_none():
    mod = _load()
    assert mod._classify_iface(None) == "unknown"


def test_probe_path_loopback_or_local_shape():
    """probe_path returns structured dict; may be wifi/unknown on this host."""
    mod = _load()
    # Use a private LAN IP even if unreachable — structure must exist
    p = mod.probe_path("127.0.0.1")
    assert "peer_ip" in p
    assert "link_class" in p
    assert "recommendation" in p
    assert p["peer_ip"] == "127.0.0.1"
