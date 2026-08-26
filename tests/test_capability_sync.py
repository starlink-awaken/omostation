"""Contract tests for the single capability registry spine."""

from __future__ import annotations

import ast
import copy
import hashlib
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
GENERATOR_PATH = ROOT / "bin" / "ssot" / "gen-capability-registry.py"


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
        "generator": "bin/ssot/gen-capability-registry.py",
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
    assert registry["writer"] == "bin/ssot/gen-capability-registry.py"
    assert cap_sync.CANONICAL_REGISTRY_METADATA == {
        "schema": generator.REGISTRY_SCHEMA,
        "owner": generator.REGISTRY_OWNER,
        "writer": generator.REGISTRY_WRITER,
    }


def test_projection_and_index_include_canonical_skills_and_workflows(generator, cap_sync) -> None:
    registry = generator.build_registry()

    assert any(row["id"] == "git-discipline" for row in registry["skills"])
    assert any(row["id"] == "bet-execution" for row in registry["workflows"])
    index = cap_sync.build_capability_index(registry)
    assert index["skill:git-discipline"][0]["kind"] == "skill"
    assert index["workflow:bet-execution"][0]["kind"] == "workflow"


def test_old_projection_without_skills_or_workflows_stays_discoverable(cap_sync, registry: dict) -> None:
    index = cap_sync.build_capability_index(registry)

    assert "skill:git-discipline" not in index
    assert "workflow:bet-execution" not in index
    assert index["mcp-tool:omo:status"][0]["kind"] == "mcp_tool"


def test_trace_binding_compatibility_symbols_remain_available(cap_sync) -> None:
    for name in (
        "TraceBindingError",
        "_digest",
        "_canonical_json",
        "validate_trace_binding",
        "validate_trace_bound_resolution_receipt",
        "_native_owner",
        "_validate_capability_binding",
        "_trace_projection",
    ):
        assert callable(getattr(cap_sync, name))


def test_generated_projection_is_explicitly_non_authoritative_and_uses_vendored_c2g_source(generator) -> None:
    """The generated catalog remains a projection, not an authority or a C2G fallback."""
    registry = generator.build_registry()
    rendered = generator.render_yaml(registry)
    c2g = next(server for server in registry["mcp_servers"] if server["id"] == "c2g")

    assert "generated projection, not SSOT / 不是 SSOT" in rendered
    assert "全生态能力注册表 SSOT" not in rendered
    assert c2g["file"] == "projects/omo/src/omo/_vendored/c2g/mcp_server.py"
    assert c2g["exists"] == (generator.WORKSPACE / c2g["file"]).is_file()


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
    assert check_step["run"].strip() == "python3 bin/ssot/gen-capability-registry.py --check --quiet"


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
            "writer": "bin/ssot/gen-capability-registry.py",
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
            "writer": "bin/ssot/gen-capability-registry.py",
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


def _trace_binding() -> dict[str, str]:
    return {
        "correlation_id": "corr-b4b-001",
        "workflow_run_id": "run-b4b-001",
        "packet_id": "packet-b4b-001",
        "packet_hash": "sha256:" + "a" * 64,
        "assignment_id": "assignment-b4b-001",
        "dispatch_id": "dispatch-b4b-001",
        "actor_id": "blueprint-trace-binding",
        "delivery_attempt_id": "b4-b-20260823-01",
    }


def _canonical_trace_registry(registry: dict) -> dict:
    result = copy.deepcopy(registry)
    result.update(
        {
            "schema": "capability-registry/v1",
            "owner": "workspace-capability-governance",
            "writer": "bin/ssot/gen-capability-registry.py",
        }
    )
    return result


