from __future__ import annotations

import importlib.util
import json
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
            "metadata": {"internal": "must never be exported"},
        }

    @staticmethod
    def health_probe() -> dict[str, object]:
        return {
            "status": "healthy",
            "observed_at": "2026-08-02T00:00:00+00:00",
            "latency_ms": 12,
            "source": "probe:test",
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
    assert payload["resources"][0]["health"]["source"] == "probe:test"
    assert "metadata" not in payload["resources"][0]
    assert before == after


def test_failed_probe_isolated_and_explicitly_unavailable() -> None:
    class FailingProvider:
        @staticmethod
        def external_descriptor() -> dict[str, object]:
            return _Provider.external_descriptor()

        @staticmethod
        def health_probe() -> dict[str, object]:
            raise RuntimeError("provider must stay isolated")

    class FailingEntryPoint:
        group = "external.resources"
        name = "failing-source"

        @staticmethod
        def load():
            return FailingProvider

    payload = MODULE.collect_external_resources(
        Path(__file__).parents[1],
        entry_points=[FailingEntryPoint()],
        now=datetime(2026, 8, 2, tzinfo=UTC),
    )

    resource = payload["resources"][0]
    assert resource["availability"] == "unavailable"
    assert "provider_probe_failed" in resource["reason_codes"]
    assert payload["errors"][0]["error"] == "RuntimeError"


def test_descriptor_only_mode_does_not_claim_live_availability() -> None:
    payload = MODULE.collect_external_resources(
        Path(__file__).parents[1],
        entry_points=[_EntryPoint()],
        now=datetime(2026, 8, 2, tzinfo=UTC),
        probe=False,
    )

    assert payload["resources"][0]["availability"] == "unavailable"
    assert payload["errors"][0]["error"] == "health_probe_skipped"


def test_previous_snapshot_produces_safe_change_report() -> None:
    previous = {
        "schema": "external-resource-catalog/v1",
        "observed_at": "2026-08-01T00:00:00+00:00",
        "resources": [
            {
                "id": "source:test",
                "availability": "available",
                "health": {"status": "healthy"},
            }
        ],
        "errors": [],
    }
    current = {
        "schema": "external-resource-catalog/v1",
        "observed_at": "2026-08-02T00:00:00+00:00",
        "resources": [
            {
                "id": "source:test",
                "availability": "unavailable",
                "health": {"status": "unhealthy"},
            },
            {"id": "source:new", "availability": "proposal_only"},
        ],
        "errors": [
            {
                "entry_point": "external.resources:broken",
                "status": "unavailable",
                "error": "ImportError",
            }
        ],
    }

    diff = MODULE._load_agora(Path(__file__).parents[1])[1](previous, current)

    assert diff["schema"] == "external-resource-catalog-diff/v1"
    assert [item["id"] for item in diff["changes"]] == ["source:new", "source:test"]
    assert diff["summary"]["changed_count"] == 1
    assert diff["summary"]["error_change_count"] == 1


def test_observe_routes_safe_catalog_through_omo_broker(monkeypatch) -> None:
    calls: list[tuple[tuple[str, ...], str | None]] = []

    def fake_omo(_root, args, *, input_text=None):
        calls.append((args, input_text))
        if args[:2] == ("external-resources", "latest"):
            return {"ok": True, "observation": None}
        assert args[:2] == ("external-resources", "observe")
        assert input_text and json.loads(input_text)["activation"] == "forbidden"
        return {
            "ok": True,
            "status": "recorded",
            "observation": {
                "schema": "external-resource-observation/v1",
                "observation_id": "observation:test",
            },
        }

    monkeypatch.setattr(MODULE, "_run_omo", fake_omo)
    payload = MODULE.observe_external_resources(
        Path(__file__).parents[1],
        entry_points=[_EntryPoint()],
        now=datetime(2026, 8, 2, tzinfo=UTC),
    )

    assert payload["schema"] == "external-resource-observation-result/v1"
    assert payload["status"] == "recorded"
    assert len(calls) == 2
