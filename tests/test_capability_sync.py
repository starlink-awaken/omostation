"""Contract tests for the single capability registry spine."""

from __future__ import annotations

import ast
import builtins
import copy
import hashlib
import importlib.util
import io
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
HELPERS_PATH = ROOT / "lib" / "capability_sync_verification_helpers.py"
GENERATOR_PATH = ROOT / "bin" / "ssot" / "gen-capability-registry.py"


def test_capability_sync_stays_below_god_module_error_threshold() -> None:
    """The compatibility CLI must remain below the hard single-file limit."""
    assert len(SYNC_PATH.read_text(encoding="utf-8").splitlines()) <= 1500


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
def helpers(cap_sync):
    """The exact helper-module instance the CLI imported (same patch surface)."""
    import capability_sync_verification_helpers

    return sys.modules["capability_sync_verification_helpers"]


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

    def invoke(
        self,
        record: dict,
        payload: object,
        *,
        selector: dict,
        binding: dict | None = None,
        principal_authority: dict | None = None,
        **_kwargs,
    ) -> dict:
        self.calls.append(("invoke", record, payload, selector, binding, principal_authority))
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

    def fake_execute(
        reg,
        operation,
        capability_id,
        *,
        payload=None,
        gateway=None,
        service_catalog=None,
        binding=None,
        principal_authority=None,
    ):
        captured.append({"operation": operation, "binding": binding, "principal_authority": principal_authority})
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


