"""Contract tests for the read-only capability federation graph auditor."""

from __future__ import annotations

import ast
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "lib" / "capability_federation_audit.py"
PROJECTION_MODULE = ROOT / "lib" / "agent_workflow_projection.py"
SCRIPT = ROOT / "bin" / "capability-sync.py"


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("capability_federation_audit", MODULE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _load_capability_sync_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("capability_sync_fixture", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _load_projection_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("agent_workflow_projection_fixture", PROJECTION_MODULE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _workspace(tmp_path: Path) -> Path:
    _write(
        tmp_path / ".omo/_truth/registry/capability-providers.yaml",
        "schema: capability-providers/v2\n"
        "compute_plane:\n"
        "  gateway: aetherforge\n"
        "  runtime: omlxc\n"
        "providers:\n"
        "  - id: provider-a\n"
        "    capabilities: [code_edit]\n"
        "    launch_argv: [provider-a]\n"
        "    version_probe_argv: [provider-a, --version]\n"
        "    availability_policy: runtime_observation_required\n",
    )
    _write(
        tmp_path / ".omo/_truth/registry/workers.yaml",
        "---\nstatus: active\n---\n"
        "workers:\n"
        "  - id: worker-a\n"
        "    admission_state: admitted\n"
        "    provider_ref: provider-a\n"
        "    transports:\n"
        "      bounded_exec:\n"
        "        command: provider-a run\n"
        "        worker_ack_protocol: omo-worker-origin-ack/v1\n"
        "        provider_conformance:\n"
        "          transport_id: provider_a_exec\n"
        "          backend_ref: provider-a\n"
        "          route_ref: null\n"
        "          operation_level: L1\n"
        "          write_scope: bounded\n"
        "          workspace_admission: verified_independent_clone\n"
        "          states: [succeeded, failed]\n",
    )
    _write(
        tmp_path / ".omo/_truth/registry/agent-workflows/_root.yaml",
        "version: 1\ndescription: Canonical workflow registry\n",
    )
    _write(
        tmp_path / ".omo/_truth/registry/agent-workflows/workflows/project-code-change.yaml",
        "id: project-code-change\nrun_frequency: on_demand\ntitle: Project code change\n",
    )
    projection_module = _load_projection_module()
    workflow_registry = tmp_path / ".omo/_truth/registry/agent-workflows"
    registry_payload = {
            "version": 1,
            "description": "Canonical workflow registry",
            "workflows": [
                {
                    "id": "project-code-change",
                    "run_frequency": "on_demand",
                    "title": "Project code change",
                }
            ],
        }
    projection_module.sync_projection(
        registry_payload,
        workflow_registry,
        tmp_path / ".omo/_truth/registry/agent-workflows.yaml",
        source_digest_bound=projection_module.source_digest(workflow_registry),
    )
    _write(
        tmp_path / "projects/omo/src/omo/mcp_server.py",
        "# source file for the generated projection fixture\n",
    )
    _write(
        tmp_path / "docs/generated/capability-registry.yaml",
        "schema: capability-registry/v1\n"
        "writer: bin/cockpit/gen-capability-registry.py\n"
        "generator: bin/cockpit/gen-capability-registry.py\n"
        "mcp_servers:\n"
        "  - id: omo\n"
        "    file: projects/omo/src/omo/mcp_server.py\n"
        "    exists: true\n"
        "    online: true\n",
    )
    return tmp_path


def _codes(report: dict[str, object]) -> list[str]:
    return [item["code"] for item in report["diagnostics"]]  # type: ignore[index]


def test_golden_graph_is_deterministic_and_keeps_projection_non_authoritative(tmp_path: Path) -> None:
    module = _load_module()
    workspace = _workspace(tmp_path)

    first = module.audit_workspace(workspace)
    second = module.audit_workspace(workspace)

    assert first == second
    assert first["schema"] == "capability-federation-audit/v1"
    assert first["authority"]["providers"] == ".omo/_truth/registry/capability-providers.yaml"
    assert first["authority"]["workers"] == ".omo/_truth/registry/workers.yaml"
    assert first["projection"]["authority"] == "projection"
    assert first["projection"]["admission_inference"] == "forbidden"
    assert first["state_model"]["evidenced"] == "eligible evidence recorded; not independent verification"
    assert first["workers"][0]["state"] == "admitted"
    assert first["projection"]["projected_entries"] == 1
    assert "CAP_FED_WORKFLOW_DUAL_AUTHORITY" not in _codes(first)
    assert "CAP_FED_WORKFLOW_REGISTRY_DIVERGENCE" not in _codes(first)
    rendered = json.dumps(first, ensure_ascii=False, sort_keys=True)
    assert str(workspace) not in rendered


def test_dangling_provider_reference_is_a_stable_error(tmp_path: Path) -> None:
    module = _load_module()
    workspace = _workspace(tmp_path)
    workers = workspace / ".omo/_truth/registry/workers.yaml"
    workers.write_text(
        workers.read_text(encoding="utf-8").replace(
            "provider-a\n    transports", "missing-provider\n    transports", 1
        ),
        encoding="utf-8",
    )

    report = module.audit_workspace(workspace)

    assert report["verdict"] == "FAIL"
    assert "CAP_FED_DANGLING_PROVIDER_REF" in _codes(report)


def test_admitted_transport_requires_ack_and_complete_conformance(tmp_path: Path) -> None:
    module = _load_module()
    workspace = _workspace(tmp_path)
    workers = workspace / ".omo/_truth/registry/workers.yaml"
    workers.write_text(
        workers.read_text(encoding="utf-8")
        .replace("        worker_ack_protocol: omo-worker-origin-ack/v1\n", "")
        .replace("          states: [succeeded, failed]\n", ""),
        encoding="utf-8",
    )

    report = module.audit_workspace(workspace)

    codes = _codes(report)
    assert "CAP_FED_ADMITTED_TRANSPORT_ACK_MISSING" in codes
    assert "CAP_FED_ADMITTED_TRANSPORT_CONFORMANCE_INCOMPLETE" in codes


def test_admitted_transport_rejects_undeclared_backend_reference(tmp_path: Path) -> None:
    module = _load_module()
    workspace = _workspace(tmp_path)
    workers = workspace / ".omo/_truth/registry/workers.yaml"
    workers.write_text(
        workers.read_text(encoding="utf-8").replace("backend_ref: provider-a", "backend_ref: other-provider"),
        encoding="utf-8",
    )

    report = module.audit_workspace(workspace)

    assert report["verdict"] == "FAIL"
    assert "CAP_FED_ADMITTED_TRANSPORT_BACKEND_UNDECLARED" in _codes(report)


def test_admitted_transport_rejects_invalid_provider_profile_values(tmp_path: Path) -> None:
    module = _load_module()
    workspace = _workspace(tmp_path)
    workers = workspace / ".omo/_truth/registry/workers.yaml"
    workers.write_text(
        workers.read_text(encoding="utf-8")
        .replace("operation_level: L1", "operation_level: L9")
        .replace("states: [succeeded, failed]", "states: [unknown]"),
        encoding="utf-8",
    )

    report = module.audit_workspace(workspace)

    assert report["verdict"] == "FAIL"
    assert "CAP_FED_ADMITTED_TRANSPORT_CONFORMANCE_INVALID" in _codes(report)


def test_admitted_transport_accepts_valid_provider_profile(tmp_path: Path) -> None:
    module = _load_module()
    report = module.audit_workspace(_workspace(tmp_path))

    assert "CAP_FED_ADMITTED_TRANSPORT_CONFORMANCE_INVALID" not in _codes(report)
    assert "CAP_FED_ADMITTED_TRANSPORT_BACKEND_UNDECLARED" not in _codes(report)


def test_admitted_transport_accepts_declared_compute_plane_backend(tmp_path: Path) -> None:
    module = _load_module()
    workspace = _workspace(tmp_path)
    workers = workspace / ".omo/_truth/registry/workers.yaml"
    workers.write_text(
        workers.read_text(encoding="utf-8").replace("backend_ref: provider-a", "backend_ref: omlxc"),
        encoding="utf-8",
    )

    report = module.audit_workspace(workspace)

    assert "CAP_FED_ADMITTED_TRANSPORT_BACKEND_UNDECLARED" not in _codes(report)


def test_admitted_transports_reject_duplicate_conformance_transport_id(tmp_path: Path) -> None:
    module = _load_module()
    workspace = _workspace(tmp_path)
    workers = workspace / ".omo/_truth/registry/workers.yaml"
    workers.write_text(
        workers.read_text(encoding="utf-8") + "  - id: worker-b\n"
        "    admission_state: admitted\n"
        "    provider_ref: provider-a\n"
        "    transports:\n"
        "      independently_named_transport:\n"
        "        command: provider-a alternate\n"
        "        worker_ack_protocol: omo-worker-origin-ack/v1\n"
        "        provider_conformance:\n"
        "          transport_id: provider_a_exec\n"
        "          backend_ref: provider-a\n"
        "          route_ref: null\n"
        "          operation_level: L1\n"
        "          write_scope: bounded\n"
        "          workspace_admission: verified_independent_clone\n"
        "          states: [succeeded, failed]\n",
        encoding="utf-8",
    )

    report = module.audit_workspace(workspace)

    duplicate = next(
        item for item in report["diagnostics"] if item["code"] == "CAP_FED_ADMITTED_TRANSPORT_ID_DUPLICATE"
    )
    assert report["verdict"] == "FAIL"
    assert duplicate["subject"] == "transport_id:provider_a_exec"
    assert duplicate["detail"].endswith("worker-a:bounded_exec,worker-b:independently_named_transport")


def test_non_utf8_native_source_is_unprovable_not_a_crash(tmp_path: Path) -> None:
    module = _load_module()
    workspace = _workspace(tmp_path)
    (workspace / ".omo/_truth/registry/capability-providers.yaml").write_bytes(b"\xff\xfe\x00")

    report = module.audit_workspace(workspace)

    assert report["verdict"] == "UNPROVABLE"
    assert "CAP_FED_SOURCE_UNPROVABLE" in _codes(report)


def test_non_utf8_projection_is_unprovable_not_a_crash(tmp_path: Path) -> None:
    module = _load_module()
    workspace = _workspace(tmp_path)
    (workspace / "docs/generated/capability-registry.yaml").write_bytes(b"\xff\xfe\x00")

    report = module.audit_workspace(workspace)

    assert report["verdict"] == "UNPROVABLE"
    assert "CAP_FED_SOURCE_UNPROVABLE" in _codes(report)


def test_missing_source_is_unprovable_not_retired(tmp_path: Path) -> None:
    module = _load_module()
    workspace = _workspace(tmp_path)
    (workspace / "projects/omo/src/omo/mcp_server.py").unlink()

    report = module.audit_workspace(workspace)

    assert report["verdict"] == "UNPROVABLE"
    item = next(item for item in report["diagnostics"] if item["code"] == "CAP_FED_SOURCE_UNPROVABLE")
    assert item["status"] == "unprovable"
    assert "retired" not in json.dumps(item, ensure_ascii=False).lower()


def test_generated_projection_cannot_claim_ssot_authority(tmp_path: Path) -> None:
    module = _load_module()
    workspace = _workspace(tmp_path)
    projection = workspace / "docs/generated/capability-registry.yaml"
    projection.write_text(
        "# docs/generated/capability-registry.yaml — capability inventory SSOT\n"
        + projection.read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    report = module.audit_workspace(workspace)

    assert report["verdict"] == "FAIL"
    assert "CAP_FED_PROJECTION_AUTHORITY_CLAIM" in _codes(report)


def test_negated_projection_header_is_not_an_authority_claim(tmp_path: Path) -> None:
    module = _load_module()
    workspace = _workspace(tmp_path)
    projection = workspace / "docs/generated/capability-registry.yaml"
    projection.write_text(
        "# generated projection, not SSOT / 不是 SSOT\n" + projection.read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    report = module.audit_workspace(workspace)

    assert "CAP_FED_PROJECTION_AUTHORITY_CLAIM" not in _codes(report)


def test_strict_turns_existing_warning_into_non_zero_without_changing_default(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    (workspace / ".omo/_truth/registry/agent-workflows.yaml").unlink()
    default = subprocess.run(
        ["python3", str(SCRIPT), "federation-audit", "--workspace-root", str(workspace), "--json"],
        capture_output=True,
        text=True,
        check=False,
    )
    strict = subprocess.run(
        [
            "python3",
            str(SCRIPT),
            "federation-audit",
            "--workspace-root",
            str(workspace),
            "--json",
            "--strict",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert default.returncode == 0
    assert json.loads(default.stdout)["verdict"] == "WARN"
    assert json.loads(default.stdout)["strict"] is False
    assert strict.returncode == 1
    assert json.loads(strict.stdout)["verdict"] == "WARN"
    assert json.loads(strict.stdout)["strict"] is True
    assert json.loads(strict.stdout)["exit_code"] == 1


def test_workflow_projection_drift_and_wrong_authority_are_reported(tmp_path: Path) -> None:
    module = _load_module()
    workspace = _workspace(tmp_path)
    projection = workspace / ".omo/_truth/registry/agent-workflows.yaml"
    projection.write_text(
        projection.read_text(encoding="utf-8")
        .replace("authority: projection", "authority: ssot")
        .replace("id: project-code-change", "id: stale-workflow"),
        encoding="utf-8",
    )

    report = module.audit_workspace(workspace)

    codes = _codes(report)
    assert "CAP_FED_WORKFLOW_DUAL_AUTHORITY" in codes
    assert "CAP_FED_WORKFLOW_REGISTRY_DIVERGENCE" in codes


def test_workflow_projection_definition_drift_is_reported_with_id_parity(tmp_path: Path) -> None:
    module = _load_module()
    workspace = _workspace(tmp_path)
    projection = workspace / ".omo/_truth/registry/agent-workflows.yaml"
    projection.write_text(
        projection.read_text(encoding="utf-8").replace(
            "title: Project code change", "title: Stale compatibility title"
        ),
        encoding="utf-8",
    )

    report = module.audit_workspace(workspace)

    assert "CAP_FED_WORKFLOW_DUAL_AUTHORITY" not in _codes(report)
    assert "CAP_FED_WORKFLOW_REGISTRY_DIVERGENCE" in _codes(report)


def test_workflow_projection_cannot_drop_all_canonical_ids(tmp_path: Path) -> None:
    module = _load_module()
    workspace = _workspace(tmp_path)
    projection = workspace / ".omo/_truth/registry/agent-workflows.yaml"
    payload = yaml.safe_load(projection.read_text(encoding="utf-8"))
    payload["workflows"] = []
    projection.write_text(yaml.safe_dump(payload, sort_keys=True), encoding="utf-8")

    report = module.audit_workspace(workspace)

    assert "CAP_FED_WORKFLOW_DUAL_AUTHORITY" not in _codes(report)
    assert "CAP_FED_WORKFLOW_REGISTRY_DIVERGENCE" in _codes(report)


def test_script_parses_with_python_39_grammar() -> None:
    for path in (MODULE, SCRIPT):
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path), feature_version=(3, 9))


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


def _capability_registry() -> dict[str, object]:
    return {
        "schema": "capability-registry/v1",
        "owner": "workspace-capability-governance",
        "writer": "bin/cockpit/gen-capability-registry.py",
        "generator": "bin/cockpit/gen-capability-registry.py",
        "mcp_servers": [{"id": "omo", "name": "OMO", "exists": True, "tools": ["inspect"]}],
        "bos_services": {"domains": {}},
        "cli_commands": [],
    }


def test_trace_bound_resolution_receipt_is_deterministic_and_replay_verifiable() -> None:
    sync = _load_capability_sync_module()
    registry = _capability_registry()
    result = sync.resolve_capability(registry, capability_id="mcp-tool:omo:inspect")
    binding = _trace_binding()
    registry_content = yaml.safe_dump(registry, sort_keys=True).encode("utf-8")

    first = sync.build_resolution_receipt(
        result,
        registry_content,
        {"capability_id": "mcp-tool:omo:inspect"},
        binding=binding,
        projection_metadata=registry,
    )
    second = sync.build_resolution_receipt(
        result,
        registry_content,
        {"capability_id": "mcp-tool:omo:inspect"},
        binding=binding,
        projection_metadata=registry,
    )

    assert first == second
    assert first["schema"] == "capability-resolution-receipt/v1"
    assert first["trace_id"].startswith("sha256:")
    assert first["receipt_digest"].startswith("sha256:")
    assert first["resolution_source"] == {
        "authority": "projection",
        "digest": first["registry_digest"],
        "ref": "generated:capability-registry/v1",
    }
    assert first["capability"] == {
        "adapter_kind": "mcp_native",
        "id": "mcp-tool:omo:inspect",
        "kind": "mcp_tool",
        "native_owner": "mcp",
    }
    assert first["invocation"]["allowed"] is False
    assert first["states"] == {"evidenced": False, "independently_verified": False, "invoked": False}
    assert first["value_indicator_policy"] is False
    assert sync.validate_trace_bound_resolution_receipt(first) == first


def test_trace_bound_receipt_tamper_and_value_promotion_fail_closed() -> None:
    sync = _load_capability_sync_module()
    registry = _capability_registry()
    result = sync.resolve_capability(registry, capability_id="mcp-tool:omo:inspect")
    receipt = sync.build_resolution_receipt(
        result,
        yaml.safe_dump(registry, sort_keys=True).encode("utf-8"),
        {"capability_id": "mcp-tool:omo:inspect"},
        binding=_trace_binding(),
        projection_metadata=registry,
    )

    receipt["binding"]["dispatch_id"] = "tampered-dispatch"
    with pytest.raises(sync.TraceBindingError, match="trace_id_mismatch"):
        sync.validate_trace_bound_resolution_receipt(receipt)

    receipt = sync.build_resolution_receipt(
        result,
        yaml.safe_dump(registry, sort_keys=True).encode("utf-8"),
        {"capability_id": "mcp-tool:omo:inspect"},
        binding=_trace_binding(),
        projection_metadata=registry,
    )
    receipt["value_indicator_policy"] = True
    with pytest.raises(sync.TraceBindingError, match="value_promotion_forbidden"):
        sync.validate_trace_bound_resolution_receipt(receipt)

    receipt = sync.build_resolution_receipt(
        result,
        yaml.safe_dump(registry, sort_keys=True).encode("utf-8"),
        {"capability_id": "mcp-tool:omo:inspect"},
        binding=_trace_binding(),
        projection_metadata=registry,
    )
    receipt["receipt_digest"] = "sha256:" + "b" * 64
    with pytest.raises(sync.TraceBindingError, match="receipt_digest_mismatch"):
        sync.validate_trace_bound_resolution_receipt(receipt)


@pytest.mark.parametrize(
    "mutation,reason",
    [
        (lambda value: value.__setitem__("admission", {"required": False, "decision": "not_evaluated"}), "admission_invalid"),
        (lambda value: value.__setitem__("match_count", 2), "resolution_match_count_invalid"),
        (lambda value: value.__setitem__("candidate_id_digests", []), "resolution_candidate_digest_invalid"),
        (lambda value: value.__setitem__("selector_digest", "sha256:" + "c" * 64), "resolution_selector_digest_invalid"),
        (lambda value: value["capability"].__setitem__("native_owner", "agora"), "capability_semantics_invalid"),
    ],
)
def test_trace_bound_receipt_rejects_semantic_tampering_even_with_new_digest(mutation, reason) -> None:
    sync = _load_capability_sync_module()
    registry = _capability_registry()
    result = sync.resolve_capability(registry, capability_id="mcp-tool:omo:inspect")
    receipt = sync.build_resolution_receipt(
        result,
        yaml.safe_dump(registry, sort_keys=True).encode("utf-8"),
        {"capability_id": "mcp-tool:omo:inspect"},
        binding=_trace_binding(),
        projection_metadata=registry,
    )
    mutation(receipt)
    without_digest = dict(receipt)
    without_digest.pop("receipt_digest")
    receipt["receipt_digest"] = sync._digest(sync._canonical_json(without_digest))

    with pytest.raises(sync.TraceBindingError, match=reason):
        sync.validate_trace_bound_resolution_receipt(receipt)


@pytest.mark.parametrize(
    "mutation,reason",
    [
        (lambda value: value.update({"prompt": "secret prompt"}), "binding_unknown_fields"),
        (lambda value: value.__setitem__("actor_id", "/Users/private"), "binding_absolute_path_forbidden"),
        (lambda value: value.__setitem__("actor_id", "\\Users\\private"), "binding_absolute_path_forbidden"),
        (lambda value: value.__setitem__("actor_id", "agent with space"), "binding_identifier_invalid"),
        (lambda value: value.__setitem__("assignment_id", "assignment..parent"), "binding_identifier_invalid"),
        (lambda value: value.__setitem__("delivery_attempt_id", "a" * 257), "binding_identifier_invalid"),
        (lambda value: value.__setitem__("packet_hash", "not-a-digest"), "binding_packet_hash_invalid"),
    ],
)
def test_trace_binding_rejects_unknown_sensitive_path_and_invalid_digest(mutation, reason) -> None:
    sync = _load_capability_sync_module()
    binding = _trace_binding()
    mutation(binding)

    with pytest.raises(sync.TraceBindingError, match=reason):
        sync.validate_trace_binding(binding)


def test_find_binding_json_is_read_only_and_rejects_query_selector(tmp_path: Path) -> None:
    registry_path = tmp_path / "capability-registry.yaml"
    registry_path.write_text(yaml.safe_dump(_capability_registry(), sort_keys=True), encoding="utf-8")
    binding_path = tmp_path / "binding.json"
    binding_path.write_text(json.dumps(_trace_binding(), sort_keys=True), encoding="utf-8")
    before = {path: (path.stat().st_mtime_ns, path.read_bytes()) for path in tmp_path.iterdir()}

    run = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "find",
            "--id",
            "mcp-tool:omo:inspect",
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
            str(SCRIPT),
            "find",
            "--query",
            "inspect",
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


def test_find_without_binding_preserves_legacy_receipt_contract(tmp_path: Path) -> None:
    registry_path = tmp_path / "capability-registry.yaml"
    registry_path.write_text(yaml.safe_dump(_capability_registry(), sort_keys=True), encoding="utf-8")

    run = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "find",
            "--id",
            "mcp-tool:omo:inspect",
            "--registry",
            str(registry_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    receipt = json.loads(run.stdout)

    assert run.returncode == 0
    assert receipt["status"] == "resolved"
    assert receipt["capability_id"] == "mcp-tool:omo:inspect"
    assert receipt["adapter"] == {"kind": "mcp_native", "target": "omo/inspect"}
    assert "binding" not in receipt
    assert "trace_id" not in receipt
    assert "receipt_digest" not in receipt


def test_bound_find_reports_unprovable_when_projection_cannot_be_read(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    sync = _load_capability_sync_module()
    binding_path = tmp_path / "binding.json"
    binding_path.write_text(json.dumps(_trace_binding(), sort_keys=True), encoding="utf-8")

    assert sync.main(
        [
            "find",
            "--id",
            "mcp-tool:omo:inspect",
            "--binding-json",
            str(binding_path),
            "--registry",
            str(tmp_path / "missing-registry.yaml"),
        ]
    ) == 4
    receipt = json.loads(capsys.readouterr().out)

    assert receipt["status"] == "rejected"
    assert receipt["failure_code"] == "source_unprovable"
    assert receipt["invocation"]["allowed"] is False


def test_bound_resolution_rejects_legacy_registry_without_canonical_projection_metadata(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    sync = _load_capability_sync_module()
    legacy_registry = {
        "version": "1.0.0",
        "mcp_servers": [{"id": "omo", "name": "OMO", "exists": True, "tools": ["inspect"]}],
        "bos_services": {"domains": {}},
        "cli_commands": [],
    }
    registry_path = tmp_path / "legacy-registry.yaml"
    binding_path = tmp_path / "binding.json"
    registry_path.write_text(yaml.safe_dump(legacy_registry, sort_keys=True), encoding="utf-8")
    binding_path.write_text(json.dumps(_trace_binding(), sort_keys=True), encoding="utf-8")

    assert sync.load_registry(registry_path)["version"] == "1.0.0"
    assert sync.main(
        ["find", "--id", "mcp-tool:omo:inspect", "--binding-json", str(binding_path), "--registry", str(registry_path)]
    ) == 4
    receipt = json.loads(capsys.readouterr().out)

    assert receipt["failure_code"] == "source_unprovable"
    assert receipt["invocation"]["allowed"] is False


def test_bound_resolution_maps_not_found_and_ambiguous_to_stable_failures() -> None:
    sync = _load_capability_sync_module()
    registry = _capability_registry()
    content = yaml.safe_dump(registry, sort_keys=True).encode("utf-8")
    binding = _trace_binding()
    missing = sync.resolve_capability(registry, capability_id="mcp-tool:omo:missing")

    with pytest.raises(sync.TraceBindingError, match="resolution_not_found"):
        sync.build_resolution_receipt(
            missing,
            content,
            {"capability_id": "mcp-tool:omo:missing"},
            binding=binding,
            projection_metadata=registry,
        )

    registry["mcp_servers"].append(dict(registry["mcp_servers"][0]))
    ambiguous = sync.resolve_capability(registry, capability_id="mcp-tool:omo:inspect")
    with pytest.raises(sync.TraceBindingError, match="resolution_ambiguous"):
        sync.build_resolution_receipt(
            ambiguous,
            yaml.safe_dump(registry, sort_keys=True).encode("utf-8"),
            {"capability_id": "mcp-tool:omo:inspect"},
            binding=binding,
            projection_metadata=registry,
        )


def test_bound_resolution_rejects_unsafe_capability_identity_and_adapter_semantics() -> None:
    sync = _load_capability_sync_module()
    registry = _capability_registry()
    registry["mcp_servers"][0]["tools"] = ["inspect secret"]
    content = yaml.safe_dump(registry, sort_keys=True).encode("utf-8")
    unsafe = sync.resolve_capability(registry, capability_id="mcp-tool:omo:inspect secret")

    with pytest.raises(sync.TraceBindingError, match="capability_id_invalid"):
        sync.build_resolution_receipt(
            unsafe,
            content,
            {"capability_id": "mcp-tool:omo:inspect secret"},
            binding=_trace_binding(),
            projection_metadata=registry,
        )

    registry = _capability_registry()
    result = sync.resolve_capability(registry, capability_id="mcp-tool:omo:inspect")
    result.capability["adapter"]["kind"] = "bos_native"
    with pytest.raises(sync.TraceBindingError, match="capability_semantics_invalid"):
        sync.build_resolution_receipt(
            result,
            yaml.safe_dump(registry, sort_keys=True).encode("utf-8"),
            {"capability_id": "mcp-tool:omo:inspect"},
            binding=_trace_binding(),
            projection_metadata=registry,
        )


def test_bound_find_cli_maps_not_found_and_ambiguous_to_stable_failures(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    sync = _load_capability_sync_module()
    registry_path = tmp_path / "capability-registry.yaml"
    binding_path = tmp_path / "binding.json"
    binding_path.write_text(json.dumps(_trace_binding(), sort_keys=True), encoding="utf-8")
    registry_path.write_text(yaml.safe_dump(_capability_registry(), sort_keys=True), encoding="utf-8")

    assert sync.main(
        ["find", "--id", "mcp-tool:omo:missing", "--binding-json", str(binding_path), "--registry", str(registry_path)]
    ) == 4
    assert json.loads(capsys.readouterr().out)["failure_code"] == "resolution_not_found"

    registry = _capability_registry()
    registry["mcp_servers"].append(dict(registry["mcp_servers"][0]))
    registry_path.write_text(yaml.safe_dump(registry, sort_keys=True), encoding="utf-8")
    assert sync.main(
        ["find", "--id", "mcp-tool:omo:inspect", "--binding-json", str(binding_path), "--registry", str(registry_path)]
    ) == 4
    assert json.loads(capsys.readouterr().out)["failure_code"] == "resolution_ambiguous"


def test_duplicate_provider_authority_claim_is_reported(tmp_path: Path) -> None:
    module = _load_module()
    workspace = _workspace(tmp_path)
    providers = workspace / ".omo/_truth/registry/capability-providers.yaml"
    providers.write_text(
        providers.read_text(encoding="utf-8") + providers.read_text(encoding="utf-8").split("providers:\n", 1)[1],
        encoding="utf-8",
    )

    report = module.audit_workspace(workspace)

    assert "CAP_FED_DUPLICATE_AUTHORITY_CLAIM" in _codes(report)


def test_cli_is_read_only_and_json_is_stable(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    before = {
        path.relative_to(workspace): (path.stat().st_mtime_ns, path.read_bytes())
        for path in workspace.rglob("*")
        if path.is_file()
    }

    first = subprocess.run(
        ["python3", str(SCRIPT), "federation-audit", "--workspace-root", str(workspace), "--json"],
        capture_output=True,
        text=True,
        check=False,
    )
    second = subprocess.run(
        ["python3", str(SCRIPT), "federation-audit", "--workspace-root", str(workspace), "--json"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert first.returncode == second.returncode == 0
    assert first.stdout == second.stdout
    assert json.loads(first.stdout)["schema"] == "capability-federation-audit/v1"
    after = {
        path.relative_to(workspace): (path.stat().st_mtime_ns, path.read_bytes())
        for path in workspace.rglob("*")
        if path.is_file()
    }
    assert after == before
    assert not os.path.isabs(json.loads(first.stdout)["authority"]["providers"])
