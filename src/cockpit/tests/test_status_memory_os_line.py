"""Workbench Memory OS health line uses real _invoke_mos path (mocked)."""

from __future__ import annotations

from cockpit.commands import status as status_mod


def test_memory_os_workbench_line_ready(monkeypatch):
    monkeypatch.setattr(
        status_mod,
        "_invoke_mos" if hasattr(status_mod, "_invoke_mos") else "x",
        lambda *a, **k: {},
        raising=False,
    )

    def fake_invoke(cmd, kwargs=None, **kw):
        assert cmd == "status"
        return {
            "ok": True,
            "version": "0.10.0",
            "neo4j_configured": True,
            "neo4j_available": True,
            "neo4j_recall": True,
            "neo4j_as_of": True,
        }

    # Patch the memory module import target used inside the helper
    import cockpit.commands.memory as mem

    monkeypatch.setattr(mem, "_invoke_mos", fake_invoke)
    line = status_mod._memory_os_workbench_line()
    assert "Memory OS" in line
    assert "0.10.0" in line
    assert "neo4j ready" in line
    assert "as_of=True" in line


def test_memory_os_workbench_line_degraded(monkeypatch):
    import cockpit.commands.memory as mem

    monkeypatch.setattr(mem, "_invoke_mos", lambda *a, **k: {"ok": False, "error": "timeout"})
    line = status_mod._memory_os_workbench_line()
    assert "Memory OS" in line
    assert "degraded" in line or "timeout" in line
