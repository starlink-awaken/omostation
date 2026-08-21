"""reload_daemon() must reflect whether config.toml on disk actually changed.

Regression coverage for the 2026-08-22 finding: the endpoint used to always
report status="reloaded" using stale in-memory counts, regardless of whether
it had re-read anything from disk. See docs/operations/2026-08-22-*.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from omlxc.config import load_config
from omlxc.daemon import build_production_daemon

_MINIMAL_TOML = """
schema_version = 1

[daemon]
socket_path = "{root}/omlxcd.sock"

[storage]
database_path = "{root}/state.db"

[[nodes]]
id = "node"
display_name = "Node"
platform = "macos"
memory_gb = 16

[[backends]]
id = "backend"
node_id = "node"
kind = "omlx_app"
base_url = "http://127.0.0.1:8000"

[[models]]
id = "local/model"
category = "llm"
role = "chat"
engine = "omlx"

[[placements]]
id = "placement"
model_id = "local/model"
backend_id = "backend"
backend_model_id = "model-0"
context_limit = 8192
memory_gb = 2
"""


def _write_toml(path: Path, *, root: Path, extra_model: bool = False) -> None:
    content = _MINIMAL_TOML.format(root=root)
    if extra_model:
        content += """
[[models]]
id = "local/second"
category = "llm"
role = "chat"
engine = "omlx"
"""
    path.write_text(content, encoding="utf-8")


@pytest.mark.asyncio
async def test_reload_reports_reloaded_when_disk_matches_loaded(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    _write_toml(config_path, root=tmp_path)
    loaded = load_config(config_path, base_directory=tmp_path)
    composition = build_production_daemon(loaded, adapters={}, config_path=config_path)
    try:
        result = await composition.control.reload_daemon()
    finally:
        await composition.runtime.close()
    assert result["status"] == "reloaded"
    assert "no restart needed" in str(result["note"])


@pytest.mark.asyncio
async def test_reload_reports_stale_when_disk_changed(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    _write_toml(config_path, root=tmp_path)
    loaded = load_config(config_path, base_directory=tmp_path)
    composition = build_production_daemon(loaded, adapters={}, config_path=config_path)
    try:
        _write_toml(config_path, root=tmp_path, extra_model=True)
        result = await composition.control.reload_daemon()
    finally:
        await composition.runtime.close()
    assert result["status"] == "stale"
    assert "daemon restart" in str(result["note"])
    # in-memory counts must still reflect what's actually loaded, not the new file
    assert result["models_count"] == 1


@pytest.mark.asyncio
async def test_reload_falls_back_to_default_path_when_none_given(tmp_path: Path) -> None:
    """config_path=None (existing call sites) must not raise; behaves like before."""
    config_path = tmp_path / "config.toml"
    _write_toml(config_path, root=tmp_path)
    loaded = load_config(config_path, base_directory=tmp_path)
    composition = build_production_daemon(loaded, adapters={})
    try:
        result = await composition.control.reload_daemon()
    finally:
        await composition.runtime.close()
    assert result["status"] in {"reloaded", "stale"}
    assert result["nodes_count"] == 1
