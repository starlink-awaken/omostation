"""Agora StdioAdapter contract: stdin JSON {args, kwargs} → stdout JSON."""

from __future__ import annotations

import io
import json
import subprocess
import sys
from pathlib import Path

from mos.cli import main


def test_stdio_write_via_stdin_json(monkeypatch, tmp_path, capsys):
    store = tmp_path / "store.json"
    monkeypatch.setenv("MOS_STORE_PATH", str(store))
    monkeypatch.setenv("MOS_STDIO", "1")
    payload = json.dumps(
        {
            "args": [],
            "kwargs": {
                "type": "semantic",
                "content": "stdio path prefers green tea",
                "confidence": 0.9,
            },
        }
    )
    monkeypatch.setattr(sys, "stdin", io.StringIO(payload))
    # isatty False on StringIO by default in some versions — force
    monkeypatch.setattr(sys.stdin, "isatty", lambda: False)

    rc = main(["write"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["ok"] is True
    assert out["raw_ok"] is True
    assert out["theta_ok"] is True


def test_stdio_recall_via_stdin_json(monkeypatch, tmp_path, capsys):
    store = tmp_path / "store.json"
    monkeypatch.setenv("MOS_STORE_PATH", str(store))
    monkeypatch.setenv("MOS_STDIO", "1")
    # seed
    monkeypatch.setattr(
        sys,
        "stdin",
        io.StringIO(
            json.dumps(
                {
                    "args": [],
                    "kwargs": {"type": "semantic", "content": "stdio green tea preference", "confidence": 0.95},
                }
            )
        ),
    )
    monkeypatch.setattr(sys.stdin, "isatty", lambda: False)
    assert main(["write"]) == 0
    capsys.readouterr()

    monkeypatch.setattr(
        sys,
        "stdin",
        io.StringIO(
            json.dumps(
                {
                    "args": [],
                    "kwargs": {"query": "green tea preference", "intent": "preference_self", "limit": 5},
                }
            )
        ),
    )
    monkeypatch.setattr(sys.stdin, "isatty", lambda: False)
    assert main(["recall"]) == 0
    recall = json.loads(capsys.readouterr().out)
    assert recall["count"] >= 1
    assert recall["empty"] is False


def test_subprocess_stdio_matches_agora_adapter(tmp_path, monkeypatch):
    """Spawn real process like StdioAdapter: communicate(input=json)."""
    store = tmp_path / "subproc-store.json"
    env = {
        **{k: v for k, v in __import__("os").environ.items()},
        "MOS_STORE_PATH": str(store),
        "MOS_STDIO": "1",
        "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src"),
    }
    # Use python -m mos from package source (mirrors Agora transport=stdio)
    cmd = [sys.executable, "-m", "mos", "write"]
    req = json.dumps({"args": [], "kwargs": {"type": "episodic", "content": "subprocess dual-track note"}})
    proc = subprocess.run(
        cmd,
        input=req,
        text=True,
        capture_output=True,
        env=env,
        timeout=15,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    data = json.loads(proc.stdout.strip().splitlines()[-1])
    assert data["ok"] is True
    assert data["theta_ok"] is True

    req2 = json.dumps({"args": [], "kwargs": {"query": "dual-track note", "intent": "general"}})
    proc2 = subprocess.run(
        [sys.executable, "-m", "mos", "recall"],
        input=req2,
        text=True,
        capture_output=True,
        env=env,
        timeout=15,
        check=False,
    )
    assert proc2.returncode == 0, proc2.stderr
    recall = json.loads(proc2.stdout.strip().splitlines()[-1])
    assert recall["count"] >= 1
