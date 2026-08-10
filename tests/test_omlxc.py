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


def test_remote_lmstudio_policy_avoids_day_long_residency_and_gpu_oom():
    remotes = _load_models_config()["autopilot"]["remote_resident"]
    by_host = {entry["host"]: entry for entry in remotes if entry["engine"] == "lmstudio"}

    macmini = by_host["100.99.210.78"]["lms_args"]
    assert "--ttl 3600" in macmini
    assert "-c 16384" in macmini
    assert "--parallel 1" in macmini

    y7000p = by_host["100.64.43.36"]["lms_args"]
    assert "--ttl 3600" in y7000p
    assert "-c 8192" in y7000p
    assert "--parallel 1" in y7000p

    ollama = next(
        entry for entry in remotes
        if entry["host"] == "100.99.210.78" and entry["engine"] == "ollama"
    )
    assert ollama["keep_alive_sec"] == 3600


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


def _global_settings_fixture():
    return {
        "memory": {
            "prefill_memory_guard": True,
            "memory_guard_tier": "custom",
            "memory_guard_custom_ceiling_gb": 100.0,
        },
        "scheduler": {
            "max_concurrent_requests": 1,
            "embedding_batch_size": 32,
            "chunked_prefill": False,
            "prefill_priority": "context",
        },
        "cache": {
            "enabled": True,
            "ssd_cache_max_size": "185GB",
            "initial_cache_blocks": 256,
        },
        "sampling": {
            "max_context_window": 255000,
            "max_tokens": 32768,
            "temperature": 1.0,
            "top_p": 0.95,
        },
        "api_key": "must-not-enter-backup",
    }


def _app_catalog_fixture():
    return {
        "models": [
            {
                "id": "mythos-fast",
                "loaded": True,
                "pinned": False,
                "settings": {
                    "chat_template_kwargs": {"custom_flag": "keep"},
                },
            },
            {
                "id": "coding-next",
                "loaded": False,
                "pinned": False,
                "settings": None,
            },
            {
                "id": "embedding",
                "loaded": False,
                "pinned": False,
                "settings": None,
            },
        ]
    }


def test_app_tuning_targets_are_memory_bounded_and_force_thinking_off():
    cli = _load_cli()
    conf = {
        "models": {
            "mythos-fast": {
                "category": "reasoning",
                "role": "chat",
                "size_gb": 5,
                "params": {"temp": 0.7, "top_p": 0.9},
            },
            "coding-next": {
                "category": "coding",
                "role": "chat",
                "size_gb": 52,
                "params": {},
            },
            "embedding": {
                "category": "retrieval",
                "role": "embedding",
                "size_gb": 8,
                "params": {},
            },
        }
    }

    targets = cli._app_tuning_targets(conf, _app_catalog_fixture())

    assert targets["global"]["memory_guard_tier"] == "balanced"
    assert targets["global"]["max_concurrent_requests"] == 2
    assert targets["global"]["embedding_batch_size"] == 16
    assert targets["global"]["ssd_cache_max_size"] == "64GB"
    assert targets["global"]["sampling_max_context_window"] == 32768

    mythos = targets["models"]["mythos-fast"]
    assert mythos["enable_thinking"] is False
    assert mythos["thinking_budget_enabled"] is False
    # oMLX 0.5.7 normalizes a disabled/zero budget to null.
    assert mythos["thinking_budget_tokens"] is None
    assert mythos["chat_template_kwargs"] == {
        "custom_flag": "keep",
        "enable_thinking": False,
    }
    assert "enable_thinking" in mythos["forced_ct_kwargs"]
    assert mythos["is_pinned"] is True
    assert mythos["ttl_seconds"] == 3600

    coder = targets["models"]["coding-next"]
    assert coder["max_context_window"] == 131072
    assert coder["temperature"] == 1.0
    assert coder["top_p"] == 0.95
    assert coder["top_k"] == 40
    assert coder["ttl_seconds"] == 1800

    embedding = targets["models"]["embedding"]
    assert embedding == {
        "max_context_window": 8192,
        "ttl_seconds": 1800,
        "is_pinned": False,
    }


def test_app_tuning_snapshot_contains_only_controlled_reversible_fields():
    cli = _load_cli()
    targets = cli._app_tuning_targets(
        {
            "models": {
                "mythos-fast": {
                    "category": "reasoning",
                    "role": "chat",
                    "size_gb": 5,
                    "params": {},
                }
            }
        },
        {"models": _app_catalog_fixture()["models"][:1]},
    )

    snapshot = cli._app_tuning_snapshot(
        _global_settings_fixture(),
        {"models": _app_catalog_fixture()["models"][:1]},
        targets,
    )

    assert snapshot["global"]["memory_guard_tier"] == "custom"
    assert snapshot["global"]["ssd_cache_max_size"] == "185GB"
    assert "api_key" not in json.dumps(snapshot)
    assert snapshot["models"]["mythos-fast"]["is_pinned"] is False
    assert snapshot["models"]["mythos-fast"]["enable_thinking"] is None
    assert snapshot["models"]["mythos-fast"]["chat_template_kwargs"] == {
        "custom_flag": "keep"
    }


