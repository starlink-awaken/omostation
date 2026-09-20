"""Live server value readiness must count only qualifying v2 evidence."""

from __future__ import annotations

from importlib.machinery import SourceFileLoader
from pathlib import Path
import importlib.util
import shutil
import sys
import tempfile

HOST_DIR = Path(__file__).resolve().parents[2] / "bin/panorama/assets/host"


def _module():
    with tempfile.TemporaryDirectory(prefix="live-server-value-readiness-") as directory:
        deployed = Path(directory)
        shutil.copy2(HOST_DIR / "observatory_query.py.asset", deployed / "observatory_query.py")
        server_path = deployed / "live_server_under_test.py"
        shutil.copy2(HOST_DIR / "live_server.py.asset", server_path)
        query_loader = SourceFileLoader(
            "zhixing_observatory_query_value_readiness_test",
            str(deployed / "observatory_query.py"),
        )
        query_spec = importlib.util.spec_from_loader(query_loader.name, query_loader)
        assert query_spec is not None and query_spec.loader is not None
        query_module = importlib.util.module_from_spec(query_spec)
        sys.modules[query_spec.name] = query_module
        query_loader.exec_module(query_module)
        sys.modules["observatory_query"] = query_module
        loader = SourceFileLoader("zhixing_live_server_value_readiness_test", str(server_path))
        spec = importlib.util.spec_from_loader(loader.name, loader)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        return module


def _snapshot(*, validation):
    return {
        "generated_at": "2026-09-20T00:00:00Z",
        "generation_id": "generation",
        "panel_value": {
            "schema": "panel-value/v1",
            "state": "not_proven",
            "state_reason": ["样本 28/30 不足"],
            "samples": {
                "records": 28,
                "qualifying": 1,
                "accepted": 24,
                "adjudicated": 28,
                "net_saved_seconds": 90,
            },
            "thresholds": [
                {"key": "samples", "label": "真实样本", "target": 30, "unit": "个", "comparator": "gte", "current": 1, "met": False, "gate": None},
            ],
        },
        "value_evidence_validation": validation,
    }


def test_legacy_qualifying_is_not_counted_as_business_value():
    module = _module()
    validation = {
        "schema": "value-evidence-validation/v2",
        "ok": True,
        "available": True,
        "records": 20,
        "v2_records": 0,
        "legacy_records": 20,
        "legacy_qualifying": 1,
        "qualifying": 0,
        "target": 30,
    }

    payload = module.value_proof_readiness_payload(_snapshot(validation=validation))

    assert payload["schema_version"] == "agent-value-proof-readiness/v2"
    assert payload["samples"]["qualifying"] == 0
    assert payload["samples"]["remaining"] == 30
    assert payload["samples"]["v2_records"] == 0
    assert payload["samples"]["legacy_qualifying"] == 1
    assert payload["thresholds"][0]["current"] == 0
    assert payload["thresholds"][0]["gate"] == "样本 0/30 不足, 比率不可判定"


def test_v2_qualifying_records_count_toward_target():
    module = _module()
    validation = {
        "schema": "value-evidence-validation/v2",
        "ok": True,
        "available": True,
        "v2_records": 3,
        "legacy_records": 1,
        "legacy_qualifying": 1,
        "qualifying": 2,
        "target": 30,
    }

    payload = module.value_proof_readiness_payload(_snapshot(validation=validation))

    assert payload["samples"]["qualifying"] == 2
    assert payload["samples"]["remaining"] == 28
    assert payload["samples"]["v2_records"] == 3
    assert payload["samples"]["legacy_qualifying"] == 1
    assert payload["thresholds"][0]["current"] == 2


def test_invalid_or_unavailable_validation_fails_closed_to_zero():
    module = _module()
    validation = {
        "schema": "value-evidence-validation/v2",
        "ok": False,
        "available": False,
        "v2_records": 0,
        "legacy_records": 20,
        "legacy_qualifying": 1,
        "qualifying": 99,
        "target": 30,
    }

    payload = module.value_proof_readiness_payload(_snapshot(validation=validation))

    assert payload["samples"]["qualifying"] == 0
    assert payload["samples"]["remaining"] == 30
    assert payload["samples"]["legacy_qualifying"] == 1
