from __future__ import annotations

import importlib.util
from datetime import UTC, datetime
from pathlib import Path

MODULE_PATH = Path(__file__).parents[1] / "bin/ssot/external-resource-catalog.py"
SPEC = importlib.util.spec_from_file_location("external_resource_catalog", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class _EntryPoint:
    group = "external.resources"
    name = "test-source"

    def load(self):
        return _Provider


class _Provider:
    @staticmethod
    def external_descriptor() -> dict[str, object]:
        return {
            "id": "source:test",
            "kind": "knowledge_source",
            "provider": "test-provider",
            "protocol": "external-resource/v1",
            "capabilities": ["discover", "search"],
            "data_classification": "public",
            "provenance": {"source_ref": "evidence://source/test"},
            "lifecycle": "active",
            "health": {
                "status": "healthy",
                "observed_at": "2026-08-02T00:00:00+00:00",
                "latency_ms": 10,
                "source": "probe:test",
            },
            "owner": "test-owner",
            "version": "1.0.0",
            "permission_ref": "permission://test",
            "mode": "live_query",
            "expires_at": "2099-01-01T00:00:00+00:00",
            "rollback_plan": "disable",
            "metadata": {"raw_content": "must never be exported"},
        }


def test_collects_dynamic_resources_as_read_only_safe_projection(tmp_path: Path) -> None:
    before = sorted(path.relative_to(tmp_path).as_posix() for path in tmp_path.rglob("*"))

    payload = MODULE.collect_external_resources(
        Path(__file__).parents[1],
        entry_points=[_EntryPoint()],
        now=datetime(2026, 8, 2, tzinfo=UTC),
    )

    after = sorted(path.relative_to(tmp_path).as_posix() for path in tmp_path.rglob("*"))
    assert payload["schema"] == "external-resource-catalog/v1"
    assert payload["mode"] == "read_only_projection"
    assert payload["activation"] == "forbidden"
    assert payload["summary"]["resource_count"] == 1
    assert payload["resources"][0]["entry_point"] == "external.resources:test-source"
    assert "metadata" not in payload["resources"][0]
    assert before == after
