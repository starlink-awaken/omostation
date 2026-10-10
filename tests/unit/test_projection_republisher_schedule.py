"""The republisher's skip threshold must not let a scheduled lease expire."""

from __future__ import annotations

import importlib.util
from datetime import timedelta
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "bin/panorama/projection-republisher.py"
REGISTRY = ROOT / ".omo/_truth/registry/services.yaml"


def _load_republisher():
    spec = importlib.util.spec_from_file_location("projection_republisher", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_renew_threshold_covers_launchd_interval_within_lease() -> None:
    republisher = _load_republisher()
    registry = next(
        document
        for document in yaml.safe_load_all(REGISTRY.read_text(encoding="utf-8"))
        if isinstance(document, dict) and "services" in document
    )
    services = registry["services"]
    service = next(item for item in services if item.get("id") == "omostation.zhixing-projection-republisher")
    interval = service["interval_sec"]

    minimum_threshold = timedelta(seconds=interval) + republisher.RENEWAL_JITTER_MARGIN
    assert republisher.RENEW_THRESHOLD >= minimum_threshold
    assert republisher.RENEW_THRESHOLD < republisher.LEASE
