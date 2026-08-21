"""Contract tests for the single capability registry spine."""

from __future__ import annotations

import ast
import copy
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
SYNC_PATH = ROOT / "bin" / "capability-sync.py"
GENERATOR_PATH = ROOT / "bin" / "cockpit" / "gen-capability-registry.py"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def cap_sync():
    return _load("capability_sync_contract", SYNC_PATH)


@pytest.fixture(scope="module")
def generator():
    return _load("capability_registry_generator", GENERATOR_PATH)


@pytest.fixture
def registry() -> dict:
    return {
        "version": "1.0.0",
        "generated_at": "1970-01-01T00:00:00Z",
        "generator": "bin/cockpit/gen-capability-registry.py",
        "totals": {
            "mcp_servers": 1,
            "mcp_tools": 2,
            "bos_services": 1,
            "bos_domains": 1,
            "cli_commands": 1,
        },
        "mcp_servers": [
            {
                "id": "omo",
                "name": "OMO",
                "layer": "L2",
                "file": "projects/omo/src/omo/mcp_server.py",
                "transport": "stdio",
                "exists": True,
                "tools": ["status", "shared"],
                "tool_count": 2,
            }
        ],
        "bos_services": {
            "_domain_counts": {"governance": 1},
            "domains": {
                "governance": [
                    {
                        "uri": "bos://governance/shared",
                        "description": "shared governance service",
                        "transport": "internal",
                        "status": "active",
                    }
                ]
            },
        },
        "cli_commands": [{"name": "status", "description": "show status"}],
    }


def test_canonical_generator_declares_registry_contract(cap_sync, generator) -> None:
    registry = generator.build_registry()

    assert registry["schema"] == "capability-registry/v1"
    assert registry["owner"] == "workspace-capability-governance"
    assert registry["writer"] == "bin/cockpit/gen-capability-registry.py"
    assert cap_sync.CANONICAL_REGISTRY_METADATA == {
        "schema": generator.REGISTRY_SCHEMA,
        "owner": generator.REGISTRY_OWNER,
        "writer": generator.REGISTRY_WRITER,
    }


def test_sync_and_check_follow_canonical_writer_behavior(cap_sync, generator, tmp_path: Path) -> None:
    output = tmp_path / "capability-registry.yaml"

    assert cap_sync.main(["sync", "--registry", str(output)]) == 0
    assert output.read_text(encoding="utf-8") == generator.render_yaml(generator.build_registry())

    before = output.read_bytes()
    assert cap_sync.main(["check", "--registry", str(output)]) == 0
    assert output.read_bytes() == before

    output.write_text(output.read_text(encoding="utf-8") + "# drift\n", encoding="utf-8")
    drifted = output.read_bytes()
    assert cap_sync.main(["check", "--registry", str(output)]) == 1
    assert output.read_bytes() == drifted


def test_generator_check_detects_drift_without_writing(generator, tmp_path: Path) -> None:
    registry = generator.build_registry()
    output = tmp_path / "capability-registry.yaml"
    expected = generator.render_yaml(registry)
    output.write_text(expected, encoding="utf-8")

    assert generator.check_yaml(registry, output) is True
    output.write_text(expected + "# drift\n", encoding="utf-8")
    before = output.read_bytes()

    assert generator.check_yaml(registry, output) is False
    assert output.read_bytes() == before


def test_make_and_ci_run_blocking_canonical_check() -> None:
    completed = subprocess.run(
        ["make", "check-capability-registry"],
        cwd=ROOT,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr

    workflow = yaml.safe_load((ROOT / ".github/workflows/ci-lint.yml").read_text(encoding="utf-8"))
    job = workflow["jobs"]["capability-registry-drift"]
    assert job.get("continue-on-error", False) is False
    checkout_step = next(step for step in job["steps"] if step.get("uses") == "actions/checkout@v4")
    assert checkout_step.get("continue-on-error", False) is False
    check_step = next(step for step in job["steps"] if step.get("name") == "Check capability registry drift")
    assert check_step["run"].strip() == "python3 bin/cockpit/gen-capability-registry.py --check --quiet"


def test_python39_grammar_is_supported() -> None:
    for path in (SYNC_PATH, GENERATOR_PATH):
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path), feature_version=(3, 9))


def test_schema_v1_without_new_metadata_remains_readable(cap_sync, registry: dict, tmp_path: Path) -> None:
    path = tmp_path / "registry.yaml"
    path.write_text(yaml.safe_dump(registry, sort_keys=False), encoding="utf-8")

    loaded = cap_sync.load_registry(path)

    assert loaded["version"] == "1.0.0"
    assert cap_sync.resolve_capability(loaded, capability_id="mcp-server:omo").status == "resolved"