def test_unbound_invoke_rejects_before_gateway_and_emits_safe_receipt(
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
        == 4
    )
    receipt = json.loads(capsys.readouterr().out)
    encoded = json.dumps(receipt, sort_keys=True)
    assert receipt["schema"] == "capability-resolution-receipt/v1"
    assert receipt["status"] == "rejected"
    assert receipt["failure_code"] == "binding_required"
    assert receipt["states"] == {"invoked": False, "evidenced": False, "independently_verified": False}
    assert gateway.calls == []
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

    assert cap_sync.main(["load", "--id", secret_id, "--registry", str(registry_path)]) == 4
    receipt = json.loads(capsys.readouterr().out)
    encoded = json.dumps(receipt, sort_keys=True)
    assert receipt["status"] == "rejected"
    assert receipt["failure_code"] == "binding_required"
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
    # WorkflowAdmitted preserves OMO's canonical WorkPacket identity.  The
    # execution envelope, not the admission identity, owns operation/effect
    # and request-digest binding.
    request_identity = {
        "bet_id": "BET-Y1Q3-T1-12",
        "packet_id": packet_id,
        "packet_hash": packet_hash,
        "task_ref": "tasks/task6b.yaml",
        "instruction_binding": {
            "instruction_ref": "instructions/task6b.md",
            "instruction_version": "v1",
            "content_digest": "sha256:" + "e" * 64,
            "instruction_profile": "executor",
        },
        "capability_requirements": [
            {
                "capability_id": "bos-service:bos://governance/shared",
                "operation": "invoke",
                "effect": effect,
            }
        ],
    }
    canonical_requirements = json.dumps(
        request_identity["capability_requirements"], sort_keys=True, separators=(",", ":")
    )
    request_identity["capability_requirements_digest"] = "sha256:" + hashlib.sha256(
        canonical_requirements.encode("utf-8")
    ).hexdigest()
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
        "capability": {"kind": "bos_service", "id": "bos-service:bos://governance/shared"},
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
    if state in {"dispatched", "running", "acknowledged", "active", "lease_expired", "reclaimed", "successor"}:
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
    if state in {"acknowledged", "active", "lease_expired", "reclaimed", "successor"}:
        events.append(
            {
                "event_id": "event-acknowledged-task6b",
                "event_type": "WorkerAcknowledged",
                "trace_id": "trace-task6b",
                "workflow_run_id": run_id,
                "occurred_at": "2026-08-26T00:00:03+00:00",
                "producer": "test",
                "schema_version": "workflow-mesh/v1",
                "idempotency_key": "task6b-acknowledged",
                "payload": {
                    "dispatch_id": binding["dispatch_id"],
                    "worker_id": binding["actor_id"],
                    "step_run_id": step_run_id,
                    "admission_id": admission_id,
                    "acknowledged_at": "2026-08-26T00:00:03+00:00",
                    "lease_expires_at": "2026-08-26T00:10:00+00:00",
                    "packet_id": packet_id,
                    "packet_hash": packet_hash,
                    "instruction_binding": None,
                    "ack_decision": "proceed",
                    "ack_origin_proof_digest": "sha256:" + "f" * 64,
                },
            }
        )
    if state in {"active", "lease_expired", "reclaimed", "successor"}:
        events.append(
            {
                "event_id": "event-renewed-task6b",
                "event_type": "WorkerLeaseRenewed",
                "trace_id": "trace-task6b",
                "workflow_run_id": run_id,
                "occurred_at": "2026-08-26T00:00:04+00:00",
                "producer": "test",
                "schema_version": "workflow-mesh/v1",
                "idempotency_key": "task6b-renewed",
                "payload": {
                    "dispatch_id": binding["dispatch_id"],
                    "worker_id": binding["actor_id"],
                    "step_run_id": step_run_id,
                    "admission_id": admission_id,
                    "heartbeat_id": "heartbeat-task6b",
                    "heartbeat_at": "2026-08-26T00:00:04+00:00",
                    "lease_expires_at": "2026-08-26T00:20:00+00:00",
                },
            }
        )
    if state in {"lease_expired", "reclaimed", "successor"}:
        events.append(
            {
                "event_id": "event-expired-task6b",
                "event_type": "WorkerLeaseExpired",
                "trace_id": "trace-task6b",
                "workflow_run_id": run_id,
                "occurred_at": "2026-08-26T00:20:01+00:00",
                "producer": "test",
                "schema_version": "workflow-mesh/v1",
                "idempotency_key": "task6b-expired",
                "payload": {
                    "dispatch_id": binding["dispatch_id"],
                    "worker_id": binding["actor_id"],
                    "step_run_id": step_run_id,
                    "admission_id": admission_id,
                    "expired_at": "2026-08-26T00:20:01+00:00",
                    "lease_expires_at": "2026-08-26T00:20:00+00:00",
                    "reason": "lease_expired",
                },
            }
        )
    if state in {"reclaimed", "successor"}:
        events.append(
            {
                "event_id": "event-reclaimed-task6b",
                "event_type": "WorkerReclaimed",
                "trace_id": "trace-task6b",
                "workflow_run_id": run_id,
                "occurred_at": "2026-08-26T00:20:02+00:00",
                "producer": "test",
                "schema_version": "workflow-mesh/v1",
                "idempotency_key": "task6b-reclaimed",
                "payload": {
                    "dispatch_id": binding["dispatch_id"],
                    "worker_id": binding["actor_id"],
                    "step_run_id": step_run_id,
                    "admission_id": admission_id,
                    "reclaimed_at": "2026-08-26T00:20:02+00:00",
                    "successor_worker_id": "worker-task6b-successor",
                    "successor_dispatch_id": "dispatch-task6b-successor",
                    "reason": "lease_expired",
                },
            }
        )
    if state == "successor":
        events.append(
            {
                "event_id": "event-successor-dispatched-task6b",
                "event_type": "StepDispatched",
                "trace_id": "trace-task6b",
                "workflow_run_id": run_id,
                "occurred_at": "2026-08-26T00:20:03+00:00",
                "producer": "test",
                "schema_version": "workflow-mesh/v1",
                "idempotency_key": "task6b-successor-dispatched",
                "payload": {
                    "step_run_id": step_run_id,
                    "admission_id": admission_id,
                    "dispatch_id": "dispatch-task6b-successor",
                    "worker_id": "worker-task6b-successor",
                    "packet_id": packet_id,
                    "packet_hash": packet_hash,
                    "instruction_binding": None,
                },
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


def _refresh_admission_proof(events: list[dict]) -> None:
    """Keep test mutations valid as an OMO WorkflowAdmitted receipt."""
    grant = events[1]["payload"]["admission"]
    unsigned = {key: value for key, value in grant.items() if key != "proof"}
    grant["proof"] = hashlib.sha256(
        json.dumps(unsigned, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    events[1]["payload"].update(grant)


def _refresh_capability_requirements_digest(request_identity: dict) -> None:
    canonical_requirements = json.dumps(
        request_identity["capability_requirements"], sort_keys=True, separators=(",", ":")
    )
    request_identity["capability_requirements_digest"] = "sha256:" + hashlib.sha256(
        canonical_requirements.encode("utf-8")
    ).hexdigest()


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


def test_verification_fixture_uses_omo_exact_request_identity_without_execution_extras() -> None:
    material, _request, events = _verification_context()
    identity = events[0]["payload"]["request_identity"]

    assert set(identity) == {
        "bet_id",
        "packet_id",
        "packet_hash",
        "task_ref",
        "instruction_binding",
        "capability_requirements",
        "capability_requirements_digest",
    }
    assert identity["capability_requirements"] == [
        {
            "capability_id": material["capability"]["id"],
            "operation": "invoke",
            "effect": "read_only",
        }
    ]
    canonical_requirements = json.dumps(
        identity["capability_requirements"], sort_keys=True, separators=(",", ":")
    )
    assert identity["capability_requirements_digest"] == "sha256:" + hashlib.sha256(
        canonical_requirements.encode("utf-8")
    ).hexdigest()
    assert not ({"operation", "effect", "request", "request_digest"} & set(identity))


@pytest.mark.parametrize("receipt_digest", ["original", "sha256:" + "0" * 64])
def test_verifier_rejects_old_or_new_material_after_real_omo_admission_renewal(
    cap_sync, tmp_path: Path, receipt_digest: str
) -> None:
    material, request, events = _verification_context(effect="effectful", state="dispatched")
    events.append(
        {
            "event_id": "event-admission-renewed-task6b",
            "event_type": "AdmissionRenewed",
            "trace_id": "trace-task6b",
            "workflow_run_id": material["binding"]["workflow_run_id"],
            "occurred_at": "2026-08-26T00:00:03+00:00",
            "producer": "omo-workflow-dispatch",
            "schema_version": "workflow-mesh/v1",
            "idempotency_key": "task6b-admission-renewed",
            "payload": {
                "admission_id": material["admission"]["admission_id"],
                "previous_expires_at": "2099-01-01T00:00:00+00:00",
                "expires_at": "2099-01-01T00:15:00+00:00",
                "renewed_at": "2026-08-26T00:00:03+00:00",
            },
        }
    )
    if receipt_digest != "original":
        material["admission"]["receipt_digest"] = receipt_digest
    _write_mesh(tmp_path / ".omo", events)

    receipt = cap_sync.verify_material_against_mesh(tmp_path / ".omo", _verification_envelope(material, request))

    assert receipt == {
        "schema": "capability-admission-verification-receipt/v1",
        "status": "rejected",
        "failure_code": "admission_contradiction",
        "value_indicator_policy": False,
    }


@pytest.mark.parametrize(
    "capabilities",
    [
        [{"capability_id": "bos-service:bos://governance/shared"}],
        [{"id": "bos-service:bos://governance/shared"}],
        ["mcp-tool:omo:status"],
        [],
        None,
        ["bos-service:bos://governance/shared", {"id": "bos-service:bos://governance/shared"}],
    ],
)
def test_verifier_rejects_noncanonical_admission_capabilities(
    cap_sync, tmp_path: Path, capabilities: object
) -> None:
    material, request, events = _verification_context()
    events[1]["payload"]["admission"]["capabilities"] = capabilities
    _refresh_admission_proof(events)
    _write_mesh(tmp_path / ".omo", events)

    receipt = cap_sync.verify_material_against_mesh(tmp_path / ".omo", _verification_envelope(material, request))

    assert receipt["failure_code"] == "admission_receipt_invalid"


def test_verifier_rejects_missing_admission_capabilities(cap_sync, tmp_path: Path) -> None:
    material, request, events = _verification_context()
    events[1]["payload"]["admission"].pop("capabilities")
    _refresh_admission_proof(events)
    _write_mesh(tmp_path / ".omo", events)

    receipt = cap_sync.verify_material_against_mesh(tmp_path / ".omo", _verification_envelope(material, request))

    assert receipt["failure_code"] == "admission_receipt_invalid"


def test_verifier_accepts_exact_mcp_tool_material_with_mcp_pep(cap_sync, tmp_path: Path) -> None:
    material, request, events = _verification_context()
    capability_id = "mcp-tool:omo:status"
    material["capability"] = {"kind": "mcp_tool", "id": capability_id}
    material["authorization_source"] = "mcp-pep"
    events[1]["payload"]["admission"]["capabilities"] = [capability_id]
    request_identity = events[0]["payload"]["request_identity"]
    request_identity["capability_requirements"][0]["capability_id"] = capability_id
    _refresh_capability_requirements_digest(request_identity)
    _refresh_admission_proof(events)
    material["admission"]["receipt_digest"] = "sha256:" + events[1]["payload"]["admission"]["proof"]
    _write_mesh(tmp_path / ".omo", events)

    receipt = cap_sync.verify_material_against_mesh(tmp_path / ".omo", _verification_envelope(material, request))

    assert receipt["status"] == "verified"
    assert receipt["capability_id"] == capability_id
    assert events[1]["payload"]["admission"]["request_identity"] == request_identity
    assert request_identity["capability_requirements"] == [
        {"capability_id": capability_id, "operation": "invoke", "effect": "read_only"}
    ]
    assert request_identity["capability_requirements_digest"] == "sha256:" + hashlib.sha256(
        json.dumps(
            request_identity["capability_requirements"], sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()


@pytest.mark.parametrize(
    "field",
    ["dispatch_id", "worker_id", "step_run_id", "admission_id", "packet_id", "packet_hash"],
)
def test_verifier_rejects_each_exact_persisted_worker_identity_mismatch(
    cap_sync, tmp_path: Path, field: str
) -> None:
    material, request, events = _verification_context(effect="effectful", state="dispatched")
    if field in {"dispatch_id", "packet_id", "packet_hash"}:
        material["binding"][field] = (
            "sha256:" + "f" * 64 if field == "packet_hash" else "other-" + field
        )
    elif field == "worker_id":
        material["admission"]["worker"]["id"] = "other-worker"
    else:
        material["admission"][field] = "other-" + field
    _write_mesh(tmp_path / ".omo", events)

    receipt = cap_sync.verify_material_against_mesh(tmp_path / ".omo", _verification_envelope(material, request))

    assert receipt["failure_code"] == "admission_receipt_invalid"


def test_root_mesh_projector_never_imports_omo_or_mutates_import_state(
    cap_sync,
    monkeypatch: pytest.MonkeyPatch,
    helpers,
) -> None:
    material, _request, events = _verification_context(effect="effectful", state="active")
    monkeypatch.delitem(sys.modules, "omo", raising=False)
    monkeypatch.delitem(sys.modules, "omo.workflow_mesh", raising=False)
    original_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name == "omo" or name.startswith("omo."):
            raise AssertionError("root verifier must not import OMO")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    before_path = list(sys.path)
    before_dont_write_bytecode = sys.dont_write_bytecode

    projector = helpers._load_workflow_mesh_projection()
    snapshot = projector(events, material["binding"]["workflow_run_id"])

    assert callable(projector)
    assert snapshot["state"] == "running"
    assert snapshot["step_runs"][material["admission"]["step_run_id"]]["state"] == "running"
    assert snapshot["worker"]["state"] == "active"
    assert sys.path == before_path
    assert sys.dont_write_bytecode is before_dont_write_bytecode
    assert "omo" not in sys.modules
    assert "omo.workflow_mesh" not in sys.modules


def test_root_mesh_projector_vocabulary_matches_authoritative_omo_source_ast(cap_sync) -> None:
    source_path = ROOT / "projects" / "omo" / "src" / "omo" / "workflow_mesh.py"
    tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
    assignments = {
        target.id: ast.literal_eval(node.value)
        for node in tree.body
        if isinstance(node, ast.Assign)
        for target in node.targets
        if isinstance(target, ast.Name) and target.id in {"EVENT_STATE", "_WORKER_EVENTS"}
    }
    authoritative_event_state = assignments["EVENT_STATE"]
    authoritative_subset = {
        "WorkflowRequested",
        "WorkflowAdmitted",
        "StepDispatched",
        "StepStarted",
        "AdmissionRenewed",
        *assignments["_WORKER_EVENTS"],
    }

    assert cap_sync.VERIFICATION_MESH_EVENT_STATES == {
        event_type: authoritative_event_state[event_type] for event_type in authoritative_subset
    }
    assert authoritative_subset == {
        "WorkflowRequested",
        "WorkflowAdmitted",
        "StepDispatched",
        "StepStarted",
        "WorkerAcknowledged",
        "WorkerLeaseRenewed",
        "WorkerLeaseExpired",
        "AdmissionRenewed",
        "WorkerReclaimed",
    }
    assert not {
        "WorkflowPrepared",
        "WorkerDispatched",
        "StepRunStarted",
        "WorkerActive",
    } & set(cap_sync.VERIFICATION_MESH_EVENT_STATES)


@pytest.mark.parametrize(
    ("worker_state", "ack_decision", "status", "failure_code"),
    [
        ("acknowledged", "proceed", "verified", None),
        ("active", "proceed", "verified", None),
        ("acknowledged", "stop", "rejected", "admission_contradiction"),
        ("active", "stop", "rejected", "admission_contradiction"),
    ],
)
def test_verifier_requires_proceed_acknowledgement_for_live_worker_context(
    cap_sync,
    tmp_path: Path,
    worker_state: str,
    ack_decision: str,
    status: str,
    failure_code: str | None,
    helpers,
) -> None:
    material, request, events = _verification_context(effect="effectful", state=worker_state)
    acknowledgement = next(event for event in events if event["event_type"] == "WorkerAcknowledged")
    acknowledgement["payload"]["ack_decision"] = ack_decision
    omo_dir = tmp_path / ".omo"
    _write_mesh(omo_dir, events)

    projector = helpers._load_workflow_mesh_projection()
    snapshot = projector(events, material["binding"]["workflow_run_id"])
    receipt = cap_sync.verify_material_against_mesh(omo_dir, _verification_envelope(material, request))

    assert snapshot["worker"]["ack_decision"] == ack_decision
    assert receipt["status"] == status
    if failure_code is not None:
        assert receipt["failure_code"] == failure_code


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


@pytest.mark.parametrize(
    ("worker_state", "status", "failure_code"),
    [
        ("dispatched", "verified", None),
        ("acknowledged", "verified", None),
        ("active", "verified", None),
        ("lease_expired", "rejected", "admission_contradiction"),
        ("reclaimed", "rejected", "admission_contradiction"),
        ("successor", "rejected", "admission_receipt_invalid"),
    ],
)
def test_verifier_requires_a_live_projected_worker_lease_and_rejects_replaced_dispatch(
    cap_sync, tmp_path: Path, worker_state: str, status: str, failure_code: str | None
) -> None:
    """Use the actual Mesh projection for every worker lifecycle state."""
    material, request, events = _verification_context(effect="effectful", state=worker_state)
    omo_dir = tmp_path / ".omo"
    _write_mesh(omo_dir, events)

    receipt = cap_sync.verify_material_against_mesh(omo_dir, _verification_envelope(material, request))

    assert receipt["status"] == status
    if failure_code is not None:
        assert receipt["failure_code"] == failure_code


def test_verifier_preserves_source_unprovable_when_lazy_mesh_projector_cannot_load(
    cap_sync, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, helpers
) -> None:
    material, request, events = _verification_context()
    omo_dir = tmp_path / ".omo"
    _write_mesh(omo_dir, events)
    monkeypatch.setattr(
        helpers,
        "_load_workflow_mesh_projection",
        lambda: (_ for _ in ()).throw(cap_sync.TraceBindingError("source_unprovable")),
    )

    assert cap_sync.verify_material_against_mesh(omo_dir, _verification_envelope(material, request)) == {
        "schema": "capability-admission-verification-receipt/v1",
        "status": "rejected",
        "failure_code": "source_unprovable",
        "value_indicator_policy": False,
    }


@pytest.mark.parametrize(
    "reader",
    [
        lambda _size: (_ for _ in ()).throw(OSError("private input path")),
        lambda size: b"x" * size,
        lambda _size: b"{not-json}",
    ],
)
def test_verify_material_cli_always_emits_the_exact_redacted_receipt_for_stdin_failures(
    cap_sync, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], reader
) -> None:
    monkeypatch.setattr(cap_sync.sys, "stdin", SimpleNamespace(buffer=SimpleNamespace(read=reader)))

    assert cap_sync.main(["verify-material"]) == 4

    receipt = json.loads(capsys.readouterr().out)
    assert receipt == {
        "schema": "capability-admission-verification-receipt/v1",
        "status": "rejected",
        "failure_code": "native_route_unprovable",
        "value_indicator_policy": False,
    }


def test_verify_material_cli_reads_one_bounded_stdin_envelope_and_uses_fixed_omo_root(
    cap_sync, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(cap_sync.sys, "stdin", SimpleNamespace(buffer=SimpleNamespace(read=lambda _size: b"{}")))
    assert cap_sync.main(["verify-material"]) == 4
    receipt = json.loads(capsys.readouterr().out)
    assert receipt["status"] == "rejected"
    assert receipt["failure_code"] in {"native_route_unprovable", "admission_receipt_invalid"}
    assert "omo_dir" not in json.dumps(receipt, sort_keys=True)


def test_verify_material_cli_uses_only_fixed_root_omo_and_never_creates_files(
    cap_sync, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    material, request, events = _verification_context()
    envelope = _verification_envelope(material, request)
    encoded = json.dumps(envelope, sort_keys=True).encode("utf-8")
    root = tmp_path / "root"
    root.mkdir()
    _write_mesh(root / ".omo", events)
    monkeypatch.setattr(cap_sync, "ROOT", root)
    monkeypatch.setattr(cap_sync.sys, "stdin", SimpleNamespace(buffer=io.BytesIO(encoded)))
    before = _tree_snapshot(root)

    assert cap_sync.main(["verify-material"]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "verified"
    assert _tree_snapshot(root) == before

    empty_root = tmp_path / "empty-root"
    empty_root.mkdir()
    monkeypatch.setattr(cap_sync, "ROOT", empty_root)
    monkeypatch.setattr(cap_sync.sys, "stdin", SimpleNamespace(buffer=io.BytesIO(encoded)))
    before_empty = _tree_snapshot(empty_root)

    assert cap_sync.main(["verify-material"]) == 4
    assert json.loads(capsys.readouterr().out) == {
        "schema": "capability-admission-verification-receipt/v1",
        "status": "rejected",
        "failure_code": "source_unprovable",
        "value_indicator_policy": False,
    }
    assert _tree_snapshot(empty_root) == before_empty


def _tree_snapshot(root: Path) -> dict[str, tuple[bytes, int]]:
    """Capture every file below root so verifier reads cannot hide writes."""
    return {
        path.relative_to(root).as_posix(): (path.read_bytes(), path.stat().st_mode)
        for path in root.rglob("*")
        if path.is_file()
    }


def _forbid_verifier_gateways(cap_sync, monkeypatch: pytest.MonkeyPatch) -> dict[str, int]:
    calls = {"gateway": 0, "subprocess": 0}

    def forbidden_gateway(*args, **kwargs):
        calls["gateway"] += 1
        raise AssertionError("verifier must not reach a native gateway")

    def forbidden_subprocess(*args, **kwargs):
        calls["subprocess"] += 1
        raise AssertionError("verifier must not spawn a subprocess")

    monkeypatch.setattr(cap_sync, "_load_native_gateway", forbidden_gateway)
    monkeypatch.setattr(cap_sync, "execute_gateway_operation", forbidden_gateway)
    monkeypatch.setattr(cap_sync.subprocess, "run", forbidden_subprocess)
    return calls


def test_verifier_is_python39_safe_and_legacy_import_does_not_load_omo(cap_sync, registry: dict, tmp_path: Path, monkeypatch, helpers) -> None:
    source = SYNC_PATH.read_text(encoding="utf-8")
    ast.parse(source, filename=str(SYNC_PATH), feature_version=(3, 9))
    assert "from datetime import UTC" not in source
    assert "omo.workflow_mesh" not in source
    assert "Path | str" not in source
    assert "OMO_SRC" not in source
    assert callable(helpers._load_workflow_mesh_projection)

    registry_path = tmp_path / "registry.yaml"
    registry_path.write_text(yaml.safe_dump(registry, sort_keys=False), encoding="utf-8")
    monkeypatch.setattr(
        helpers,
        "_load_workflow_mesh_projection",
        lambda: (_ for _ in ()).throw(AssertionError("legacy command loaded OMO")),
    )
    assert cap_sync.main(["find", "--id", "mcp-server:omo", "--registry", str(registry_path)]) == 0


def test_xcode_python39_subprocess_positively_verifies_temp_mesh(tmp_path: Path) -> None:
    python39 = Path("/Applications/Xcode.app/Contents/Developer/usr/bin/python3")
    assert python39.is_file(), "the required Xcode Python 3.9 interpreter is unavailable"
    material, request, events = _verification_context(effect="effectful", state="active")
    omo_dir = tmp_path / ".omo"
    _write_mesh(omo_dir, events)
    envelope_path = tmp_path / "envelope.json"
    envelope_path.write_text(
        json.dumps(_verification_envelope(material, request), sort_keys=True), encoding="utf-8"
    )
    before = _tree_snapshot(tmp_path)
    probe = """
import importlib.util
import json
import sys

source_path, omo_dir, envelope_path = sys.argv[1:]
spec = importlib.util.spec_from_file_location("capability_sync_python39_probe", source_path)
if spec is None or spec.loader is None:
    raise SystemExit("unable to load capability-sync")
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
with open(envelope_path, "r", encoding="utf-8") as handle:
    envelope = json.load(handle)
receipt = module.verify_material_against_mesh(omo_dir, envelope)
print(json.dumps(receipt, sort_keys=True))
raise SystemExit(0 if receipt.get("status") == "verified" else 1)
"""

    completed = subprocess.run(
        [str(python39), "-c", probe, str(SYNC_PATH), str(omo_dir), str(envelope_path)],
        cwd=ROOT,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    receipt = json.loads(completed.stdout)
    assert receipt["status"] == "verified"
    assert receipt["authority"] == "omo-workflow-mesh"
    assert receipt["capability_id"] == material["capability"]["id"]
    assert _tree_snapshot(tmp_path) == before


def test_mesh_reader_uses_separate_log_bound_and_rejects_path_replacement(
    cap_sync, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, helpers
) -> None:
    material, request, events = _verification_context()
    omo_dir = tmp_path / ".omo"
    _write_mesh(omo_dir, events)
    log = omo_dir / "_knowledge" / "workflow-mesh" / "events.jsonl"
    assert cap_sync.MAX_MESH_LOG_BYTES > cap_sync.MAX_INPUT_JSON_BYTES

    # A Mesh log is not stdin: shrinking only the stdin cap must not reject it.
    monkeypatch.setattr(cap_sync, "MAX_INPUT_JSON_BYTES", 1)
    assert cap_sync.verify_material_against_mesh(omo_dir, _verification_envelope(material, request))["status"] == "verified"

    replacement = log.with_name("replacement.jsonl")
    replacement.write_bytes(log.read_bytes())
    calls = 0

    def replace_after_open(path: Path):
        nonlocal calls
        calls += 1
        if calls == 1:
            replacement.replace(log)
        return path.stat()

    monkeypatch.setattr(helpers, "_mesh_path_stat", replace_after_open)
    rejected = cap_sync.verify_material_against_mesh(omo_dir, _verification_envelope(material, request))
    assert rejected == {
        "schema": "capability-admission-verification-receipt/v1",
        "status": "rejected",
        "failure_code": "source_unprovable",
        "value_indicator_policy": False,
    }


@pytest.mark.parametrize("effect,state", [("read_only", "dispatched"), ("read_only", "running"), ("effectful", "dispatched"), ("effectful", "running")])
def test_verifier_accepts_exact_projected_dispatch_context_without_writes(
    cap_sync, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, effect: str, state: str
) -> None:
    material, request, events = _verification_context(effect=effect, state=state)
    omo_dir = tmp_path / ".omo"
    _write_mesh(omo_dir, events)
    before = _tree_snapshot(omo_dir)
    calls = _forbid_verifier_gateways(cap_sync, monkeypatch)

    receipt = cap_sync.verify_material_against_mesh(omo_dir, _verification_envelope(material, request))

    assert receipt["status"] == "verified"
    assert _tree_snapshot(omo_dir) == before
    assert calls == {"gateway": 0, "subprocess": 0}


@pytest.mark.parametrize(
    ("mutation", "failure_code"),
    [
        (lambda material, request, events: events[1]["payload"]["admission"].update({"expires_at": "2000-01-01T00:00:00+00:00"}), "admission_receipt_invalid"),
        (lambda material, request, events: events[1]["payload"]["admission"]["request_identity"].update({"packet_id": "other-packet"}), "admission_receipt_invalid"),
        (lambda material, request, events: events[1]["payload"]["admission"]["request_identity"].update({"packet_hash": "sha256:" + "0" * 64}), "admission_receipt_invalid"),
        (lambda material, request, events: events[1]["payload"]["admission"].update({"capabilities": []}), "admission_receipt_invalid"),
        (lambda material, request, events: events[1]["payload"]["admission"].update({"proof": "0" * 64}), "admission_receipt_invalid"),
        (lambda material, request, events: material["admission"].update({"admission_id": "other-admission"}), "admission_receipt_invalid"),
        (lambda material, request, events: material["binding"].update({"workflow_run_id": "other-run"}), "admission_contradiction"),
        (lambda material, request, events: request["payload"].update({"operation": "drifted"}), "native_route_unprovable"),
    ],
)
def test_verifier_rejects_bound_admission_and_material_mismatches_without_writes(
    cap_sync, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mutation, failure_code: str
) -> None:
    material, request, events = _verification_context()
    mutation(material, request, events)
    omo_dir = tmp_path / ".omo"
    _write_mesh(omo_dir, events)
    before = _tree_snapshot(omo_dir)
    calls = _forbid_verifier_gateways(cap_sync, monkeypatch)

    receipt = cap_sync.verify_material_against_mesh(omo_dir, _verification_envelope(material, request))

    assert receipt["status"] == "rejected"
    assert receipt["failure_code"] == failure_code
    assert _tree_snapshot(omo_dir) == before
    assert calls == {"gateway": 0, "subprocess": 0}


def test_verifier_rejects_when_native_verifier_is_unavailable_without_outbound_calls(
    cap_sync, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, helpers
) -> None:
    material, request, events = _verification_context()
    omo_dir = tmp_path / ".omo"
    _write_mesh(omo_dir, events)
    calls = _forbid_verifier_gateways(cap_sync, monkeypatch)
    monkeypatch.setattr(cap_sync, "NATIVE_EXECUTION_LIBS_AVAILABLE", False)
    monkeypatch.setattr(helpers, "NATIVE_EXECUTION_LIBS_AVAILABLE", False)

    assert cap_sync.verify_material_against_mesh(omo_dir, _verification_envelope(material, request)) == {
        "schema": "capability-admission-verification-receipt/v1",
        "status": "rejected",
        "failure_code": "native_route_unprovable",
        "value_indicator_policy": False,
    }
    assert calls == {"gateway": 0, "subprocess": 0}


@pytest.mark.parametrize("state", ["dispatched", "running"])
def test_verifier_requires_exact_step_run_projection_for_dispatched_paths(
    cap_sync, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, state: str, helpers
) -> None:
    material, request, events = _verification_context(effect="read_only", state=state)
    admission = events[1]["payload"]["admission"]
    omo_dir = tmp_path / ".omo"
    _write_mesh(omo_dir, events)
    monkeypatch.setattr(helpers, "_load_workflow_mesh_projection", lambda: lambda _events, _run_id: {
        "workflow_run_id": material["binding"]["workflow_run_id"],
        "state": state,
        "admission": admission,
        "step_runs": {},
        "worker": {
            "dispatch_id": material["binding"]["dispatch_id"],
            "worker_id": material["binding"]["actor_id"],
            "step_run_id": material["admission"]["step_run_id"],
            "admission_id": material["admission"]["admission_id"],
            "packet_id": material["binding"]["packet_id"],
            "packet_hash": material["binding"]["packet_hash"],
        },
    })

    receipt = cap_sync.verify_material_against_mesh(omo_dir, _verification_envelope(material, request))

    assert receipt["failure_code"] == "admission_receipt_invalid"


def test_effectful_admitted_and_missing_or_wrong_step_run_are_rejected(cap_sync, tmp_path: Path) -> None:
    material, request, events = _verification_context(effect="effectful", state="admitted")
    omo_dir = tmp_path / ".omo"
    _write_mesh(omo_dir, events)
    assert cap_sync.verify_material_against_mesh(omo_dir, _verification_envelope(material, request))["failure_code"] == "admission_contradiction"

    material, request, events = _verification_context(effect="effectful", state="dispatched")
    events[2]["payload"]["admission_id"] = "wrong-admission"
    _write_mesh(omo_dir, events)
    assert cap_sync.verify_material_against_mesh(omo_dir, _verification_envelope(material, request))["failure_code"] == "admission_receipt_invalid"


def test_verifier_rejects_expired_admission_after_reproof(cap_sync, tmp_path: Path) -> None:
    material, request, events = _verification_context()
    grant = events[1]["payload"]["admission"]
    grant["issued_at"] = "1999-01-01T00:00:00+00:00"
    grant["expires_at"] = "2000-01-01T00:00:00+00:00"
    proof_input = dict(grant)
    proof_input.pop("proof", None)
    grant["proof"] = hashlib.sha256(
        json.dumps(proof_input, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    events[1]["payload"]["issued_at"] = grant["issued_at"]
    events[1]["payload"]["expires_at"] = grant["expires_at"]
    events[1]["payload"]["proof"] = grant["proof"]
    material["admission"]["receipt_digest"] = "sha256:" + grant["proof"]
    omo_dir = tmp_path / ".omo"
    _write_mesh(omo_dir, events)

    receipt = cap_sync.verify_material_against_mesh(omo_dir, _verification_envelope(material, request))

    assert receipt["failure_code"] == "admission_expired"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("capability_id", "bos-service:bos://governance/other"),
        ("operation_id", "other"),
        ("effect_classification", "effectful"),
    ],
)
def test_verifier_rejects_expected_material_mismatch(cap_sync, tmp_path: Path, field: str, value: str) -> None:
    material, request, events = _verification_context()
    omo_dir = tmp_path / ".omo"
    _write_mesh(omo_dir, events)
    envelope = _verification_envelope(material, request)
    envelope["expected"][field] = value

    receipt = cap_sync.verify_material_against_mesh(omo_dir, envelope)

    assert receipt["failure_code"] == "native_route_unprovable"


def test_verifier_rejects_malformed_or_oversize_mesh_log_with_redacted_failure(cap_sync, tmp_path: Path, monkeypatch, helpers) -> None:
    material, request, events = _verification_context()
    omo_dir = tmp_path / ".omo"
    _write_mesh(omo_dir, events)
    log = omo_dir / "_knowledge" / "workflow-mesh" / "events.jsonl"
    log.write_text("not-json\n", encoding="utf-8")
    malformed = cap_sync.verify_material_against_mesh(omo_dir, _verification_envelope(material, request))
    assert malformed["failure_code"] == "admission_receipt_invalid"
    assert str(log) not in json.dumps(malformed, sort_keys=True)

    _write_mesh(omo_dir, events)
    monkeypatch.setattr(cap_sync, "MAX_MESH_LOG_BYTES", 1)
    monkeypatch.setattr(helpers, "MAX_MESH_LOG_BYTES", 1)
    oversize = cap_sync.verify_material_against_mesh(omo_dir, _verification_envelope(material, request))
    assert oversize["failure_code"] == "source_unprovable"
    assert str(log) not in json.dumps(oversize, sort_keys=True)


def test_unbound_invoke_fails_closed_before_gateway(cap_sync, monkeypatch, registry, tmp_path, capsys):
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
    assert rc == 4
    assert calls == 0
    assert receipt["status"] == "rejected"
    assert receipt["failure_code"] == "binding_required"
    assert receipt["states"] == {"invoked": False, "evidenced": False, "independently_verified": False}
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
