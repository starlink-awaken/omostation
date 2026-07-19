"""Drive collab_cli + emergence_cli real entry points."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DELIVERY = ROOT / "bin" / "delivery"
COLLAB = DELIVERY / "collab_cli.py"
EMERG = DELIVERY / "emergence_cli.py"


def _run(script: Path, args: list[str], *, env: dict | None = None) -> subprocess.CompletedProcess[str]:
    e = os.environ.copy()
    if env:
        e.update(env)
    return subprocess.run(
        [sys.executable, str(script), *args],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
        env=e,
    )


def test_collab_handshake_and_handoff_link(tmp_path: Path):
    hist = tmp_path / "collab"
    ctx = tmp_path / "ctx"
    r = _run(COLLAB, ["--history-root", str(hist), "run-handshake"])
    assert r.returncode == 0, r.stderr
    data = json.loads(r.stdout)
    assert data["ok"] is True
    task = data["task_ref"]
    h = _run(COLLAB, ["--history-root", str(hist), "history", "--task-ref", task])
    assert h.returncode == 0
    assert json.loads(h.stdout)["n"] >= 1
    link = _run(
        COLLAB,
        [
            "--history-root",
            str(hist),
            "handoff-link",
            "--task-ref",
            task,
            "--writer",
            "orch-1",
            "--scope",
            "bet",
            "--context-root",
            str(ctx),
        ],
    )
    assert link.returncode == 0, link.stderr
    assert json.loads(link.stdout)["ok"] is True
    # file exists
    assert any(ctx.rglob("*.json"))


def test_emergence_status_and_kill_file(tmp_path: Path, monkeypatch):
    # point kill dir via cwd is fixed to ROOT — use env and real path under delivery delivery test isolation
    # Use measure which doesn't need kill file
    st = _run(EMERG, ["status"])
    assert st.returncode == 0
    body = json.loads(st.stdout)
    assert "ECOS_EMERGENCE_ENABLED" in body
    assert body["allow_run"] is False or body["ECOS_EMERGENCE_ENABLED"] in ("0", "1")

    # force detect when enabled
    d = _run(
        EMERG,
        ["detect", "--text", "swarm consensus multi-agent vote", "--force-enable"],
    )
    assert d.returncode == 0
    assert json.loads(d.stdout)["emergent"] is True

    k = _run(EMERG, ["kill"])
    assert k.returncode == 0
    assert json.loads(k.stdout)["session_killed"] is True
    d2 = _run(
        EMERG,
        ["detect", "--text", "swarm consensus multi-agent vote", "--force-enable"],
    )
    assert d2.returncode == 0
    body2 = json.loads(d2.stdout)
    assert body2["session_killed"] is True
    assert body2["emergent"] is False  # killed blocks detect
    _run(EMERG, ["clear-kill"])


def test_emergence_measure_green():
    r = _run(EMERG, ["measure"], env={"ECOS_EMERGENCE_ENABLED": "1"})
    assert r.returncode == 0, r.stderr + r.stdout
    data = json.loads(r.stdout)
    assert data["meets_gate"] is True
    assert data["accuracy"] > 0.80