def test_canonical_registry_metadata_is_accepted(cap_sync, registry: dict, tmp_path: Path) -> None:
    registry.update(
        {
            "schema": "capability-registry/v1",
            "owner": "workspace-capability-governance",
            "writer": "bin/cockpit/gen-capability-registry.py",
        }
    )
    path = tmp_path / "registry.yaml"
    path.write_text(yaml.safe_dump(registry, sort_keys=False), encoding="utf-8")

    assert cap_sync.load_registry(path)["owner"] == "workspace-capability-governance"


@pytest.mark.parametrize(
    ("field", "value", "reason"),
    [
        ("schema", "capability-registry/v999", "registry_schema_invalid"),
        ("owner", "untrusted-writer", "registry_owner_invalid"),
        ("writer", "bin/capability-sync.py", "registry_writer_invalid"),
    ],
)
def test_noncanonical_registry_metadata_is_rejected(
    cap_sync, registry: dict, tmp_path: Path, field: str, value: str, reason: str
) -> None:
    registry.update(
        {
            "schema": "capability-registry/v1",
            "owner": "workspace-capability-governance",
            "writer": "bin/cockpit/gen-capability-registry.py",
        }
    )
    registry[field] = value
    path = tmp_path / "registry.yaml"
    path.write_text(yaml.safe_dump(registry, sort_keys=False), encoding="utf-8")

    with pytest.raises(cap_sync.RegistryError, match=reason):
        cap_sync.load_registry(path)


def test_partial_registry_metadata_is_not_grandfathered(cap_sync, registry: dict, tmp_path: Path) -> None:
    registry["schema"] = "capability-registry/v1"
    path = tmp_path / "registry.yaml"
    path.write_text(yaml.safe_dump(registry, sort_keys=False), encoding="utf-8")

    with pytest.raises(cap_sync.RegistryError, match="registry_metadata_incomplete"):
        cap_sync.load_registry(path)


@pytest.mark.parametrize(
    ("capability_id", "kind", "adapter"),
    [
        ("mcp-server:omo", "mcp_server", "mcp_native"),
        ("mcp-tool:omo:status", "mcp_tool", "mcp_native"),
        ("bos-service:bos://governance/shared", "bos_service", "bos_native"),
        ("cli-command:status", "cli_command", "cockpit_native"),
    ],
)
def test_find_resolves_only_exact_ids(cap_sync, registry: dict, capability_id: str, kind: str, adapter: str) -> None:
    result = cap_sync.resolve_capability(registry, capability_id=capability_id)

    assert result.status == "resolved"
    assert result.capability["id"] == capability_id
    assert result.capability["kind"] == kind
    assert result.capability["adapter"]["kind"] == adapter


def test_query_rejects_ambiguity_instead_of_first_match(cap_sync, registry: dict) -> None:
    result = cap_sync.resolve_capability(registry, query="shared")

    assert result.status == "ambiguous"
    assert result.capability is None
    assert result.candidate_ids == (
        "bos-service:bos://governance/shared",
        "mcp-tool:omo:shared",
    )


def test_duplicate_exact_id_is_ambiguous(cap_sync, registry: dict) -> None:
    registry["mcp_servers"].append(dict(registry["mcp_servers"][0]))

    result = cap_sync.resolve_capability(registry, capability_id="mcp-server:omo")

    assert result.status == "ambiguous"
    assert result.capability is None


def test_not_found_is_explicit(cap_sync, registry: dict) -> None:
    result = cap_sync.resolve_capability(registry, capability_id="mcp-tool:omo:missing")

    assert result.status == "not_found"
    assert result.capability is None
    assert result.candidate_ids == ()


def test_unavailable_mcp_server_and_tools_cannot_resolve(cap_sync, registry: dict) -> None:
    unavailable = copy.deepcopy(registry["mcp_servers"][0])
    unavailable.update({"id": "c2g", "name": "C2G", "exists": False, "tools": ["c2g_bet"]})
    registry["mcp_servers"].append(unavailable)

    assert cap_sync.resolve_capability(registry, capability_id="mcp-server:c2g").status == "not_found"
    assert cap_sync.resolve_capability(registry, capability_id="mcp-tool:c2g:c2g_bet").status == "not_found"
    assert cap_sync.resolve_capability(registry, query="c2g").status == "not_found"


