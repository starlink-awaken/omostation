"""B4-C static native capability inspection contract tests."""

from __future__ import annotations

import ast
import copy
import importlib.util
import json
import os
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
LIB_PATH = ROOT / "lib" / "capability_native_inspection.py"
SOURCES_PATH = ROOT / "lib" / "capability_native_sources.py"
RECEIPT_PATH = ROOT / "lib" / "capability_native_receipt.py"
SYNC_PATH = ROOT / "bin" / "capability-sync.py"
if str(ROOT / "lib") not in sys.path:
    sys.path.insert(0, str(ROOT / "lib"))

import capability_native_inspection as native_inspection  # noqa: E402
from capability_native_inspection import (  # noqa: E402
    NativeInspectionError,
    _read_stable_source,
    inspect_native_capability,
    validate_native_inspection_receipt,
)
from capability_trace_binding import _canonical_json, _digest  # noqa: E402


def _load_sync():
    spec = importlib.util.spec_from_file_location("capability_sync_native_contract", SYNC_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


SYNC = _load_sync()


def _binding() -> dict[str, str]:
    return {
        "correlation_id": "corr-b4c-001",
        "workflow_run_id": "run-b4c-001",
        "packet_id": "packet-b4c-001",
        "packet_hash": "sha256:" + "b" * 64,
        "assignment_id": "assignment-b4c-001",
        "dispatch_id": "dispatch-b4c-001",
        "actor_id": "blueprint-native-inspection",
        "delivery_attempt_id": "b4-c-20260823-01",
    }


def _registry() -> dict:
    return {
        "version": "1.0.0",
        "schema": "capability-registry/v1",
        "owner": "workspace-capability-governance",
        "writer": "bin/cockpit/gen-capability-registry.py",
        "generated_at": "1970-01-01T00:00:00Z",
        "totals": {"mcp_servers": 1, "mcp_tools": 1, "bos_services": 1, "bos_domains": 1, "cli_commands": 0},
        "mcp_servers": [
            {
                "id": "demo",
                "name": "Demo",
                "file": "native/demo_mcp.py",
                "exists": True,
                "tools": ["inspect_item"],
            }
        ],
        "bos_services": {
            "domains": {
                "governance": [
                    {
                        "uri": "bos://governance/demo",
                        "description": "demo",
                        "transport": "internal",
                        "status": "active",
                    }
                ]
            }
        },
        "cli_commands": [],
    }


def _registry_bytes(registry: dict) -> bytes:
    return yaml.safe_dump(registry, sort_keys=True).encode("utf-8")


def _resolution_receipt(registry: dict, capability_id: str) -> dict:
    content = _registry_bytes(registry)
    selector = {"capability_id": capability_id}
    result = SYNC.resolve_capability(registry, **selector)
    return SYNC.build_resolution_receipt(
        result,
        content,
        selector,
        binding=_binding(),
        projection_metadata=registry,
    )


@pytest.fixture
def authority_root(tmp_path: Path) -> Path:
    skill = tmp_path / ".agents/skills/demo/SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("---\nname: demo\ndescription: safe metadata\nversion: 1.2\n---\nSECRET PROMPT\n", encoding="utf-8")
    workflow = tmp_path / ".omo/_truth/registry/agent-workflows/workflows/demo.yaml"
    workflow.parent.mkdir(parents=True)
    workflow.write_text("id: demo\ntitle: Demo workflow\n", encoding="utf-8")
    mcp = tmp_path / "native/demo_mcp.py"
    mcp.parent.mkdir(parents=True)
    mcp.write_text(
        "from fastmcp import FastMCP\n"
        "mcp = FastMCP('demo')\n"
        "@mcp.tool()\n"
        "async def inspect_item(value: str) -> str:\n"
        "    return value\n",
        encoding="utf-8",
    )
    bos = tmp_path / "projects/agora/etc/bos-services.yaml"
    bos.parent.mkdir(parents=True)
    bos.write_text(
        yaml.safe_dump(
            {
                "services": [
                    {
                        "uri": "bos://governance/demo",
                        "command": ["python3", "secret-provider.py", "--token", "SECRET"],
                        "transport": "stdio",
                    }
                ]
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    return tmp_path


@pytest.mark.parametrize(
    ("capability_id", "kind", "source_schema"),
    [
        ("skill:demo", "skill", "skill-markdown-frontmatter/v1"),
        ("workflow:demo", "workflow", "agent-workflow-canonical-yaml/v1"),
        ("mcp-tool:demo:inspect_item", "mcp_tool", "python-ast-fastmcp/v1"),
        ("bos-service:bos://governance/demo", "bos_service", "agora-bos-services-yaml/v1"),
    ],
)
def test_four_native_kinds_emit_golden_non_execution_receipts(
    authority_root: Path, capability_id: str, kind: str, source_schema: str
) -> None:
    registry = _registry()
    kwargs = {"binding": _binding()} if kind in {"skill", "workflow"} else {
        "resolution_receipt": _resolution_receipt(registry, capability_id)
    }
    receipt = inspect_native_capability(
        root=authority_root,
        capability_id=capability_id,
        registry=registry,
        registry_content=_registry_bytes(registry),
        **kwargs,
    )

    assert receipt["schema"] == "native-capability-inspection-receipt/v1"
    assert receipt["status"] == "inspected"
    assert receipt["capability"] == {"kind": kind, "id": capability_id}
    assert receipt["source_schema"] == source_schema
    assert receipt["proof"]["strength"] == "strong"
    assert receipt["source_ref"] and not Path(receipt["source_ref"]).is_absolute()
    assert receipt["source_digest"].startswith("sha256:")
    assert receipt["receipt_digest"].startswith("sha256:")
    assert receipt["admission"] == {"evaluated": False, "decision": "not_evaluated"}
    assert receipt["authorization"] == {"evaluated": False, "decision": "not_evaluated"}
    assert receipt["evidence"] == {"recorded": False, "status": "not_evaluated"}
    assert receipt["verification"] == {"performed": False, "status": "not_evaluated"}
    assert all(receipt[field] is expected for field, expected in {
        "read_only": True,
        "executed": False,
        "provider_called": False,
        "invoked": False,
        "value_indicator_policy": False,
    }.items())


def test_skill_and_workflow_explicitly_mark_projection_resolution_not_applicable(authority_root: Path) -> None:
    registry = _registry()
    for capability_id in ("skill:demo", "workflow:demo"):
        receipt = inspect_native_capability(
            root=authority_root,
            capability_id=capability_id,
            registry=registry,
            registry_content=_registry_bytes(registry),
            binding=_binding(),
        )
        assert receipt["upstream_resolution"] == {
            "status": "not_applicable",
            "reason": "native_kind_not_in_projection",
        }


def test_skill_id_may_contain_colon_after_selector_prefix(authority_root: Path) -> None:
    skill = authority_root / ".agents/skills/workflow:mini/SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("---\nname: workflow:mini\ndescription: namespaced skill\n---\nbody\n", encoding="utf-8")
    receipt = inspect_native_capability(
        root=authority_root,
        capability_id="skill:workflow:mini",
        registry={},
        registry_content=b"",
        binding=_binding(),
    )
    assert receipt["source_ref"] == ".agents/skills/workflow:mini/SKILL.md"


def test_mcp_server_static_declaration_is_provable(authority_root: Path) -> None:
    registry = _registry()
    capability_id = "mcp-server:demo"
    receipt = inspect_native_capability(
        root=authority_root,
        capability_id=capability_id,
        registry=registry,
        registry_content=_registry_bytes(registry),
        resolution_receipt=_resolution_receipt(registry, capability_id),
    )
    assert receipt["capability"]["kind"] == "mcp_server"


def test_mcp_explicit_literal_version_is_proved(authority_root: Path) -> None:
    registry = _registry()
    (authority_root / "native/demo_mcp.py").write_text(
        "from fastmcp import FastMCP\n"
        "mcp = FastMCP('demo', version='1.0.0')\n"
        "@mcp.tool()\n"
        "async def inspect_item(value: str) -> str:\n"
        "    return value\n",
        encoding="utf-8",
    )
    receipt = inspect_native_capability(
        root=authority_root,
        capability_id="mcp-server:demo",
        registry=registry,
        registry_content=_registry_bytes(registry),
        resolution_receipt=_resolution_receipt(registry, "mcp-server:demo"),
    )
    assert receipt["native_version"] == "1.0.0"
    assert receipt["native_version_status"] == "proved"


def test_mcp_dynamic_version_remains_unprovable(authority_root: Path) -> None:
    registry = _registry()
    (authority_root / "native/demo_mcp.py").write_text(
        "from fastmcp import FastMCP\n"
        "VERSION = '1.0.0'\n"
        "mcp = FastMCP('demo', version=VERSION)\n"
        "@mcp.tool()\n"
        "async def inspect_item(value: str) -> str:\n"
        "    return value\n",
        encoding="utf-8",
    )
    receipt = inspect_native_capability(
        root=authority_root,
        capability_id="mcp-server:demo",
        registry=registry,
        registry_content=_registry_bytes(registry),
        resolution_receipt=_resolution_receipt(registry, "mcp-server:demo"),
    )
    assert receipt["native_version"] is None
    assert receipt["native_version_status"] == "unprovable"


@pytest.mark.parametrize(
    ("source", "failure"),
    [
        (
            "from fastmcp import FastMCP\n"
            "mcp = FastMCP('wrong-id')\n"
            "@mcp.tool()\nasync def inspect_item():\n    return 'x'\n",
            "source_unprovable",
        ),
        (
            "class FastMCP:\n"
            "    def __init__(self, name): pass\n"
            "mcp = FastMCP('demo')\n"
            "@mcp.tool()\nasync def inspect_item():\n    return 'x'\n",
            "source_unprovable",
        ),
        (
            "from fastmcp import FastMCP\n"
            "mcp = FastMCP('demo')\nother = FastMCP('demo')\n"
            "@mcp.tool()\nasync def inspect_item():\n    return 'x'\n",
            "duplicate_authority_claim",
        ),
        (
            "from fastmcp import FastMCP\n"
            "name = 'demo'\nmcp = FastMCP(name)\n"
            "@mcp.tool()\nasync def inspect_item():\n    return 'x'\n",
            "source_unprovable",
        ),
        (
            "from fastmcp import FastMCP\n"
            "from local_fake import FastMCP\n"
            "mcp = FastMCP('demo')\n"
            "@mcp.tool()\nasync def inspect_item():\n    return 'x'\n",
            "source_unprovable",
        ),
        (
            "try:\n"
            "    from fastmcp import FastMCP\n"
            "except ImportError:\n"
            "    from local_fake import FastMCP\n"
            "mcp = FastMCP('demo')\n"
            "@mcp.tool()\nasync def inspect_item():\n    return 'x'\n",
            "source_unprovable",
        ),
        (
            "from fastmcp import FastMCP\n"
            "try:\n"
            "    pass\n"
            "except Exception:\n"
            "    class FastMCP:\n        pass\n"
            "mcp = FastMCP('demo')\n"
            "@mcp.tool()\nasync def inspect_item():\n    return 'x'\n",
            "source_unprovable",
        ),
        (
            "from fastmcp import FastMCP\n"
            "globals()['FastMCP'] = object\n"
            "mcp = FastMCP('demo')\n"
            "@mcp.tool()\nasync def inspect_item():\n    return 'x'\n",
            "source_unprovable",
        ),
        (
            "from fastmcp import FastMCP\n"
            "import current_module\n"
            "setattr(current_module, 'FastMCP', object)\n"
            "mcp = FastMCP('demo')\n"
            "@mcp.tool()\nasync def inspect_item():\n    return 'x'\n",
            "source_unprovable",
        ),
    ],
)
def test_mcp_authority_requires_exact_import_single_binding_and_literal_native_id(
    authority_root: Path, source: str, failure: str
) -> None:
    registry = _registry()
    (authority_root / "native/demo_mcp.py").write_text(source, encoding="utf-8")
    with pytest.raises(NativeInspectionError, match=failure):
        inspect_native_capability(
            root=authority_root,
            capability_id="mcp-server:demo",
            registry=registry,
            registry_content=_registry_bytes(registry),
            resolution_receipt=_resolution_receipt(registry, "mcp-server:demo"),
        )


def test_receipt_replay_accepts_exact_value_and_rejects_tampering(authority_root: Path) -> None:
    registry = _registry()
    receipt = inspect_native_capability(
        root=authority_root,
        capability_id="skill:demo",
        registry=registry,
        registry_content=_registry_bytes(registry),
        binding=_binding(),
    )
    assert validate_native_inspection_receipt(receipt) == receipt

    for field, value in (("executed", True), ("source_digest", "sha256:" + "0" * 64)):
        tampered = copy.deepcopy(receipt)
        tampered[field] = value
        with pytest.raises(NativeInspectionError):
            validate_native_inspection_receipt(tampered)


def test_mcp_and_bos_require_bound_resolution_receipt(authority_root: Path) -> None:
    registry = _registry()
    for capability_id in ("mcp-server:demo", "bos-service:bos://governance/demo"):
        with pytest.raises(NativeInspectionError, match="upstream_resolution_required"):
            inspect_native_capability(
                root=authority_root,
                capability_id=capability_id,
                registry=registry,
                registry_content=_registry_bytes(registry),
                binding=_binding(),
            )


def test_projection_digest_mismatch_fails_closed(authority_root: Path) -> None:
    registry = _registry()
    receipt = _resolution_receipt(registry, "mcp-server:demo")
    changed = copy.deepcopy(registry)
    changed["generated_at"] = "1970-01-02T00:00:00Z"
    with pytest.raises(NativeInspectionError, match="source_digest_mismatch"):
        inspect_native_capability(
            root=authority_root,
            capability_id="mcp-server:demo",
            registry=changed,
            registry_content=_registry_bytes(changed),
            resolution_receipt=receipt,
        )


def test_dynamic_mcp_registration_is_not_promoted_to_static_proof(authority_root: Path) -> None:
    registry = _registry()
    (authority_root / "native/demo_mcp.py").write_text(
        "from fastmcp import FastMCP\nmcp = FastMCP('demo')\nregister_tools(mcp)\n",
        encoding="utf-8",
    )
    with pytest.raises(NativeInspectionError, match="source_unprovable"):
        inspect_native_capability(
            root=authority_root,
            capability_id="mcp-tool:demo:inspect_item",
            registry=registry,
            registry_content=_registry_bytes(registry),
            resolution_receipt=_resolution_receipt(registry, "mcp-tool:demo:inspect_item"),
        )


def test_nested_mcp_declaration_is_not_misreported_as_module_authority(authority_root: Path) -> None:
    registry = _registry()
    (authority_root / "native/demo_mcp.py").write_text(
        "from fastmcp import FastMCP\n"
        "def make_server():\n"
        "    mcp = FastMCP('demo')\n"
        "    @mcp.tool()\n"
        "    async def inspect_item(value: str) -> str:\n"
        "        return value\n"
        "    return mcp\n",
        encoding="utf-8",
    )
    with pytest.raises(NativeInspectionError, match="source_unprovable"):
        inspect_native_capability(
            root=authority_root,
            capability_id="mcp-tool:demo:inspect_item",
            registry=registry,
            registry_content=_registry_bytes(registry),
            resolution_receipt=_resolution_receipt(registry, "mcp-tool:demo:inspect_item"),
        )


def test_bos_receipt_never_leaks_command_or_provider_fields(authority_root: Path) -> None:
    registry = _registry()
    receipt = inspect_native_capability(
        root=authority_root,
        capability_id="bos-service:bos://governance/demo",
        registry=registry,
        registry_content=_registry_bytes(registry),
        resolution_receipt=_resolution_receipt(registry, "bos-service:bos://governance/demo"),
    )
    encoded = json.dumps(receipt, sort_keys=True)
    assert "command" not in encoded
    assert "argv" not in encoded
    assert "secret-provider" not in encoded
    assert "SECRET" not in encoded
    assert str(authority_root) not in encoded


def test_safe_source_rejects_absolute_parent_and_symlink_escape(authority_root: Path, tmp_path: Path) -> None:
    outside = tmp_path.parent / "outside-native-proof.txt"
    outside.write_text("outside", encoding="utf-8")
    escape = authority_root / "native/escape.py"
    escape.symlink_to(outside)
    for source_ref in (str(outside), "../outside-native-proof.txt", "native/escape.py"):
        with pytest.raises(NativeInspectionError, match="dangling_reference"):
            _read_stable_source(authority_root, source_ref)


def test_source_race_is_detected(authority_root: Path) -> None:
    source_ref = "native/race.py"
    path = authority_root / source_ref
    path.write_text("before", encoding="utf-8")

    def mutate(target: Path) -> None:
        target.write_text("after-change", encoding="utf-8")

    with pytest.raises(NativeInspectionError, match="source_digest_mismatch"):
        _read_stable_source(authority_root, source_ref, after_read=mutate)


def test_same_size_same_mtime_source_mutation_is_detected(authority_root: Path) -> None:
    source_ref = "native/same-size.py"
    path = authority_root / source_ref
    path.write_text("before", encoding="utf-8")
    original = path.stat()

    def mutate(target: Path) -> None:
        target.write_text("after!", encoding="utf-8")
        os.utime(target, ns=(original.st_atime_ns, original.st_mtime_ns))

    with pytest.raises(NativeInspectionError, match="source_digest_mismatch"):
        _read_stable_source(authority_root, source_ref, after_read=mutate)


def test_replaced_final_entry_is_detected_even_with_same_metadata(authority_root: Path) -> None:
    source_ref = "native/replaced.py"
    path = authority_root / source_ref
    path.write_text("before", encoding="utf-8")
    original = path.stat()

    def replace(target: Path) -> None:
        replacement = target.with_suffix(".replacement")
        replacement.write_text("before", encoding="utf-8")
        os.utime(replacement, ns=(original.st_atime_ns, original.st_mtime_ns))
        replacement.replace(target)

    with pytest.raises(NativeInspectionError, match="source_digest_mismatch"):
        _read_stable_source(authority_root, source_ref, after_read=replace)


def test_symlink_parent_is_rejected_even_when_target_stays_inside_root(authority_root: Path) -> None:
    real = authority_root / "real-parent"
    real.mkdir()
    (real / "source.py").write_text("safe", encoding="utf-8")
    (authority_root / "linked-parent").symlink_to(real, target_is_directory=True)
    with pytest.raises(NativeInspectionError, match="dangling_reference"):
        _read_stable_source(authority_root, "linked-parent/source.py")


def test_workflow_id_must_be_unique_across_canonical_directory(authority_root: Path) -> None:
    duplicate = authority_root / ".omo/_truth/registry/agent-workflows/workflows/other.yaml"
    duplicate.write_text("id: demo\ntitle: duplicate\n", encoding="utf-8")
    with pytest.raises(NativeInspectionError, match="duplicate_authority_claim"):
        inspect_native_capability(
            root=authority_root,
            capability_id="workflow:demo",
            registry={},
            registry_content=b"",
            binding=_binding(),
        )


def test_unreadable_competing_workflow_fails_closed(authority_root: Path) -> None:
    competing = authority_root / ".omo/_truth/registry/agent-workflows/workflows/unreadable.yaml"
    competing.write_text("id: [broken\n", encoding="utf-8")
    with pytest.raises(NativeInspectionError, match="source_unprovable"):
        inspect_native_capability(
            root=authority_root,
            capability_id="workflow:demo",
            registry={},
            registry_content=b"",
            binding=_binding(),
        )


def test_workflow_full_snapshot_detects_content_race(
    authority_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original_snapshot = native_inspection._workflow_snapshot
    calls = 0

    def racing_snapshot(root: Path, source_ref: str):
        nonlocal calls
        snapshot = original_snapshot(root, source_ref)
        calls += 1
        if calls == 1:
            target = root / source_ref / "demo.yaml"
            target.write_text("id: demo\ntitle: changed during validation\n", encoding="utf-8")
        return snapshot

    monkeypatch.setattr(native_inspection, "_workflow_snapshot", racing_snapshot)
    with pytest.raises(NativeInspectionError, match="source_digest_mismatch"):
        inspect_native_capability(
            root=authority_root,
            capability_id="workflow:demo",
            registry={},
            registry_content=b"",
            binding=_binding(),
        )


def _rehash(receipt: dict) -> dict:
    tampered = copy.deepcopy(receipt)
    tampered.pop("receipt_digest", None)
    tampered["receipt_digest"] = _digest(_canonical_json(tampered))
    return tampered


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("source_schema", "attacker-schema/v1"),
        ("proof", {"method": "attacker_method", "strength": "strong"}),
        ("source_ref", ".agents/skills/other/SKILL.md"),
        ("native_version", "bad\nversion"),
    ],
)
def test_recomputed_hash_cannot_bypass_kind_or_version_semantics(
    authority_root: Path, field: str, value: object
) -> None:
    receipt = inspect_native_capability(
        root=authority_root,
        capability_id="skill:demo",
        registry={},
        registry_content=b"",
        binding=_binding(),
    )
    tampered = copy.deepcopy(receipt)
    tampered[field] = value
    if field == "native_version":
        tampered["native_version_status"] = "proved"
    with pytest.raises(NativeInspectionError):
        validate_native_inspection_receipt(_rehash(tampered))


def test_recomputed_hash_cannot_bypass_upstream_digest_format(authority_root: Path) -> None:
    registry = _registry()
    receipt = inspect_native_capability(
        root=authority_root,
        capability_id="mcp-server:demo",
        registry=registry,
        registry_content=_registry_bytes(registry),
        resolution_receipt=_resolution_receipt(registry, "mcp-server:demo"),
    )
    receipt["upstream_resolution"]["receipt_digest"] = "not-a-sha256"
    with pytest.raises(NativeInspectionError):
        validate_native_inspection_receipt(_rehash(receipt))


def test_library_has_no_provider_import_process_or_socket_surface() -> None:
    imported = set()
    for path in (LIB_PATH, SOURCES_PATH, RECEIPT_PATH):
        tree = ast.parse(path.read_text(encoding="utf-8"), feature_version=(3, 9))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".", 1)[0])
    assert imported.isdisjoint({"importlib", "subprocess", "socket", "agora"})
    assert "_load_native_gateway" not in LIB_PATH.read_text(encoding="utf-8")


def test_python39_grammar_for_native_inspector() -> None:
    for path in (LIB_PATH, SOURCES_PATH, RECEIPT_PATH, SYNC_PATH, Path(__file__)):
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path), feature_version=(3, 9))
