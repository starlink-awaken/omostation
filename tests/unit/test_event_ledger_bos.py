"""W1-04 Event Ledger BOS — declaration & integration tests."""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

import pytest
import yaml

# Workspace root: tests/unit/ → project/ → projects/ → workspace/
WORKSPACE_ROOT = Path(__file__).resolve().parents[4]


@pytest.fixture(autouse=True)
def _workspace_cwd(monkeypatch):
    monkeypatch.chdir(WORKSPACE_ROOT)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

BOS_YAML = WORKSPACE_ROOT / "projects/agora/etc/bos-services.yaml"

LEDGER_URIS = {
    "append": "bos://governance/omo/ledger-append",
    "read": "bos://governance/omo/ledger-read",
    "verify": "bos://governance/omo/ledger-verify",
    "status": "bos://governance/omo/ledger-status",
}


def _load_services():
    return yaml.safe_load(BOS_YAML.read_text(encoding="utf-8"))["services"]


def _ledger_services():
    return [s for s in _load_services() if s["uri"] in LEDGER_URIS.values()]


def _service_by_action(action):
    uri = LEDGER_URIS[action]
    return next(s for s in _load_services() if s["uri"] == uri)


# ---------------------------------------------------------------------------
# Registry schema
# ---------------------------------------------------------------------------


def test_all_4_uris_exist():
    found = {s["uri"] for s in _ledger_services()}
    for uri in LEDGER_URIS.values():
        assert uri in found, f"missing {uri}"


def test_no_duplicates():
    uris = [s["uri"] for s in _ledger_services()]
    assert len(uris) == len(set(uris)) == 4


@pytest.mark.parametrize("action", ["append", "read", "verify", "status"])
def test_transport_and_command_shape(action):
    svc = _service_by_action(action)
    assert svc["transport"] == "stdio"
    assert svc["domain"] == "governance"
    assert svc["package"] == "omo"
    cmd = svc["command"]
    assert cmd[2] == "--frozen", f"{action}: missing --frozen"
    assert cmd[:9] == [
        "uv",
        "run",
        "--frozen",
        "--directory",
        "projects/omo",
        "python",
        "-m",
        "omo.cli",
        "ledger",
    ]
    assert cmd[9] == action
    assert cmd[10] == "--agora"
    assert len(cmd) == 11


def test_all_ledger_commands_have_frozen():
    for s in _ledger_services():
        assert s["command"][2] == "--frozen", f"{s['uri']}: missing --frozen"


def test_required_fields():
    required = {
        "action",
        "command",
        "description",
        "domain",
        "package",
        "status",
        "transport",
        "uri",
    }
    for s in _ledger_services():
        assert not (required - set(s.keys())), f"{s['uri']}: missing fields"


def test_yaml_parsable():
    _load_services()


# ---------------------------------------------------------------------------
# Integration: invoke_stdio
# ---------------------------------------------------------------------------


def test_append_read_verify_roundtrip(tmp_path):
    from agora.mcp.resolver.api import invoke_stdio

    db = str(tmp_path / "ledger.db")

    r = invoke_stdio(
        LEDGER_URIS["append"],
        db=db,
        event_type="TestEvent.v1",
        producer="bos-test",
        payload={"msg": "hello from BOS"},
    )
    assert r["status"] == "ok", r
    assert r["result"]["ok"] is True
    assert r["result"]["sequence"] == 1

    r2 = invoke_stdio(LEDGER_URIS["read"], db=db)
    assert r2["status"] == "ok"
    assert r2["result"]["count"] == 1
    assert r2["result"]["events"][0]["producer"] == "bos-test"

    r3 = invoke_stdio(LEDGER_URIS["verify"], db=db)
    assert r3["status"] == "ok"
    assert r3["result"]["ok"] is True


def test_status_report(tmp_path):
    from agora.mcp.resolver.api import invoke_stdio

    r = invoke_stdio(LEDGER_URIS["status"], db=str(tmp_path / "status.db"))
    assert r["status"] == "ok"
    assert "count" in r["result"]


def test_duplicate_write_fails(tmp_path):
    from agora.mcp.resolver.api import invoke_stdio

    db = str(tmp_path / "dup.db")
    kwargs = {"db": db, "producer": "dp", "idempotency_key": "k1", "payload": {"a": 1}}
    assert invoke_stdio(LEDGER_URIS["append"], **kwargs)["status"] == "ok"
    r2 = invoke_stdio(LEDGER_URIS["append"], **kwargs)
    assert r2["status"] == "error"
    assert "duplicate" in r2["error"].lower()


def test_malformed_payload_fails(tmp_path):
    from agora.mcp.resolver.api import invoke_stdio

    db = str(tmp_path / "bad.db")
    r = invoke_stdio(LEDGER_URIS["append"], db=db, producer="bp", payload="not json")
    assert r["status"] == "error"


# ---------------------------------------------------------------------------
# No persistence in Agora source
# ---------------------------------------------------------------------------


def test_agora_has_no_ledger_broker_import():
    import ast

    agora_root = WORKSPACE_ROOT / "projects/agora/src/agora"
    for py in agora_root.rglob("*.py"):
        tree = ast.parse(py.read_text(encoding="utf-8", errors="replace"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                assert "omo.event_ledger" not in node.module, (
                    f"{py}: imports {node.module}"
                )
            if isinstance(node, ast.Import):
                for a in node.names:
                    assert "LedgerBroker" not in a.name, f"{py}: imports {a.name}"


# ---------------------------------------------------------------------------
# Async resolve_bos_uri
# ---------------------------------------------------------------------------


def test_async_resolve_ledger_status():
    from agora.mcp.resolver.api import resolve_bos_uri

    async def _run():
        with tempfile.TemporaryDirectory() as td:
            return await resolve_bos_uri(
                LEDGER_URIS["status"], db=str(Path(td) / "async.db")
            )

    result = asyncio.run(_run())
    assert result["status"] == "ok"
    assert result["result"]["ok"] is True
