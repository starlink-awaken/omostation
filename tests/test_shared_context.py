"""G-DEL.4 shared context store + CLI + measure — real entry points."""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DELIVERY = ROOT / "bin" / "delivery"
CLI = DELIVERY / "shared-context-cli.py"


def _load(name: str):
    path = DELIVERY / f"{name}.py"
    mod_name = f"delivery_{name}"
    spec = importlib.util.spec_from_file_location(mod_name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader
    sys.path.insert(0, str(DELIVERY))
    sys.modules[mod_name] = mod
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_file_store_visibility_and_isolation(tmp_path: Path):
    mod = _load("shared_context_store")
    store = mod.FileSharedContextStore(tmp_path / "sc")
    store.write("agent-A", "public.key", "hello", scope="s1")
    store.write("agent-A", "private.key", "secret", scope="s1", readers=["agent-A"])
    assert store.read("agent-B", "public.key", scope="s1").value == "hello"
    assert store.read("agent-B", "private.key", scope="s1") is None
    assert store.read("agent-A", "private.key", scope="s1").value == "secret"
    vis = store.list_visible("agent-B", scope="s1")
    assert len(vis) == 1
    assert vis[0].key == "public.key"


def test_cli_cross_process_and_kos(tmp_path: Path):
    root = tmp_path / "sc"
    db = tmp_path / "kos.sqlite"
    w = subprocess.run(
        [
            sys.executable,
            str(CLI),
            "--root",
            str(root),
            "write",
            "--writer",
            "agent-A",
            "--key",
            "collab.handoff",
            "--value",
            "ready",
            "--scope",
            "bet",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert w.returncode == 0, w.stderr
    r = subprocess.run(
        [
            sys.executable,
            str(CLI),
            "--root",
            str(root),
            "read",
            "--reader",
            "agent-B",
            "--key",
            "collab.handoff",
            "--scope",
            "bet",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert r.returncode == 0, r.stderr
    data = json.loads(r.stdout)
    assert data["record"]["value"] == "ready"
    ex = subprocess.run(
        [
            sys.executable,
            str(CLI),
            "--root",
            str(root),
            "export-kos",
            "--scope",
            "bet",
            "--db",
            str(db),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert ex.returncode == 0, ex.stderr
    ret = subprocess.run(
        [
            sys.executable,
            str(CLI),
            "retrieve-kos",
            "--query",
            "collab.handoff",
            "--db",
            str(db),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert ret.returncode == 0
    hits = json.loads(ret.stdout)
    assert hits["n"] >= 1
    assert "shared-context" in hits["hits"][0]["path"]


def test_measure_role_memory_includes_cross_process():
    mem = _load("role_memory")
    m = mem.measure_role_memory_share()
    assert m["meets_gate"] is True
    assert m["cross_process"]["ok"] is True
    assert m["cross_process"]["kos_retrieve_ok"] is True
    assert m["caliber"] == "single_repo_gbrain"
    assert "callchain" in m