def test_tune_preview_performs_gets_only(monkeypatch, capsys):
    cli = _load_cli()
    calls = []
    conf = {
        "omlx_app": {"base_url": "http://127.0.0.1:8000", "timeout_sec": 2},
        "models": {
            "mythos-fast": {
                "category": "reasoning",
                "role": "chat",
                "size_gb": 5,
                "params": {},
            }
        },
    }

    def fake_http(url, payload=None, method=None, **_kwargs):
        calls.append((url, payload, method))
        if url.endswith("/admin/api/global-settings"):
            return _global_settings_fixture()
        return {"models": _app_catalog_fixture()["models"][:1]}

    monkeypatch.setattr(cli, "_http_json", fake_http)
    args = SimpleNamespace(
        apply=False,
        rollback=None,
        yes=False,
        restart=False,
        json=True,
    )

    cli.cmd_tune(conf, args)

    report = json.loads(capsys.readouterr().out)
    assert report["mode"] == "preview"
    assert report["changes"]
    assert len(calls) == 2
    assert all(payload is None and method is None for _, payload, method in calls)


def test_tune_apply_requires_explicit_yes_before_any_http(monkeypatch):
    cli = _load_cli()
    calls = []
    monkeypatch.setattr(cli, "_http_json", lambda *a, **k: calls.append((a, k)))
    args = SimpleNamespace(
        apply=True,
        rollback=None,
        yes=False,
        restart=False,
        json=True,
    )

    with pytest.raises(SystemExit):
        cli.cmd_tune({"models": {}, "omlx_app": {}}, args)

    assert calls == []