@pytest.mark.parametrize("selector", [{"capability_id": "missing"}, {"query": "shared"}])
def test_negative_receipt_is_privacy_safe(cap_sync, registry: dict, selector: dict) -> None:
    result = cap_sync.resolve_capability(registry, **selector)
    receipt = cap_sync.build_resolution_receipt(result, b"registry-content", selector)
    encoded = json.dumps(receipt, ensure_ascii=False, sort_keys=True)

    assert receipt["schema"] == "capability-resolution-receipt/v1"
    assert receipt["status"] in {"not_found", "ambiguous"}
    assert receipt["admission"] == {"required": True, "decision": "not_evaluated"}
    assert receipt["invocation"]["allowed"] is False
    assert receipt["invocation"]["route"] == "native_adapter_only"
    assert "missing" not in encoded
    assert "shared" not in encoded
    assert "prompt" not in encoded
    assert "environment" not in encoded
    assert str(ROOT) not in encoded


def test_resolved_receipt_cannot_be_used_as_direct_invocation(cap_sync, registry: dict) -> None:
    selector = {"capability_id": "mcp-tool:omo:status"}
    result = cap_sync.resolve_capability(registry, **selector)
    receipt = cap_sync.build_resolution_receipt(result, b"registry-content", selector)

    assert receipt["capability_id"] == "mcp-tool:omo:status"
    assert receipt["adapter"] == {"kind": "mcp_native", "target": "omo/status"}
    assert receipt["invocation"] == {
        "allowed": False,
        "route": "native_adapter_only",
        "reason": "admission_not_evaluated",
    }


