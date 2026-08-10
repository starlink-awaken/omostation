"""omlxc control-plane unit tests (no live model server required)."""

from __future__ import annotations

import importlib.machinery
import importlib.util
from pathlib import Path


def _load_cli():
    path = Path(__file__).parents[1] / "bin" / "omlx"
    loader = importlib.machinery.SourceFileLoader("omlxc_cli", str(path))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def test_app_projection_is_flat_idempotent_and_only_cleans_managed_links(tmp_path, monkeypatch):
    cli = _load_cli()
    active = tmp_path / "active"
    real = tmp_path / "weights" / "model-a"
    real.mkdir(parents=True)
    alias_dir = active / "coding"
    alias_dir.mkdir(parents=True)
    (alias_dir / "current").symlink_to(real)
    projection = tmp_path / "app-models"
    config = {
        "active_root": str(active),
        "models": {"coding": {"alias": "coding/current"}},
        "omlx_app": {"model_dir": str(projection), "base_url": "http://127.0.0.1:8000"},
    }
    monkeypatch.setattr(cli, "_app_reload", lambda _conf: {"status": "ok"})

    preview = cli._app_sync(config, apply=False)
    assert preview["changed"] == [("coding", str(real))]
    result = cli._app_sync(config, apply=True)
    assert result["reload"] == {"status": "ok"}
    assert (projection / "coding").is_symlink()
    assert (projection / "coding").resolve() == real
    assert cli._app_sync(config, apply=False)["changed"] == []

    unmanaged = projection / "keep-me"
    unmanaged.write_text("user data")
    config["models"] = {}
    cli._app_sync(config, apply=True)
    assert not (projection / "coding").exists()
    assert unmanaged.read_text() == "user data"


def test_reranker_capability_wins_over_bge_name():
    cli = _load_cli()
    assert cli._infer_caps("baai-bge-reranker-v2-m3", "x", {"models": {}}) == ["rerank"]


def test_app_mode_is_explicit_engine_policy():
    cli = _load_cli()
    assert cli._app_enabled({"engine_policy": {"nodes": {"mbp": {"primary": "omlx_app"}}}})
    assert not cli._app_enabled({"engine_policy": {"nodes": {"mbp": {"primary": "omlx"}}}})
