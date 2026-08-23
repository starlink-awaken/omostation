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

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "lib" / "capability_federation_audit.py"
SCRIPT = ROOT / "bin" / "capability-sync.py"


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("capability_federation_audit", MODULE)
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
        "version: 1\nworkflows:\n  project-code-change:\n    title: Project code change\n",
    )
    _write(
        tmp_path / ".omo/_truth/registry/agent-workflows/workflows/project-code-change.yaml",
        "id: project-code-change\ntitle: Project code change\n",
    )
    _write(
        tmp_path / ".omo/_truth/registry/agent-workflows.yaml",
        "version: 1\nworkflows:\n  project-code-change:\n    title: Project code change\n",
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
    assert "CAP_FED_WORKFLOW_DUAL_AUTHORITY" in _codes(first)
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


def test_script_parses_with_python_39_grammar() -> None:
    for path in (MODULE, SCRIPT):
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path), feature_version=(3, 9))


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