def test_find_cli_returns_receipt_and_distinct_fail_closed_codes(
    cap_sync, registry: dict, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "registry.yaml"
    path.write_text(yaml.safe_dump(registry, sort_keys=False), encoding="utf-8")

    assert cap_sync.main(["find", "--id", "mcp-tool:omo:status", "--registry", str(path)]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "resolved"

    assert cap_sync.main(["find", "--id", "missing", "--registry", str(path)]) == 2
    assert json.loads(capsys.readouterr().out)["status"] == "not_found"

    assert cap_sync.main(["find", "--query", "shared", "--registry", str(path)]) == 3
    assert json.loads(capsys.readouterr().out)["status"] == "ambiguous"


class _FakeGateway:
    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def load(self, record: dict, *, selector: dict) -> dict:
        self.calls.append(("load", record, selector))
        return {
            "schema": "capability-invocation-receipt/v1",
            "operation": "load",
            "status": "ready",
            "capability_id": record["id"],
            "invocation_attempted": False,
        }

    def invoke(self, record: dict, payload: object, *, selector: dict) -> dict:
        self.calls.append(("invoke", record, payload, selector))
        return {
            "schema": "capability-invocation-receipt/v1",
            "operation": "invoke",
            "status": "succeeded",
            "capability_id": record["id"],
            "invocation_attempted": True,
        }


def _native_service() -> SimpleNamespace:
    return SimpleNamespace(
        uri="bos://governance/shared",
        transport="internal",
        action="audit",
        description="shared governance service",
    )


def test_native_record_requires_exact_internal_bos_truth(cap_sync, registry: dict) -> None:
    record = cap_sync.build_native_bos_record(
        registry,
        "bos-service:bos://governance/shared",
        [_native_service()],
    )

    assert record == {
        "id": "bos-service:bos://governance/shared",
        "source": "agora.bos",
        "status": "active",
        "native_bos_uri": "bos://governance/shared",
        "kind": "bos_service",
        "transport": "bos_native",
        "operation": "audit",
        "adapter": {"kind": "bos_native", "target": "bos://governance/shared"},
        "description": "shared governance service",
    }


@pytest.mark.parametrize(
    ("capability_id", "transport", "service_transport", "reason"),
    [
        ("mcp-tool:omo:status", "internal", "internal", "unsupported_capability_kind"),
        ("bos-service:bos://governance/shared", "stdio", "internal", "bos_transport_not_internal"),
        ("bos-service:bos://governance/shared", "internal", "stdio", "runtime_transport_not_internal"),
    ],
)
def test_native_record_rejects_legacy_or_noninternal_paths(
    cap_sync,
    registry: dict,
    capability_id: str,
    transport: str,
    service_transport: str,
    reason: str,
) -> None:
    registry["bos_services"]["domains"]["governance"][0]["transport"] = transport
    service = _native_service()
    service.transport = service_transport

    with pytest.raises(cap_sync.GatewayError, match=reason):
        cap_sync.build_native_bos_record(registry, capability_id, [service])


def test_gateway_operations_are_explicit_and_do_not_spawn_provider_processes(
    cap_sync, registry: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    gateway = _FakeGateway()

    def forbidden_subprocess(*args, **kwargs):
        raise AssertionError("provider subprocess execution is forbidden")

    monkeypatch.setattr(cap_sync.subprocess, "run", forbidden_subprocess)

    load_receipt = cap_sync.execute_gateway_operation(
        registry,
        "load",
        "bos-service:bos://governance/shared",
        gateway=gateway,
        service_catalog=[_native_service()],
    )
    invoke_receipt = cap_sync.execute_gateway_operation(
        registry,
        "invoke",
        "bos-service:bos://governance/shared",
        payload={"scope": "bounded"},
        gateway=gateway,
        service_catalog=[_native_service()],
    )

    assert load_receipt["status"] == "ready"
    assert invoke_receipt["status"] == "succeeded"
    assert [call[0] for call in gateway.calls] == ["load", "invoke"]
    assert gateway.calls[1][2] == {"scope": "bounded"}


def test_native_router_requires_lifecycle_catalogs_before_seed(cap_sync) -> None:
    events = []

    class Router:
        _capability_catalog = None
        _admission_catalog = None

        def enable_capability_gating(self) -> None:
            events.append("enable")

        def seed_from_poc(self, services: list) -> None:
            events.append("seed")

    with pytest.raises(cap_sync.GatewayError, match="lifecycle_catalog_unavailable"):
        cap_sync._prepare_native_router(Router(), [_native_service()])

    assert events == ["enable"]


def test_native_router_enables_lifecycle_before_exact_route_seed(cap_sync) -> None:
    events = []

    class Router:
        _capability_catalog = None
        _admission_catalog = None

        def enable_capability_gating(self) -> None:
            events.append("enable")
            self._capability_catalog = object()
            self._admission_catalog = object()

        def seed_from_poc(self, services: list) -> None:
            events.append(("seed", [service.uri for service in services]))

    router = Router()
    assert cap_sync._prepare_native_router(router, [_native_service()]) is router
    assert events == ["enable", ("seed", ["bos://governance/shared"])]


def test_load_and_invoke_cli_require_exact_id_and_structured_input(cap_sync) -> None:
    parser = cap_sync._parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["load", "--query", "shared"])
    with pytest.raises(SystemExit):
        parser.parse_args(["invoke", "--id", "bos-service:x", "--", "--unsafe"])
    with pytest.raises(SystemExit):
        parser.parse_args(["invoke", "--id", "bos-service:x"])


def test_invoke_cli_delegates_only_to_gateway_and_emits_safe_receipt(
    cap_sync,
    registry: dict,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry_path = tmp_path / "registry.yaml"
    registry_path.write_text(yaml.safe_dump(registry, sort_keys=False), encoding="utf-8")
    payload_path = tmp_path / "payload.json"
    payload_path.write_text('{"scope":"bounded"}', encoding="utf-8")
    gateway = _FakeGateway()
    monkeypatch.setattr(
        cap_sync,
        "_load_native_gateway",
        lambda capability_id: (gateway, [_native_service()]),
    )

    assert (
        cap_sync.main(
            [
                "invoke",
                "--id",
                "bos-service:bos://governance/shared",
                "--input-json",
                str(payload_path),
                "--registry",
                str(registry_path),
            ]
        )
        == 0
    )
    receipt = json.loads(capsys.readouterr().out)
    encoded = json.dumps(receipt, sort_keys=True)
    assert receipt["schema"] == "capability-invocation-receipt/v1"
    assert receipt["status"] == "succeeded"
    assert "bounded" not in encoded
    assert str(payload_path) not in encoded


def test_gateway_unavailable_fails_closed_without_echoing_sensitive_selector(
    cap_sync,
    registry: dict,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry_path = tmp_path / "registry.yaml"
    registry_path.write_text(yaml.safe_dump(registry, sort_keys=False), encoding="utf-8")

    def unavailable(capability_id: str):
        raise cap_sync.GatewayError("gateway_unavailable")

    monkeypatch.setattr(cap_sync, "_load_native_gateway", unavailable)
    secret_id = "bos-service:bos://secret/private"

    assert cap_sync.main(["load", "--id", secret_id, "--registry", str(registry_path)]) == 5
    receipt = json.loads(capsys.readouterr().out)
    encoded = json.dumps(receipt, sort_keys=True)
    assert receipt["status"] == "rejected"
    assert receipt["error_code"] == "CAPABILITY_GATEWAY_UNAVAILABLE"
    assert secret_id not in encoded