def test_restart_falls_back_to_relaunch_when_menubar_supervisor_stalls(monkeypatch):
    cli = _load_cli()
    health_calls = []
    relaunches = []
    clock = iter(range(100))

    def fake_http(url, payload=None, method=None, **_kwargs):
        if url.endswith("/admin/api/server/restart"):
            return {"status": "accepted"}
        health_calls.append(url)
        if len(health_calls) < 12:
            raise ConnectionError("server is still down")
        return {"status": "ok"}

    monkeypatch.setattr(cli, "_http_json", fake_http)
    monkeypatch.setattr(cli.time, "monotonic", lambda: next(clock))
    monkeypatch.setattr(cli.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(
        cli,
        "_relaunch_omlx_menubar",
        lambda: relaunches.append(True) or True,
        raising=False,
    )

    cli._restart_app_and_wait(
        {"omlx_app": {"base_url": "http://127.0.0.1:8000"}},
        timeout=45,
    )

    assert relaunches == [True]


def test_menubar_relaunch_only_terminates_one_exact_omlx_process(monkeypatch):
    cli = _load_cli()
    helper = getattr(cli, "_relaunch_omlx_menubar", None)
    assert helper is not None

    commands = []
    signals = []

    def fake_run(command):
        commands.append(command)
        if command == ["/usr/bin/pgrep", "-x", "oMLX"]:
            return SimpleNamespace(returncode=0, stdout="12345\n", stderr="")
        if command == ["/usr/bin/open", "-a", "oMLX"]:
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        raise AssertionError(f"unexpected command: {command}")

    def fake_kill(pid, sig):
        signals.append((pid, sig))
        if sig == 0:
            raise ProcessLookupError

    monkeypatch.setattr(cli, "_run", fake_run)
    monkeypatch.setattr(cli.os, "kill", fake_kill)
    monkeypatch.setattr(cli.time, "sleep", lambda _seconds: None)

    assert helper()
    assert signals == [(12345, cli.signal.SIGTERM), (12345, 0)]
    assert commands == [
        ["/usr/bin/pgrep", "-x", "oMLX"],
        ["/usr/bin/open", "-a", "oMLX"],
    ]


def test_apply_app_tuning_writes_only_changed_fields(monkeypatch):
    cli = _load_cli()
    calls = []
    monkeypatch.setattr(
        cli,
        "_http_json",
        lambda url, payload=None, method=None, **_kwargs: calls.append(
            (url, payload, method)
        ) or {},
    )
    current = {
        "global": {"max_concurrent_requests": 1, "chunked_prefill": False},
        "models": {
            "model/with slash": {
                "enable_thinking": None,
                "ttl_seconds": 3600,
            }
        },
    }
    target = {
        "global": {"max_concurrent_requests": 2, "chunked_prefill": False},
        "models": {
            "model/with slash": {
                "enable_thinking": False,
                "ttl_seconds": 3600,
            }
        },
    }

    result = cli._apply_app_tuning(
        {"omlx_app": {"base_url": "http://127.0.0.1:8000"}},
        current,
        target,
    )

    assert result == {"global_fields": 1, "models": 1, "fields": 2}
    assert calls == [
        (
            "http://127.0.0.1:8000/admin/api/global-settings",
            {"max_concurrent_requests": 2},
            "POST",
        ),
        (
            "http://127.0.0.1:8000/admin/api/models/model%2Fwith%20slash/settings",
            {"enable_thinking": False},
            "PUT",
        ),
    ]


def test_tuning_backup_is_private_and_round_trips_nulls(tmp_path, monkeypatch):
    cli = _load_cli()
    monkeypatch.setattr(cli, "OMLX_ROOT", str(tmp_path))
    snapshot = {
        "schema_version": 1,
        "global": {"sampling_max_tokens": 32768},
        "models": {"mythos-fast": {"enable_thinking": None}},
    }

    path = Path(cli._write_tuning_backup(snapshot))

    assert path.stat().st_mode & 0o777 == 0o600
    assert cli._read_tuning_backup(str(path)) == snapshot


def test_tuning_backup_rejects_fields_outside_control_plane(tmp_path):
    cli = _load_cli()
    path = tmp_path / "forged.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "global": {"api_key": "replace-me"},
                "models": {"mythos-fast": {"trust_remote_code": True}},
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(SystemExit):
        cli._read_tuning_backup(str(path))


def test_main_exposes_safe_tune_preview_command(monkeypatch):
    cli = _load_cli()
    called = []
    monkeypatch.setattr(cli, "load_conf", lambda: {"models": {}})
    monkeypatch.setattr(cli, "cmd_tune", lambda _conf, args: called.append(args))
    monkeypatch.setattr(cli.sys, "argv", ["omlxc", "tune", "--json"])

    cli.main()

    assert len(called) == 1
    assert called[0].apply is False
    assert called[0].rollback is None
    assert called[0].json is True


def test_fleet_tuning_targets_parse_lmstudio_and_ollama_policies():
    cli = _load_cli()
    conf = {
        "autopilot": {
            "remote_resident": [
                {
                    "host": "100.0.0.1",
                    "port": 1234,
                    "engine": "lmstudio",
                    "model": "model-a",
                    "ssh": True,
                    "lms_args": "-c 16384 --parallel 1 --ttl 3600",
                },
                {
                    "host": "100.0.0.2",
                    "port": 11434,
                    "engine": "ollama",
                    "model": "model-b",
                    "keep_alive_sec": 3600,
                },
            ]
        }
    }

    targets = cli._fleet_tuning_targets(conf)

    assert targets[0]["desired"] == {
        "loaded": True,
        "context_length": 16384,
        "parallel": 1,
        "ttl_seconds": 3600,
    }
    assert targets[1]["desired"] == {
        "loaded": True,
        "keep_alive_seconds": 3600,
    }


def test_fleet_tuning_changes_detect_long_lived_fallbacks_but_allow_countdown():
    cli = _load_cli()
    lm_target = {
        "engine": "lmstudio",
        "desired": {
            "loaded": True,
            "context_length": 16384,
            "parallel": 1,
            "ttl_seconds": 3600,
        },
    }
    assert cli._fleet_tuning_changes(
        lm_target,
        {
            "reachable": True,
            "manageable": True,
            "loaded": True,
            "context_length": 16384,
            "parallel": 1,
            "ttl_seconds": 86400,
        },
    ) == [{"field": "ttl_seconds", "from": 86400, "to": 3600}]

    ollama_target = {
        "engine": "ollama",
        "desired": {"loaded": True, "keep_alive_seconds": 3600},
    }
    assert cli._fleet_tuning_changes(
        ollama_target,
        {
            "reachable": True,
            "manageable": True,
            "loaded": True,
            "keep_alive_seconds": -1,
        },
    ) == [{"field": "keep_alive_seconds", "from": -1, "to": 3600}]
    assert cli._fleet_tuning_changes(
        ollama_target,
        {
            "reachable": True,
            "manageable": True,
            "loaded": True,
            "keep_alive_seconds": 1700,
        },
    ) == []


def test_fleet_tune_preview_never_applies(monkeypatch, capsys):
    cli = _load_cli()
    target = {
        "id": "ollama@node/model",
        "engine": "ollama",
        "host": "node",
        "port": 11434,
        "model": "model",
        "desired": {"loaded": True, "keep_alive_seconds": 3600},
        "source": {},
    }
    current = {
        "reachable": True,
        "manageable": True,
        "loaded": True,
        "keep_alive_seconds": -1,
    }
    monkeypatch.setattr(cli, "_fleet_tuning_targets", lambda _conf: [target])
    monkeypatch.setattr(cli, "_probe_fleet_target", lambda _target: current)
    applied = []
    monkeypatch.setattr(cli, "_apply_fleet_target", lambda *args: applied.append(args))

    cli.cmd_fleet_tune(
        {},
        SimpleNamespace(apply=False, yes=False, allow_partial=False, json=True),
    )

    report = json.loads(capsys.readouterr().out)
    assert report["mode"] == "preview"
    assert report["drift_count"] == 1
    assert applied == []


def test_fleet_tune_apply_requires_yes_before_probing(monkeypatch):
    cli = _load_cli()
    probed = []
    monkeypatch.setattr(cli, "_probe_fleet_target", lambda target: probed.append(target))

    with pytest.raises(SystemExit):
        cli.cmd_fleet_tune(
            {"autopilot": {"remote_resident": []}},
            SimpleNamespace(apply=True, yes=False, allow_partial=False, json=True),
        )

    assert probed == []


def test_fleet_tune_refuses_partial_apply_before_backup_or_mutation(monkeypatch):
    cli = _load_cli()
    target = {
        "id": "lmstudio@offline/model",
        "engine": "lmstudio",
        "host": "offline",
        "port": 1234,
        "model": "model",
        "desired": {
            "loaded": True,
            "context_length": 8192,
            "parallel": 1,
            "ttl_seconds": 3600,
        },
        "source": {},
    }
    monkeypatch.setattr(cli, "_fleet_tuning_targets", lambda _conf: [target])
    monkeypatch.setattr(
        cli,
        "_probe_fleet_target",
        lambda _target: {
            "reachable": False,
            "manageable": False,
            "loaded": None,
            "error": "offline",
        },
    )
    writes = []
    monkeypatch.setattr(cli, "_write_tuning_backup", lambda *args: writes.append(args))
    monkeypatch.setattr(cli, "_apply_fleet_target", lambda *args: writes.append(args))

    with pytest.raises(SystemExit):
        cli.cmd_fleet_tune(
            {},
            SimpleNamespace(apply=True, yes=True, allow_partial=False, json=True),
        )

    assert writes == []


def test_apply_fleet_target_sets_only_ollama_residency(monkeypatch):
    cli = _load_cli()
    calls = []
    monkeypatch.setattr(
        cli,
        "_api",
        lambda conf, port, endpoint, payload=None, timeout=None: calls.append(
            (conf, port, endpoint, payload, timeout)
        ) or {"done": True},
    )
    target = {
        "engine": "ollama",
        "host": "node",
        "port": 11434,
        "model": "qwen:9b",
        "desired": {"loaded": True, "keep_alive_seconds": 3600},
    }

    cli._apply_fleet_target(target, {"loaded": True})

    assert calls == [
        (
            {"host": "node"},
            11434,
            "/api/generate",
            {"model": "qwen:9b", "keep_alive": 3600, "stream": False},
            180,
        )
    ]


def test_apply_fleet_target_reloads_lmstudio_with_stable_identifier(monkeypatch):
    cli = _load_cli()
    calls = []
    monkeypatch.setattr(
        cli,
        "_remote_lms_command",
        lambda target, arguments, **_kwargs: calls.append((target, arguments)) or "ok",
    )
    target = {
        "engine": "lmstudio",
        "host": "node",
        "port": 1234,
        "model": "gemma",
        "desired": {
            "loaded": True,
            "context_length": 16384,
            "parallel": 1,
            "ttl_seconds": 3600,
        },
        "source": {"ssh": True},
    }

    cli._apply_fleet_target(target, {"loaded": True, "identifier": "old-instance"})

    assert calls == [
        (target, ["unload", "old-instance"]),
        (
            target,
            [
                "load",
                "gemma",
                "-c",
                16384,
                "--parallel",
                1,
                "--ttl",
                3600,
                "--identifier",
                "gemma",
                "-y",
            ],
        ),
    ]


def test_main_exposes_safe_fleet_tune_preview_command(monkeypatch):
    cli = _load_cli()
    called = []
    monkeypatch.setattr(cli, "load_conf", lambda: {"autopilot": {}})
    monkeypatch.setattr(cli, "cmd_fleet_tune", lambda _conf, args: called.append(args))
    monkeypatch.setattr(cli.sys, "argv", ["omlxc", "fleet-tune", "--json"])

    cli.main()

    assert len(called) == 1
    assert called[0].apply is False
    assert called[0].allow_partial is False