def test_find_binding_json_is_read_only_and_rejects_query_selector(registry: dict, tmp_path: Path) -> None:
    registry_path = tmp_path / "capability-registry.yaml"
    registry_path.write_text(yaml.safe_dump(_canonical_trace_registry(registry), sort_keys=True), encoding="utf-8")
    binding_path = tmp_path / "binding.json"
    binding_path.write_text(json.dumps(_trace_binding(), sort_keys=True), encoding="utf-8")
    before = {path: (path.stat().st_mtime_ns, path.read_bytes()) for path in tmp_path.iterdir()}

    run = subprocess.run(
        [
            sys.executable,
            str(SYNC_PATH),
            "find",
            "--id",
            "mcp-tool:omo:status",
            "--binding-json",
            str(binding_path),
            "--registry",
            str(registry_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    query = subprocess.run(
        [
            sys.executable,
            str(SYNC_PATH),
            "find",
            "--query",
            "status",
            "--binding-json",
            str(binding_path),
            "--registry",
            str(registry_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert run.returncode == 0
    assert json.loads(run.stdout)["trace_id"].startswith("sha256:")
    assert query.returncode == 4
    assert json.loads(query.stdout)["failure_code"] == "binding_requires_exact_id"
    after = {path: (path.stat().st_mtime_ns, path.read_bytes()) for path in tmp_path.iterdir()}
    assert after == before


def test_find_without_binding_preserves_legacy_receipt_contract(registry: dict, tmp_path: Path) -> None:
    registry_path = tmp_path / "capability-registry.yaml"
    registry_path.write_text(yaml.safe_dump(_canonical_trace_registry(registry), sort_keys=True), encoding="utf-8")

    run = subprocess.run(
        [sys.executable, str(SYNC_PATH), "find", "--id", "mcp-tool:omo:status", "--registry", str(registry_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    receipt = json.loads(run.stdout)

    assert run.returncode == 0
    assert receipt["status"] == "resolved"
    assert receipt["capability_id"] == "mcp-tool:omo:status"
    assert receipt["adapter"] == {"kind": "mcp_native", "target": "omo/status"}
    assert "binding" not in receipt
    assert "trace_id" not in receipt
    assert "receipt_digest" not in receipt


def test_inspect_cli_is_static_read_only_and_does_not_delegate_or_load_provider(
    cap_sync, registry: dict, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    skill = tmp_path / ".agents/skills/demo/SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("---\nname: demo\ndescription: static proof\n---\nprivate instructions\n", encoding="utf-8")
    registry_path = tmp_path / "projection-not-applicable.yaml"
    binding_path = tmp_path / "binding.json"
    binding_path.write_text(json.dumps(_trace_binding(), sort_keys=True), encoding="utf-8")
    before = {path: (path.stat().st_mtime_ns, path.read_bytes()) for path in (skill, binding_path)}

    monkeypatch.setattr(cap_sync, "ROOT", tmp_path)

    def forbidden_process(*_args, **_kwargs):
        raise AssertionError("inspect must not start a process")

    monkeypatch.setattr(cap_sync.subprocess, "run", forbidden_process)
    assert (
        cap_sync.main(
            [
                "inspect",
                "--id",
                "skill:demo",
                "--binding-json",
                str(binding_path),
                "--registry",
                str(registry_path),
            ]
        )
        == 0
    )
    receipt = json.loads(capsys.readouterr().out)

    assert receipt["status"] == "inspected"
    assert receipt["read_only"] is True
    assert receipt["executed"] is False
    assert receipt["provider_called"] is False
    assert receipt["invoked"] is False
    assert receipt["value_indicator_policy"] is False
    assert "private instructions" not in json.dumps(receipt, sort_keys=True)
    assert receipt["upstream_resolution"]["status"] == "not_applicable"
    after = {path: (path.stat().st_mtime_ns, path.read_bytes()) for path in (skill, binding_path)}
    assert after == before


def test_inspect_cli_returns_stable_upstream_failure_code(
    cap_sync, registry: dict, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    registry_path = tmp_path / "capability-registry.yaml"
    registry_path.write_text(yaml.safe_dump(_canonical_trace_registry(registry), sort_keys=True), encoding="utf-8")
    binding_path = tmp_path / "binding.json"
    binding_path.write_text(json.dumps(_trace_binding(), sort_keys=True), encoding="utf-8")
    monkeypatch.setattr(cap_sync, "ROOT", tmp_path)

    assert (
        cap_sync.main(
            [
                "inspect",
                "--id",
                "mcp-tool:omo:status",
                "--binding-json",
                str(binding_path),
                "--registry",
                str(registry_path),
            ]
        )
        == 4
    )
    receipt = json.loads(capsys.readouterr().out)
    assert receipt["failure_code"] == "upstream_resolution_required"
    assert receipt["executed"] is False


def test_inspect_cli_replays_resolution_and_statically_proves_mcp_source(
    cap_sync, registry: dict, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    source = tmp_path / "projects/omo/src/omo/mcp_server.py"
    source.parent.mkdir(parents=True)
    source.write_text(
        "from fastmcp import FastMCP\n"
        "mcp = FastMCP('omo')\n"
        "@mcp.tool()\n"
        "async def status() -> str:\n"
        "    return 'ok'\n"
        "@mcp.tool()\n"
        "async def shared() -> str:\n"
        "    return 'ok'\n",
        encoding="utf-8",
    )
    proved = _canonical_trace_registry(registry)
    registry_path = tmp_path / "capability-registry.yaml"
    registry_content = yaml.safe_dump(proved, sort_keys=True).encode("utf-8")
    registry_path.write_bytes(registry_content)
    selector = {"capability_id": "mcp-tool:omo:status"}
    resolution = cap_sync.build_resolution_receipt(
        cap_sync.resolve_capability(proved, **selector),
        registry_content,
        selector,
        binding=_trace_binding(),
        projection_metadata=proved,
    )
    resolution_path = tmp_path / "resolution.json"
    resolution_path.write_text(json.dumps(resolution, sort_keys=True), encoding="utf-8")
    monkeypatch.setattr(cap_sync, "ROOT", tmp_path)

    assert (
        cap_sync.main(
            [
                "inspect",
                "--id",
                "mcp-tool:omo:status",
                "--resolution-receipt-json",
                str(resolution_path),
                "--registry",
                str(registry_path),
            ]
        )
        == 0
    )
    receipt = json.loads(capsys.readouterr().out)
    assert receipt["status"] == "inspected"
    assert receipt["proof"] == {"method": "python_ast_static_declaration", "strength": "strong"}
    assert receipt["upstream_resolution"]["receipt_digest"] == resolution["receipt_digest"]
    assert receipt["provider_called"] is False


def test_bound_find_fails_closed_for_unproved_or_ambiguous_sources(
    cap_sync, registry: dict, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    binding_path = tmp_path / "binding.json"
    binding_path.write_text(json.dumps(_trace_binding(), sort_keys=True), encoding="utf-8")

    assert (
        cap_sync.main(
            [
                "find",
                "--id",
                "mcp-tool:omo:status",
                "--binding-json",
                str(binding_path),
                "--registry",
                str(tmp_path / "missing-registry.yaml"),
            ]
        )
        == 4
    )
    assert json.loads(capsys.readouterr().out)["failure_code"] == "source_unprovable"

    registry_path = tmp_path / "legacy-registry.yaml"
    registry_path.write_text(yaml.safe_dump(registry, sort_keys=True), encoding="utf-8")
    assert (
        cap_sync.main(
            [
                "find",
                "--id",
                "mcp-tool:omo:status",
                "--binding-json",
                str(binding_path),
                "--registry",
                str(registry_path),
            ]
        )
        == 4
    )
    assert json.loads(capsys.readouterr().out)["failure_code"] == "source_unprovable"

    proved = _canonical_trace_registry(registry)
    registry_path.write_text(yaml.safe_dump(proved, sort_keys=True), encoding="utf-8")
    assert (
        cap_sync.main(
            [
                "find",
                "--id",
                "mcp-tool:omo:missing",
                "--binding-json",
                str(binding_path),
                "--registry",
                str(registry_path),
            ]
        )
        == 4
    )
    assert json.loads(capsys.readouterr().out)["failure_code"] == "resolution_not_found"

    duplicate = _canonical_trace_registry(registry)
    duplicate["mcp_servers"].append(dict(duplicate["mcp_servers"][0]))
    registry_path.write_text(yaml.safe_dump(duplicate, sort_keys=True), encoding="utf-8")
    assert (
        cap_sync.main(
            [
                "find",
                "--id",
                "mcp-tool:omo:status",
                "--binding-json",
                str(binding_path),
                "--registry",
                str(registry_path),
            ]
        )
        == 4
    )
    assert json.loads(capsys.readouterr().out)["failure_code"] == "resolution_ambiguous"


class _FakeGateway:
    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def load(self, record: dict, *, selector: dict, binding: dict | None = None) -> dict:
        self.calls.append(("load", record, selector, binding))
        return {
            "schema": "capability-invocation-receipt/v1",
            "operation": "load",
            "status": "ready",
            "capability_id": record["id"],
            "invocation_attempted": False,
        }

    def invoke(self, record: dict, payload: object, *, selector: dict, binding: dict | None = None) -> dict:
        self.calls.append(("invoke", record, payload, selector, binding))
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


def test_execute_gateway_operation_forwards_binding_to_gateway(
    cap_sync, registry: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Task 6: a validated binding supplied to the gateway operation must be
    forwarded to Agora so the receipt can carry a binding_digest."""
    gateway = _FakeGateway()
    binding = _trace_binding()

    monkeypatch.setattr(
        cap_sync.subprocess, "run", lambda *a, **k: (_ for _ in ()).throw(AssertionError("subprocess forbidden"))
    )

    invoke_receipt = cap_sync.execute_gateway_operation(
        registry,
        "invoke",
        "bos-service:bos://governance/shared",
        payload={"scope": "bounded"},
        gateway=gateway,
        service_catalog=[_native_service()],
        binding=binding,
    )
    load_receipt = cap_sync.execute_gateway_operation(
        registry,
        "load",
        "bos-service:bos://governance/shared",
        gateway=gateway,
        service_catalog=[_native_service()],
        binding=binding,
    )

    assert invoke_receipt["status"] == "succeeded"
    assert load_receipt["status"] == "ready"
    assert gateway.calls[0][0] == "invoke"
    assert gateway.calls[0][4] == binding  # invoke received the binding
    assert gateway.calls[1][0] == "load"
    assert gateway.calls[1][3] == binding  # load received the binding


def test_execute_gateway_operation_without_binding_passes_none(
    cap_sync, registry: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Absent binding must still reach the gateway as None (backward compatible)."""
    gateway = _FakeGateway()
    monkeypatch.setattr(
        cap_sync.subprocess, "run", lambda *a, **k: (_ for _ in ()).throw(AssertionError("subprocess forbidden"))
    )

    cap_sync.execute_gateway_operation(
        registry,
        "invoke",
        "bos-service:bos://governance/shared",
        payload={},
        gateway=gateway,
        service_catalog=[_native_service()],
    )
    assert gateway.calls[0][4] is None


def test_invoke_cli_reads_binding_json_and_forwards_it(cap_sync, bound_files, monkeypatch) -> None:
    """The CLI invoke path must read --binding-json and pass it to the gateway
    operation so Agora can emit a binding_digest."""
    captured: list[dict] = []

    def fake_execute(reg, operation, capability_id, *, payload=None, gateway=None, service_catalog=None, binding=None):
        captured.append({"operation": operation, "binding": binding})
        return {"schema": "capability-invocation-receipt/v1", "status": "succeeded"}

    monkeypatch.setattr(cap_sync, "execute_gateway_operation", fake_execute)
    rc = cap_sync.main(bound_files.invoke_argv)

    assert rc == 0
    assert len(captured) == 1
    assert captured[0]["operation"] == "invoke"
    assert captured[0]["binding"] == bound_files.binding


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


def test_local_skill_and_workflow_loads_do_not_call_a_provider(
    cap_sync, monkeypatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def forbidden(*args, **kwargs):
        raise AssertionError("local capability load must not reach a provider")

    monkeypatch.setattr(cap_sync, "execute_gateway_operation", forbidden)
    assert cap_sync.main(["load", "--id", "skill:git-discipline"]) == 0
    skill_receipt = json.loads(capsys.readouterr().out)
    assert skill_receipt["status"] == "ready"
    assert skill_receipt["provider_called"] is False
    assert skill_receipt["invoked"] is False

    assert cap_sync.main(["load", "--id", "workflow:bet-execution"]) == 0
    workflow_receipt = json.loads(capsys.readouterr().out)
    assert workflow_receipt["status"] == "ready"
    assert workflow_receipt["provider_called"] is False
    assert workflow_receipt["invoked"] is False


def test_skill_invoke_is_rejected_before_any_provider(
    cap_sync, monkeypatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    payload = tmp_path / "input.json"
    payload.write_text("{}\n", encoding="utf-8")
    calls = 0

    def forbidden(*args, **kwargs):
        nonlocal calls
        calls += 1
        raise AssertionError("skill invocation must not reach a provider")

    monkeypatch.setattr(cap_sync, "execute_gateway_operation", forbidden)
    assert cap_sync.main(["invoke", "--id", "skill:git-discipline", "--input-json", str(payload)]) == 4
    receipt = json.loads(capsys.readouterr().out)
    assert calls == 0
    assert receipt["failure_code"] == "skill_invoke_forbidden"
    assert receipt["invocation"]["allowed"] is False


@pytest.mark.parametrize(
    ("actor_id", "expected_rc", "allowed"),
    [("workflow-controller", 0, True), ("other-actor", 4, False)],
)
def test_workflow_invoke_requires_workflow_controller_actor(
    cap_sync,
    monkeypatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    actor_id: str,
    expected_rc: int,
    allowed: bool,
) -> None:
    payload = tmp_path / "input.json"
    payload.write_text("{}\n", encoding="utf-8")
    binding = _trace_binding()
    binding["actor_id"] = actor_id
    binding_path = tmp_path / "binding.json"
    binding_path.write_text(json.dumps(binding), encoding="utf-8")

    monkeypatch.setattr(
        cap_sync,
        "execute_gateway_operation",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("workflow must stay local")),
    )
    rc = cap_sync.main(
        [
            "invoke",
            "--id",
            "workflow:bet-execution",
            "--input-json",
            str(payload),
            "--binding-json",
            str(binding_path),
        ]
    )
    receipt = json.loads(capsys.readouterr().out)
    assert rc == expected_rc
    assert receipt["provider_called"] is False
    assert receipt["invocation"]["allowed"] is allowed


@pytest.fixture
def bound_files(registry, tmp_path):
    from capability_native_receipt import build_native_inspection_receipt

    def digest(value: str) -> str:
        return "sha256:" + value * 64

    binding = {
        "correlation_id": "corr-test",
        "workflow_run_id": "run-test",
        "packet_id": "WP-TEST",
        "packet_hash": digest("a"),
        "assignment_id": "assignment-test",
        "dispatch_id": "dispatch-test",
        "actor_id": "actor-test",
        "delivery_attempt_id": "attempt-test",
    }
    capability_id = "bos-service:bos://governance/omo/state"
    projected = copy.deepcopy(registry)
    projected["bos_services"]["domains"]["governance"][0]["uri"] = "bos://governance/omo/state"
    registry_path = tmp_path / "registry.yaml"
    registry_path.write_text(yaml.safe_dump(projected, sort_keys=False), encoding="utf-8")
    binding_path = tmp_path / "binding.json"
    binding_path.write_text(json.dumps(binding), encoding="utf-8")
    inspection = build_native_inspection_receipt(
        capability_id=capability_id,
        binding=binding,
        proof={
            "source_ref": "projects/agora/etc/bos-services.yaml",
            "content": b"services: []\n",
            "source_schema": "agora-bos-services-yaml/v1",
            "proof": {"method": "canonical_bos_exact_uri", "strength": "strong"},
            "native_version": "1.0.0",
            "native_version_status": "proved",
        },
        upstream={
            "status": "verified",
            "schema": "capability-resolution-receipt/v1",
            "receipt_digest": digest("1"),
            "registry_digest": digest("2"),
        },
    )
    inspection_path = tmp_path / "inspection.json"
    inspection_path.write_text(json.dumps(inspection), encoding="utf-8")
    admission = {
        "receipt_digest": digest("3"),
        "admission_id": "admission-test",
        "step_run_id": "step-test",
        "worker": {"status": "bound", "id": "worker-test"},
    }
    admission_path = tmp_path / "admission.json"
    admission_path.write_text(json.dumps(admission), encoding="utf-8")
    input_path = tmp_path / "input.json"
    input_path.write_text("{}\n", encoding="utf-8")
    return SimpleNamespace(
        binding=binding,
        invoke_argv=[
            "invoke",
            "--id",
            capability_id,
            "--input-json",
            str(input_path),
            "--registry",
            str(registry_path),
            "--binding-json",
            str(binding_path),
            "--inspection-receipt-json",
            str(inspection_path),
            "--admission-receipt-json",
            str(admission_path),
            "--operation-id",
            "omo.state",
            "--effect-classification",
            "read_only",
        ],
    )


def test_bound_invoke_emits_native_execution_receipt(cap_sync, bound_files, monkeypatch, capsys):
    monkeypatch.setattr(
        cap_sync,
        "execute_gateway_operation",
        lambda *args, **kwargs: {"schema": "capability-invocation-receipt/v1", "status": "succeeded"},
    )
    rc = cap_sync.main(bound_files.invoke_argv)
    receipt = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert receipt["schema"] == "native-execution-receipt/v1"
    assert receipt["material"]["binding"] == bound_files.binding
    assert receipt["value_indicator_policy"] is False


# ---------------------------------------------------------------------------
# Task 6B root verifier: persisted admission is the only authority.
# ---------------------------------------------------------------------------


def _verification_request() -> dict:
    return {"payload": {"scope": "bounded", "operation": "audit"}}


def _verification_context(*, effect: str = "read_only", state: str = "admitted") -> tuple[dict, dict, list[dict]]:
    run_id = "run-task6b"
    packet_id = "WP-TASK6B-0123456789abcdef"
    packet_hash = "sha256:" + "a" * 64
    step_run_id = "step-task6b"
    admission_id = "admission-task6b"
    request = _verification_request()
    request_digest = "sha256:" + hashlib.sha256(
        json.dumps(request, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    request_identity = {
        "packet_id": packet_id,
        "packet_hash": packet_hash,
        "capability_id": "bos-service:bos://governance/shared",
        "operation_id": "audit",
        "effect_classification": effect,
        "request_digest": request_digest,
    }
    grant = {
        "admission_id": admission_id,
        "status": "admitted",
        "workflow_run_id": run_id,
        "trace_id": "trace-task6b",
        "backend": "task6b-test",
        "step_run_ids": [step_run_id],
        "capabilities": ["bos-service:bos://governance/shared"],
        "policy_digest": "sha256:" + "b" * 64,
        "issued_at": "2026-08-26T00:00:00+00:00",
        "expires_at": "2099-01-01T00:00:00+00:00",
        "request_identity": request_identity,
    }
    grant["proof"] = hashlib.sha256(
        json.dumps(grant, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    binding = {
        "correlation_id": "corr-task6b",
        "workflow_run_id": run_id,
        "packet_id": packet_id,
        "packet_hash": packet_hash,
        "assignment_id": "assignment-task6b",
        "dispatch_id": "dispatch-task6b",
        "actor_id": "worker-task6b",
        "delivery_attempt_id": "attempt-task6b",
    }
    material = {
        "schema": "native-execution-material/v1",
        "binding": binding,
        "capability": {"kind": "bos_service", "id": request_identity["capability_id"]},
        "inspection": {
            "receipt_digest": "sha256:" + "c" * 64,
            "source_digest": "sha256:" + "d" * 64,
        },
        "operation_id": "audit",
        "request_digest": request_digest,
        "admission": {
            "receipt_digest": "sha256:" + grant["proof"],
            "admission_id": admission_id,
            "step_run_id": step_run_id,
            "worker": {"status": "bound", "id": "worker-task6b"},
        },
        "authorization_source": "bos-pep",
        "effect_classification": effect,
        "execution_attempt": 1,
    }
    events = [
        {
            "event_id": "event-requested-task6b",
            "event_type": "WorkflowRequested",
            "trace_id": "trace-task6b",
            "workflow_run_id": run_id,
            "occurred_at": "2026-08-26T00:00:00+00:00",
            "producer": "test",
            "schema_version": "workflow-mesh/v1",
            "idempotency_key": "task6b-requested",
            "payload": {"request_identity": request_identity},
        },
        {
            "event_id": "event-admitted-task6b",
            "event_type": "WorkflowAdmitted",
            "trace_id": "trace-task6b",
            "workflow_run_id": run_id,
            "occurred_at": "2026-08-26T00:00:01+00:00",
            "producer": "test",
            "schema_version": "workflow-mesh/v1",
            "idempotency_key": "task6b-admitted",
            "payload": {"admission": grant, **grant},
        },
    ]
    if state in {"dispatched", "running"}:
        events.append(
            {
                "event_id": "event-dispatched-task6b",
                "event_type": "StepDispatched",
                "trace_id": "trace-task6b",
                "workflow_run_id": run_id,
                "occurred_at": "2026-08-26T00:00:02+00:00",
                "producer": "test",
                "schema_version": "workflow-mesh/v1",
                "idempotency_key": "task6b-dispatched",
                "payload": {
                    "step_run_id": step_run_id,
                    "admission_id": admission_id,
                    "dispatch_id": binding["dispatch_id"],
                    "worker_id": binding["actor_id"],
                    "packet_id": packet_id,
                    "packet_hash": packet_hash,
                    "instruction_binding": None,
                },
            }
        )
    if state == "running":
        events.append(
            {
                "event_id": "event-started-task6b",
                "event_type": "StepStarted",
                "trace_id": "trace-task6b",
                "workflow_run_id": run_id,
                "occurred_at": "2026-08-26T00:00:03+00:00",
                "producer": "test",
                "schema_version": "workflow-mesh/v1",
                "idempotency_key": "task6b-started",
                "payload": {"step_run_id": step_run_id, "admission_id": admission_id},
            }
        )
    return material, request, events


def _verification_envelope(material: dict, request: dict) -> dict:
    return {
        "schema": "capability-admission-verification-request/v1",
        "material": material,
        "request": request,
        "expected": {
            "capability_id": material["capability"]["id"],
            "operation_id": material["operation_id"],
            "effect_classification": material["effect_classification"],
        },
    }


def _write_mesh(omo_dir: Path, events: list[dict]) -> None:
    path = omo_dir / "_knowledge" / "workflow-mesh" / "events.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(event, sort_keys=True) + "\n" for event in events), encoding="utf-8")


def test_verify_material_rejects_cross_run_before_any_outbound_call(
    cap_sync, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    material, request, events = _verification_context()
    _write_mesh(tmp_path / ".omo", events)
    material["binding"]["workflow_run_id"] = "other-run"
    counters = {"provider": 0, "router": 0, "gateway": 0, "subprocess": 0}
    for name in ("_load_native_gateway", "execute_gateway_operation"):
        monkeypatch.setattr(cap_sync, name, lambda *args, **kwargs: counters.__setitem__("gateway", 1))
    monkeypatch.setattr(cap_sync.subprocess, "run", lambda *args, **kwargs: counters.__setitem__("subprocess", 1))

    receipt = cap_sync.verify_material_against_mesh(tmp_path / ".omo", _verification_envelope(material, request))

    assert receipt["status"] == "rejected"
    assert receipt["failure_code"] == "admission_contradiction"
    assert counters == {"provider": 0, "router": 0, "gateway": 0, "subprocess": 0}


def test_verify_material_accepts_persisted_read_only_admission_without_writes(cap_sync, tmp_path: Path) -> None:
    material, request, events = _verification_context(effect="read_only", state="admitted")
    omo_dir = tmp_path / ".omo"
    _write_mesh(omo_dir, events)
    log = omo_dir / "_knowledge" / "workflow-mesh" / "events.jsonl"
    before = (log.stat().st_mtime_ns, log.read_bytes())

    receipt = cap_sync.verify_material_against_mesh(omo_dir, _verification_envelope(material, request))

    assert receipt["schema"] == "capability-admission-verification-receipt/v1"
    assert receipt["status"] == "verified"
    assert receipt["capability_id"] == material["capability"]["id"]
    assert receipt["operation_id"] == "audit"
    assert receipt["effect_classification"] == "read_only"
    assert receipt["authority"] == "omo-workflow-mesh"
    assert receipt["value_indicator_policy"] is False
    assert (log.stat().st_mtime_ns, log.read_bytes()) == before


def test_verify_material_requires_dispatch_for_effectful_and_matches_worker(cap_sync, tmp_path: Path) -> None:
    material, request, events = _verification_context(effect="effectful", state="dispatched")
    omo_dir = tmp_path / ".omo"
    _write_mesh(omo_dir, events)

    assert cap_sync.verify_material_against_mesh(
        omo_dir, _verification_envelope(material, request)
    )["status"] == "verified"

    material["admission"]["worker"]["id"] = "other-worker"
    rejected = cap_sync.verify_material_against_mesh(omo_dir, _verification_envelope(material, request))
    assert rejected["status"] == "rejected"
    assert rejected["failure_code"] == "admission_receipt_invalid"


def test_verify_material_cli_reads_one_bounded_stdin_envelope_and_uses_fixed_omo_root(
    cap_sync, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(cap_sync.sys, "stdin", SimpleNamespace(buffer=SimpleNamespace(read=lambda _size: b"{}")))
    assert cap_sync.main(["verify-material"]) == 4
    receipt = json.loads(capsys.readouterr().out)
    assert receipt["status"] == "rejected"
    assert receipt["failure_code"] in {"native_route_unprovable", "admission_receipt_invalid"}
    assert "omo_dir" not in json.dumps(receipt, sort_keys=True)


def test_unbound_invoke_is_shadow_observed_before_fail_promotion(cap_sync, monkeypatch, registry, tmp_path, capsys):
    registry_file = tmp_path / "registry.yaml"
    registry_file.write_text(yaml.safe_dump(registry, sort_keys=False), encoding="utf-8")
    input_file = tmp_path / "input.json"
    input_file.write_text("{}\n", encoding="utf-8")
    calls = 0

    def legacy_gateway(*args, **kwargs):
        nonlocal calls
        calls += 1
        return {"schema": "capability-invocation-receipt/v1", "status": "succeeded"}

    monkeypatch.setattr(cap_sync, "execute_gateway_operation", legacy_gateway)
    rc = cap_sync.main(
        [
            "invoke",
            "--id",
            "bos-service:bos://governance/shared",
            "--input-json",
            str(input_file),
            "--registry",
            str(registry_file),
        ]
    )
    receipt = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert calls == 1
    assert receipt["binding_enforcement"] == f"{cap_sync.BINDING_ENFORCEMENT}_missing"


# ---------------------------------------------------------------------------
# T1-12 Task4C: local skill/workflow load/invoke must exact-resolve the
# registry before returning a local receipt; prefix branching alone is a
# fail-closed hole.

_LOCAL_RECEIPT_FLAGS = {
    "read_only": True,
    "executed": False,
    "provider_called": False,
    "invoked": False,
    "value_indicator_policy": False,
}


def _assert_local_receipt_flags(receipt: dict) -> None:
    for key, expected in _LOCAL_RECEIPT_FLAGS.items():
        assert key in receipt, f"local receipt must state {key} explicitly"
        assert receipt[key] is expected, f"{key} must be exactly {expected}"


def _local_projection(registry: dict) -> dict:
    result = _canonical_trace_registry(registry)
    result["skills"] = [
        {"id": "git-discipline", "exists": True},
        {"id": "unavailable-skill", "exists": False},
    ]
    result["workflows"] = [{"id": "bet-execution", "exists": True}]
    return result


def _forbid_provider(cap_sync, monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*args, **kwargs):
        raise AssertionError("local capability operations must never reach a provider")

    monkeypatch.setattr(cap_sync, "execute_gateway_operation", forbidden)
    monkeypatch.setattr(cap_sync, "_load_native_gateway", forbidden)


def test_partial_binding_bundle_fails_closed_without_gateway_call(
    cap_sync, monkeypatch, registry, tmp_path, capsys
) -> None:
    registry_path = tmp_path / "registry.yaml"
    registry_path.write_text(yaml.safe_dump(registry, sort_keys=False), encoding="utf-8")
    input_path = tmp_path / "input.json"
    input_path.write_text("{}\n", encoding="utf-8")
    binding_path = tmp_path / "binding.json"
    binding_path.write_text(json.dumps(_trace_binding()), encoding="utf-8")
    calls = 0

    def forbidden(*args, **kwargs):
        nonlocal calls
        calls += 1
        raise AssertionError("gateway must not run for a partial bundle")

    monkeypatch.setattr(cap_sync, "execute_gateway_operation", forbidden)
    rc = cap_sync.main(
        [
            "invoke",
            "--id",
            "bos-service:bos://governance/shared",
            "--input-json",
            str(input_path),
            "--registry",
            str(registry_path),
            "--binding-json",
            str(binding_path),
        ]
    )
    receipt = json.loads(capsys.readouterr().out)

    assert rc == 4
    assert calls == 0
    assert receipt["failure_code"] == "binding_bundle_incomplete"
    assert receipt["invocation"]["allowed"] is False


@pytest.mark.parametrize("capability_id", ["skill:does-not-exist", "workflow:does-not-exist"])
def test_local_load_rejects_nonexistent_ids_before_provider(
    cap_sync, monkeypatch, registry, tmp_path: Path, capsys: pytest.CaptureFixture[str], capability_id: str
) -> None:
    registry_path = tmp_path / "capability-registry.yaml"
    registry_path.write_text(yaml.safe_dump(_local_projection(registry), sort_keys=True), encoding="utf-8")
    _forbid_provider(cap_sync, monkeypatch)

    rc = cap_sync.main(["load", "--id", capability_id, "--registry", str(registry_path)])
    receipt = json.loads(capsys.readouterr().out)

    assert rc == 2
    assert receipt["status"] == "rejected"
    assert receipt["failure_code"] == "resolution_not_found"
    encoded = json.dumps(receipt, sort_keys=True)
    assert "does-not-exist" not in encoded
    assert str(tmp_path) not in encoded
    assert receipt["invocation"]["allowed"] is False
    _assert_local_receipt_flags(receipt)


def test_local_load_rejects_old_projection_without_local_capabilities(
    cap_sync, monkeypatch, registry, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    registry_path = tmp_path / "old-projection.yaml"
    registry_path.write_text(yaml.safe_dump(registry, sort_keys=True), encoding="utf-8")
    _forbid_provider(cap_sync, monkeypatch)

    rc = cap_sync.main(["load", "--id", "skill:git-discipline", "--registry", str(registry_path)])
    receipt = json.loads(capsys.readouterr().out)

    assert rc == 2
    assert receipt["status"] == "rejected"
    assert receipt["failure_code"] == "resolution_not_found"
    _assert_local_receipt_flags(receipt)


def test_local_load_rejects_unavailable_local_capability(
    cap_sync, monkeypatch, registry, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    registry_path = tmp_path / "capability-registry.yaml"
    registry_path.write_text(yaml.safe_dump(_local_projection(registry), sort_keys=True), encoding="utf-8")
    _forbid_provider(cap_sync, monkeypatch)

    rc = cap_sync.main(["load", "--id", "skill:unavailable-skill", "--registry", str(registry_path)])
    receipt = json.loads(capsys.readouterr().out)

    assert rc == 2
    assert receipt["failure_code"] == "resolution_not_found"
    _assert_local_receipt_flags(receipt)


@pytest.mark.parametrize("corruption", ["missing_file", "malformed_yaml"])
def test_local_load_invalid_registry_rejects_without_provider(
    cap_sync, monkeypatch, registry, tmp_path: Path, capsys: pytest.CaptureFixture[str], corruption: str
) -> None:
    registry_path = tmp_path / "capability-registry.yaml"
    if corruption == "malformed_yaml":
        registry_path.write_text("version: [broken\n  - !!float 'x'", encoding="utf-8")
    _forbid_provider(cap_sync, monkeypatch)

    rc = cap_sync.main(["load", "--id", "skill:git-discipline", "--registry", str(registry_path)])
    receipt = json.loads(capsys.readouterr().out)

    assert rc == 4
    assert receipt["status"] == "rejected"
    assert receipt["failure_code"] == "invalid_registry"
    encoded = json.dumps(receipt, sort_keys=True)
    assert "git-discipline" not in encoded
    _assert_local_receipt_flags(receipt)


def test_local_load_rejects_duplicate_local_capability_ids(
    cap_sync, monkeypatch, registry, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    duplicate = _local_projection(registry)
    duplicate["skills"].append(dict(duplicate["skills"][0]))
    registry_path = tmp_path / "capability-registry.yaml"
    registry_path.write_text(yaml.safe_dump(duplicate, sort_keys=True), encoding="utf-8")
    _forbid_provider(cap_sync, monkeypatch)

    rc = cap_sync.main(["load", "--id", "skill:git-discipline", "--registry", str(registry_path)])
    receipt = json.loads(capsys.readouterr().out)

    assert rc == 3
    assert receipt["failure_code"] == "resolution_ambiguous"
    assert receipt["invocation"]["allowed"] is False
    _assert_local_receipt_flags(receipt)


@pytest.mark.parametrize("capability_id", ["skill:git-discipline", "workflow:bet-execution"])
def test_local_load_exact_canonical_ids_succeed(
    cap_sync, monkeypatch, registry, tmp_path: Path, capsys: pytest.CaptureFixture[str], capability_id: str
) -> None:
    registry_path = tmp_path / "capability-registry.yaml"
    registry_path.write_text(yaml.safe_dump(_local_projection(registry), sort_keys=True), encoding="utf-8")
    _forbid_provider(cap_sync, monkeypatch)

    rc = cap_sync.main(["load", "--id", capability_id, "--registry", str(registry_path)])
    receipt = json.loads(capsys.readouterr().out)

    assert rc == 0
    assert receipt["status"] == "ready"
    assert receipt["invocation"] == {"allowed": False, "route": "local_metadata_only", "reason": "load_only"}
    _assert_local_receipt_flags(receipt)


def test_local_skill_invoke_rejects_with_full_local_receipt(
    cap_sync, monkeypatch, registry, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    registry_path = tmp_path / "capability-registry.yaml"
    registry_path.write_text(yaml.safe_dump(_local_projection(registry), sort_keys=True), encoding="utf-8")
    payload = tmp_path / "input.json"
    payload.write_text("{}\n", encoding="utf-8")
    _forbid_provider(cap_sync, monkeypatch)

    rc = cap_sync.main(
        ["invoke", "--id", "skill:git-discipline", "--input-json", str(payload), "--registry", str(registry_path)]
    )
    receipt = json.loads(capsys.readouterr().out)

    assert rc == 4
    assert receipt["failure_code"] == "skill_invoke_forbidden"
    assert receipt["invocation"] == {"allowed": False, "route": "none", "reason": "skill_load_only"}
    _assert_local_receipt_flags(receipt)


@pytest.mark.parametrize(
    ("actor_id", "expected_rc", "allowed"),
    [
        ("workflow-controller", 0, True),
        ("other-actor", 4, False),
    ],
)
def test_local_workflow_invoke_requires_controller_with_full_local_receipt(
    cap_sync,
    monkeypatch,
    registry,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    actor_id: str,
    expected_rc: int,
    allowed: bool,
) -> None:
    registry_path = tmp_path / "capability-registry.yaml"
    registry_path.write_text(yaml.safe_dump(_local_projection(registry), sort_keys=True), encoding="utf-8")
    payload = tmp_path / "input.json"
    payload.write_text("{}\n", encoding="utf-8")
    binding = _trace_binding()
    binding["actor_id"] = actor_id
    binding_path = tmp_path / "binding.json"
    binding_path.write_text(json.dumps(binding), encoding="utf-8")
    _forbid_provider(cap_sync, monkeypatch)

    rc = cap_sync.main(
        [
            "invoke",
            "--id",
            "workflow:bet-execution",
            "--input-json",
            str(payload),
            "--registry",
            str(registry_path),
            "--binding-json",
            str(binding_path),
        ]
    )
    receipt = json.loads(capsys.readouterr().out)

    assert rc == expected_rc
    assert receipt["invocation"]["allowed"] is allowed
    if not allowed:
        assert receipt["failure_code"] == "workflow_controller_required"
    _assert_local_receipt_flags(receipt)


def test_local_load_does_not_read_local_sources(
    cap_sync, monkeypatch, registry, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    skill = tmp_path / ".agents/skills/git-discipline/SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("---\nname: git-discipline\n---\nprivate instructions\n", encoding="utf-8")
    registry_path = tmp_path / "capability-registry.yaml"
    registry_path.write_text(yaml.safe_dump(_local_projection(registry), sort_keys=True), encoding="utf-8")
    before = (skill.stat().st_mtime_ns, skill.read_bytes())
    _forbid_provider(cap_sync, monkeypatch)
    monkeypatch.setattr(cap_sync, "ROOT", tmp_path)

    rc = cap_sync.main(["load", "--id", "skill:git-discipline", "--registry", str(registry_path)])
    receipt = json.loads(capsys.readouterr().out)

    assert rc == 0
    encoded = json.dumps(receipt, sort_keys=True)
    assert "private instructions" not in encoded
    assert "git-discipline" not in encoded
    assert (skill.stat().st_mtime_ns, skill.read_bytes()) == before
