"""omlxc control-plane unit tests (no live model server required)."""

from __future__ import annotations

import importlib.machinery
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest


def _load_cli():
    path = Path(__file__).parents[1] / "bin" / "omlx"
    loader = importlib.machinery.SourceFileLoader("omlxc_cli", str(path))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def _load_models_config():
    path = Path(__file__).parents[1] / "conf" / "models.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_model_memory_admission_values_cover_measured_large_models():
    models = _load_models_config()["models"]

    assert all(float(model["size_gb"]) > 0 for model in models.values())
    assert models["coding"]["size_gb"] >= 24
    assert models["coding-fast"]["size_gb"] >= 28
    assert models["coding-next"]["size_gb"] >= 52
    assert models["reasoning"]["size_gb"] >= 30
    assert models["mistral-medium-128b"]["size_gb"] >= 74


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


def test_benchmark_payload_forces_non_thinking_without_mutating_defaults():
    cli = _load_cli()
    defaults = {
        "chat_template_kwargs": {"enable_thinking": False},
        "thinking_budget": 0,
    }
    config = {
        "omlx_app": {"request_defaults": defaults},
        "models": {"coding": {"params": {"temp": 0.1}}},
    }

    payload = cli._benchmark_payload(config, "coding", "probe", 128)

    assert payload["model"] == "coding"
    assert payload["max_tokens"] == 128
    assert payload["temperature"] == 0
    assert payload["chat_template_kwargs"] == {"enable_thinking": False}
    assert payload["thinking_budget"] == 0
    assert defaults == {
        "chat_template_kwargs": {"enable_thinking": False},
        "thinking_budget": 0,
    }


def test_benchmark_request_uses_embeddings_endpoint_for_embedding_models():
    cli = _load_cli()
    config = {"models": {"embedding": {"role": "embedding"}}, "omlx_app": {}}

    path, payload = cli._benchmark_request(config, "embedding", "probe", 128)

    assert path == "/v1/embeddings"
    assert payload == {"model": "embedding", "input": "probe"}


def test_parse_footprint_bytes_accepts_macos_units():
    cli = _load_cli()
    assert cli._parse_footprint_bytes("python [1] Footprint: 4760 MB") == 4760 * 1024**2
    assert cli._parse_footprint_bytes("Footprint: 4.5 GB") == int(4.5 * 1024**3)
    assert cli._parse_footprint_bytes("no footprint here") is None


def test_benchmark_growth_flags_sustained_growth_but_allows_plateau():
    cli = _load_cli()
    gb = 1024**3
    assert cli._benchmark_growth_verdict([5 * gb, 5.1 * gb, 5.15 * gb], 512 * 1024**2)[0]
    assert cli._benchmark_growth_verdict([34 * gb, 35 * gb, 35 * gb, 35 * gb], 768 * 1024**2)[0]
    ok, message = cli._benchmark_growth_verdict(
        [5 * gb, 5.3 * gb, 5.7 * gb, 6.1 * gb],
        512 * 1024**2,
    )
    assert not ok
    assert "增长" in message


def test_benchmark_safety_stops_before_low_memory_or_hard_limit():
    cli = _load_cli()
    gb = 1024**3
    assert cli._benchmark_safety(30, 5 * gb, 95 * gb, 20)[0]
    ok, reason = cli._benchmark_safety(19, 5 * gb, 95 * gb, 20)
    assert not ok
    assert "可用内存" in reason
    ok, reason = cli._benchmark_safety(30, 91 * gb, 95 * gb, 20)
    assert not ok
    assert "硬上限" in reason


def test_benchmark_detects_reasoning_fields_and_think_tags():
    cli = _load_cli()
    assert not cli._message_has_thinking({"content": "OK"})
    assert cli._message_has_thinking({"content": "OK", "reasoning": "secret"})
    assert cli._message_has_thinking({"content": "<think>secret</think>OK"})


def test_main_exposes_memory_guarded_benchmark_command(monkeypatch):
    cli = _load_cli()
    called = []
    monkeypatch.setattr(cli, "load_conf", lambda: {"models": {"mythos-fast": {}}})
    monkeypatch.setattr(cli, "cmd_bench", lambda _conf, args: called.append(args))
    monkeypatch.setattr(
        cli.sys,
        "argv",
        [
            "omlxc",
            "bench",
            "mythos-fast",
            "--iterations",
            "3",
            "--max-growth-mb",
            "256",
        ],
    )

    cli.main()

    assert len(called) == 1
    assert called[0].model == "mythos-fast"
    assert called[0].iterations == 3
    assert called[0].max_growth_mb == 256


def test_benchmark_refuses_to_jit_load_an_unloaded_model(monkeypatch):
    cli = _load_cli()
    monkeypatch.setattr(cli, "_app_models", lambda _conf: {"mythos-fast": {"loaded": False}})
    requested = []
    monkeypatch.setattr(cli, "_http_json", lambda *a, **k: requested.append((a, k)))
    args = SimpleNamespace(
        model="mythos-fast",
        iterations=1,
        max_tokens=64,
        max_growth_mb=512,
        min_free_percent=20,
        prompt="probe",
        json=False,
    )

    with pytest.raises(SystemExit):
        cli.cmd_bench({"models": {"mythos-fast": {}}}, args)

    assert requested == []


def test_benchmark_reports_throughput_and_memory_stability(monkeypatch, capsys):
    cli = _load_cli()
    gb = 1024**3
    monkeypatch.setattr(cli, "_app_models", lambda _conf: {"mythos-fast": {"loaded": True}})
    monkeypatch.setattr(
        cli,
        "_app_conf",
        lambda _conf: {"base_url": "http://127.0.0.1:8000", "timeout": 30},
    )
    monkeypatch.setattr(cli, "_system_free_percent", lambda: 50.0)
    footprints = iter([5 * gb, 5.1 * gb])
    monkeypatch.setattr(cli, "_process_footprint_for_port", lambda _port: next(footprints))

    def fake_http(url, payload=None, **_kwargs):
        if url.endswith("/admin/api/stats"):
            return {"active_models": {"memory_pressure": {"hard_bytes": 95 * gb}}}
        return {
            "choices": [{"message": {"content": "OK"}, "finish_reason": "stop"}],
            "usage": {"completion_tokens": 100, "total_time": 2.0},
        }

    monkeypatch.setattr(cli, "_http_json", fake_http)
    args = SimpleNamespace(
        model="mythos-fast",
        iterations=1,
        max_tokens=128,
        max_growth_mb=512,
        min_free_percent=20,
        prompt="probe",
        json=True,
    )

    cli.cmd_bench({"models": {"mythos-fast": {}}, "omlx_app": {}}, args)

    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "pass"
    assert report["model"] == "mythos-fast"
    assert report["throughput_tokens_per_second"] == 50.0
    assert report["thinking_disabled"] is True
