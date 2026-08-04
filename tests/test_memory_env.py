"""Memory OS env loader (Phase 8)."""

from __future__ import annotations

import os

from cockpit.web.memory_env import apply_memory_os_env, mos_subprocess_env, mos_uv_extra_args


def test_apply_memory_os_env_sets_defaults(monkeypatch, tmp_path):
    for k in list(os.environ):
        if k.startswith("NEO4J_") or k.startswith("MOS_"):
            monkeypatch.delenv(k, raising=False)
    # force re-apply
    import cockpit.web.memory_env as me

    me._APPLIED = False
    applied = apply_memory_os_env(root=tmp_path, force=True)
    # with empty root, still gets code defaults
    assert applied.get("NEO4J_URI") == "bolt://localhost:7687"
    assert os.environ.get("MOS_RBAC") == "1"


def test_apply_does_not_overwrite_existing(monkeypatch, tmp_path):
    monkeypatch.setenv("NEO4J_URI", "bolt://custom:9999")
    import cockpit.web.memory_env as me

    me._APPLIED = False
    applied = apply_memory_os_env(root=tmp_path, force=True)
    assert applied["NEO4J_URI"] == "bolt://custom:9999"


def test_mos_uv_extra_when_uri(monkeypatch):
    monkeypatch.setenv("NEO4J_URI", "bolt://localhost:7687")
    import cockpit.web.memory_env as me

    me._APPLIED = False
    apply_memory_os_env(force=True)
    assert mos_uv_extra_args() == ["--with", "neo4j"]
    env = mos_subprocess_env()
    assert env.get("MOS_STDIO") == "1"
