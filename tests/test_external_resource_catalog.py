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
    assert payload["catalog_ttl_seconds"] == 3600
    assert payload["summary"]["resource_count"] == 1
    assert payload["resources"][0]["entry_point"] == "external.resources:test-source"
    assert payload["resources"][0]["health"]["source"] == "probe:test"
    assert "metadata" not in payload["resources"][0]
    assert before == after


def test_builds_capability_directory_with_governed_next_steps() -> None:
    catalog = {
        "schema": "external-resource-catalog/v1",
        "observed_at": "2026-08-02T00:00:00+00:00",
        "resources": [
            {
                "id": "source:available",
                "kind": "knowledge_source",
                "provider": "research-provider",
                "capabilities": ["read", "search"],
                "lifecycle": "active",
                "availability": "available",
                "mode": "live_query",
                "data_classification": "public",
                "permission_ref": "permission://research",
                "health": {
                    "status": "healthy",
                    "observed_at": "2026-08-02T00:00:00+00:00",
                    "source": "probe:research",
                },
                "reason_codes": [],
            },
            {
                "id": "method:proposal",
                "kind": "method_pack",
                "provider": "method-provider",
                "capabilities": ["explain", "evaluate"],
                "lifecycle": "sandbox",
                "availability": "proposal_only",
                "mode": "proposal_only",
                "data_classification": "public",
                "permission_ref": "permission://method",
                "health": {"status": "healthy"},
                "reason_codes": ["proposal_only"],
            },
            {
                "id": "source:stale",
                "kind": "data_source",
                "provider": "data-provider",
                "capabilities": ["query"],
                "lifecycle": "active",
                "availability": "stale",
                "mode": "governed_snapshot",
                "data_classification": "private",
                "permission_ref": "permission://data",
                "health": {"status": "healthy"},
                "reason_codes": ["health_stale"],
            },
        ],
        "errors": [],
    }

    directory = MODULE.build_external_resource_directory_snapshot(catalog)

    assert directory["schema"] == "external-resource-directory/v1"
    assert directory["activation"] == "forbidden"
    assert directory["provider_invocation"] is False
    assert directory["capability_index"]["search"]["available_resource_ids"] == [
        "source:available"
    ]
    assert directory["capability_index"]["query"]["available_resource_ids"] == []
    assert directory["summary"]["capability_count"] == 5
    assert directory["summary"]["unavailable_count"] == 1
    assert {item["resource_id"]: item["next_step"] for item in directory["next_steps"]} == {
        "source:available": "route_evaluation",
        "method:proposal": "proposal_or_evaluation",
        "source:stale": "health_probe",
    }
    assert directory["directory_digest"].startswith("sha256:")


def test_directory_rejects_observe_combination_at_cli_boundary() -> None:
    assert MODULE.main(["--directory", "--observe"]) == 2


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


def test_evaluates_catalog_with_scene_binding_without_activation() -> None:
    payload = MODULE.collect_external_resources(
        Path(__file__).parents[1],
        entry_points=[_EntryPoint()],
        now=datetime(2026, 8, 2, tzinfo=UTC),
    )

    evaluation = MODULE.evaluate_external_resources(
        Path(__file__).parents[1],
        payload,
        capability="search",
        scene_binding={
            "scene_id": "research-brief",
            "journey_id": "weekly-decision",
            "outcome_metric": "decision_latency_hours",
            "data_scope": "public:research",
            "operator": "human:test",
            "permission_ref": "permission://test",
        },
        trace_id="trace-catalog-evaluation",
        now=datetime(2026, 8, 2, tzinfo=UTC),
    )

    assert evaluation["schema"] == "external-resource-evaluation/v1"
    assert evaluation["activation"] == "forbidden"
    assert evaluation["selected_resource_id"] == "source:test"
    assert evaluation["summary"]["eligible_count"] == 1


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
    assert diff["summary"]["review_required"] is True
    assert diff["summary"]["review_required_count"] == 1
    assert diff["summary"]["operational_observation_count"] == 1


def test_observe_routes_safe_catalog_through_omo_broker(monkeypatch) -> None:
    calls: list[tuple[tuple[str, ...], str | None]] = []

    def fake_omo(_root, args, *, input_text=None):
        calls.append((args, input_text))
        if args[:2] == ("external-resources", "latest"):
            return {"ok": True, "observation": None}
        if args[:2] == ("external-resources", "record-observation-run"):
            run = json.loads(input_text or "{}")
            assert run["schema"] == "external-resource-observation-run/v1"
            assert run["provider_business_invocation"] is False
            return {
                "ok": True,
                "status": "recorded",
                "receipt": {
                    "schema": "external-resource-observation-run/v1",
                    "receipt_id": "external-observation-run:test",
                },
            }
        assert args[:2] == ("external-resources", "observe")
        assert input_text and json.loads(input_text)["activation"] == "forbidden"
        return {
            "ok": True,
            "status": "recorded",
            "observation": {
                "schema": "external-resource-observation/v1",
                "observation_id": "observation:test",
                "catalog_digest": "sha256:catalog-test",
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
    assert payload["observation_run"]["schema"] == "external-resource-observation-run/v1"
    assert payload["observation_run_status"] == "recorded"
    assert len(calls) == 3


def test_empty_catalog_is_unavailable_not_success(monkeypatch) -> None:
    run_payloads: list[dict[str, object]] = []

    def fake_omo(_root, args, *, input_text=None):
        if args[:2] == ("external-resources", "latest"):
            return {"ok": True, "observation": None}
        if args[:2] == ("external-resources", "observe"):
            return {
                "ok": True,
                "status": "recorded",
                "observation": {
                    "schema": "external-resource-observation/v1",
                    "observation_id": "observation:empty",
                    "catalog_digest": "sha256:empty",
                },
            }
        run_payloads.append(json.loads(input_text or "{}"))
        return {"ok": True, "status": "recorded", "receipt": {"receipt_id": "run:empty"}}

    monkeypatch.setattr(MODULE, "_run_omo", fake_omo)
    MODULE.observe_external_resources(
        Path(__file__).parents[1], entry_points=[], now=datetime(2026, 8, 2, tzinfo=UTC)
    )

    assert run_payloads[0]["result_state"] == "unavailable"
