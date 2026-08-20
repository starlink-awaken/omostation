"""Contract tests for the single capability registry spine."""

from __future__ import annotations

import ast
import importlib.util
import json
import sys
from pathlib import Path

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
                        "transport": "in-process",
                        "status": "active",
                    }
                ]
            },
        },
        "cli_commands": [{"name": "status", "description": "show status"}],
    }


def test_only_canonical_generator_can_write_registry(generator) -> None:
    sync_source = SYNC_PATH.read_text(encoding="utf-8")
    registry = generator.build_registry()

    assert "write_text(" not in sync_source
    assert "scan_all_sources" not in sync_source
    assert registry["schema"] == "capability-registry/v1"
    assert registry["owner"] == "workspace-capability-governance"
    assert registry["writer"] == "bin/cockpit/gen-capability-registry.py"


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


def test_make_and_ci_use_canonical_check_entrypoint() -> None:
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    workflow = (ROOT / ".github/workflows/ci-lint.yml").read_text(encoding="utf-8")
    command = "bin/cockpit/gen-capability-registry.py --check"

    assert "check-capability-registry:" in makefile
    assert command in makefile
    assert command in workflow
    assert "bin/capability-sync.py sync" not in makefile
    assert "bin/capability-sync.py sync" not in workflow


def test_python39_grammar_is_supported() -> None:
    for path in (SYNC_PATH, GENERATOR_PATH):
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path), feature_version=(3, 9))


def test_schema_v1_without_new_metadata_remains_readable(cap_sync, registry: dict, tmp_path: Path) -> None:
    path = tmp_path / "registry.yaml"
    path.write_text(yaml.safe_dump(registry, sort_keys=False), encoding="utf-8")

    loaded = cap_sync.load_registry(path)

    assert loaded["version"] == "1.0.0"
    assert cap_sync.resolve_capability(loaded, capability_id="mcp-server:omo").status == "resolved"


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
    assert not hasattr(cap_sync, "invoke_capability")


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
