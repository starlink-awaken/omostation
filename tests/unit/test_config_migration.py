"""Legacy JSON migration and atomic persistence contracts."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from omlxc.config import (
    AtomicRollbackError,
    AtomicWriteError,
    ConfigError,
    build_migration_plan,
    load_config,
    migrate_legacy_json,
    render_toml,
    write_config_atomic,
)

REPOSITORY_ROOT = Path(__file__).parents[2]


def _sanitized_legacy_config() -> dict[str, object]:
    models: dict[str, object] = {}
    fallback: dict[str, str] = {}
    fallback_ollama: dict[str, str] = {}
    for index in range(23):
        model_id = f"model-{index:02d}"
        models[model_id] = {
            "alias": f"/models/{model_id}",
            "category": "reasoning" if index == 0 else "general",
            "engine": "mlx_lm",
            "note": f"sanitized fixture {index}",
            "params": {
                "max_tokens": 4096 + index,
                "temp": 0.7,
                "top_p": 0.9,
                "chat_template_args": {"enable_thinking": index == 0},
            },
            "port": 8100 + index,
            "reasoning": index == 0,
            "role": "chat",
            "size_gb": 4.0 + index,
        }
        fallback[model_id] = f"fallback-{index:02d}"
        if index < 16:
            fallback_ollama[model_id] = f"ollama-{index:02d}"

    nodes = [
        {
            "name": f"Compute Node {index}",
            "role": "local" if index == 0 else "remote",
            "host": f"node-{index}.example.invalid",
            "probe": {"lmstudio": 1234 + index, "ollama": 11434 + index},
        }
        for index in range(3)
    ]
    engine_nodes = {
        f"pool-{index}": {
            "host": f"node-{index}.example.invalid",
            "primary": "lmstudio",
            "fallback": ["ollama"],
            "lmstudio_port": 1234 + index,
            "ollama_port": 11434 + index,
        }
        for index in range(3)
    }
    return {
        "version": 2,
        "host": "node-0.example.invalid",
        "omlx_app": {
            "base_url": "https://node-0.example.invalid:8000",
            "model_dir": "/models",
            "request_defaults": {"thinking_budget": 0},
        },
        "defaults": {"max_tokens": 4096, "temp": 0.7, "top_p": 0.9},
        "models": models,
        "cluster": {"gateway_port": 9290, "nodes": nodes},
        "autopilot": {
            "enabled": True,
            "idle_ttl_sec": 900,
            "mem_free_pct_floor": 17.5,
            "resident": ["model-00", "model-01", "model-02"],
            "remote_resident": [
                {
                    "engine": "ollama",
                    "host": "node-1.example.invalid",
                    "port": 11435,
                    "model": "ollama-00",
                    "keep_alive_sec": 3600,
                }
            ],
        },
        "engine_policy": {"nodes": engine_nodes},
        "fallback": fallback,
        "fallback_ollama": fallback_ollama,
        "presets": {"fast": ["model-00"], "dev": ["model-01", "model-02"]},
    }


def _write_legacy(path: Path, data: dict[str, object] | None = None) -> Path:
    path.write_text(json.dumps(data or _sanitized_legacy_config()), encoding="utf-8")
    return path


def test_migration_preserves_required_legacy_semantics(tmp_path: Path) -> None:
    source = _write_legacy(tmp_path / "models.json")

    migrated = migrate_legacy_json(source, base_directory=tmp_path)

    assert len(migrated.models) == 23
    assert len(migrated.nodes) == 3
    assert len(migrated.placements) == 23
    assert len(migrated.policies.fallbacks) == 23
    assert len(migrated.policies.ollama_fallbacks) == 16
    assert migrated.policies.resident_models == ("model-00", "model-01", "model-02")
    assert migrated.policies.memory_free_percent_floor == 17.5
    assert migrated.policies.thinking_enabled is False
    assert migrated.models[0].reasoning is True
    assert migrated.models[0].parameters["chat_template_args"] == {"enable_thinking": True}
    assert migrated.placements[0].model_path == "/models/model-00"

    target = tmp_path / "config.toml"
    target.write_text(render_toml(migrated), encoding="utf-8")
    round_tripped = load_config(target, env={}, base_directory=tmp_path)
    assert round_tripped == migrated


def test_migration_plan_is_summary_only_and_does_not_write(tmp_path: Path) -> None:
    source = _write_legacy(tmp_path / "models.json")
    target = tmp_path / "config.toml"

    plan = build_migration_plan(source, target=target, base_directory=tmp_path)

    assert plan.schema_version == "1"
    assert plan.model_count == 23
    assert plan.node_count == 3
    assert plan.placement_count == 23
    assert plan.will_write is False
    serialized = plan.model_dump_json()
    assert "example.invalid" not in serialized
    assert "/models/" not in serialized
    assert not target.exists()


def test_migrated_node_ids_do_not_change_when_addresses_change(tmp_path: Path) -> None:
    first_data = _sanitized_legacy_config()
    second_data = json.loads(json.dumps(first_data))
    second_data["cluster"]["nodes"][0]["host"] = "replacement.example.invalid"
    second_data["engine_policy"]["nodes"]["pool-0"]["host"] = "replacement.example.invalid"
    first = migrate_legacy_json(
        _write_legacy(tmp_path / "first.json", first_data), base_directory=tmp_path
    )
    second = migrate_legacy_json(
        _write_legacy(tmp_path / "second.json", second_data), base_directory=tmp_path
    )

    assert tuple(node.id for node in first.nodes) == tuple(node.id for node in second.nodes)
    assert first.nodes[0].addresses != second.nodes[0].addresses


def test_distinct_node_names_with_same_slug_receive_stable_collision_safe_ids(
    tmp_path: Path,
) -> None:
    data = _sanitized_legacy_config()
    data["cluster"]["nodes"][0]["name"] = "Same Node"
    data["cluster"]["nodes"][1]["name"] = "Same-Node"
    first = migrate_legacy_json(
        _write_legacy(tmp_path / "slug-collision-first.json", data),
        base_directory=tmp_path,
    )

    changed_addresses = json.loads(json.dumps(data))
    changed_addresses["cluster"]["nodes"][0]["host"] = "changed-0.example.invalid"
    changed_addresses["cluster"]["nodes"][1]["host"] = "changed-1.example.invalid"
    changed_addresses["host"] = "changed-0.example.invalid"
    first_remote = changed_addresses["autopilot"]["remote_resident"][0]
    first_remote["host"] = "changed-1.example.invalid"
    second = migrate_legacy_json(
        _write_legacy(tmp_path / "slug-collision-second.json", changed_addresses),
        base_directory=tmp_path,
    )

    first_ids = tuple(node.id for node in first.nodes[:2])
    second_ids = tuple(node.id for node in second.nodes[:2])
    assert first_ids == second_ids
    assert len(set(first_ids)) == 2
    assert all(identifier.startswith("same-node-") for identifier in first_ids)


def test_exact_duplicate_node_identity_fails_closed_with_precise_error(
    tmp_path: Path,
) -> None:
    data = _sanitized_legacy_config()
    data["cluster"]["nodes"][1]["name"] = data["cluster"]["nodes"][0]["name"]

    with pytest.raises(ConfigError, match="duplicate legacy node identity"):
        migrate_legacy_json(
            _write_legacy(tmp_path / "duplicate-node.json", data),
            base_directory=tmp_path,
        )


def test_unmapped_legacy_fields_are_retained_as_safe_extensions(tmp_path: Path) -> None:
    data = _sanitized_legacy_config()
    data["active_root"] = "/legacy/control-root"
    data["custom_operational"] = {"mode": "legacy", "attempts": 3}

    migrated = migrate_legacy_json(
        _write_legacy(tmp_path / "extensions.json", data), base_directory=tmp_path
    )

    assert migrated.legacy_extensions["active_root"] == "/legacy/control-root"
    assert migrated.legacy_extensions["custom_operational"] == {
        "mode": "legacy",
        "attempts": 3,
    }
    assert migrated.legacy_extensions["cluster_metadata"] == {"gateway_port": 9290}


def test_legacy_extensions_toml_round_trip_preserves_nested_json_and_null(
    tmp_path: Path,
) -> None:
    data = _sanitized_legacy_config()
    data["custom_operational"] = {
        "nullable": None,
        "nested": [{"enabled": True, "weight": 1.5}, None],
    }
    migrated = migrate_legacy_json(
        _write_legacy(tmp_path / "extensions-round-trip.json", data),
        base_directory=tmp_path,
    )
    target = tmp_path / "config.toml"

    target.write_text(render_toml(migrated), encoding="utf-8")
    loaded = load_config(target, env={}, base_directory=tmp_path)

    assert loaded.legacy_extensions == migrated.legacy_extensions


def test_plaintext_secrets_in_legacy_extensions_fail_closed(tmp_path: Path) -> None:
    data = _sanitized_legacy_config()
    data["custom_operational"] = {"api_token": "synthetic-do-not-copy"}

    with pytest.raises(ConfigError, match="Keychain") as captured:
        migrate_legacy_json(_write_legacy(tmp_path / "secret.json", data), base_directory=tmp_path)

    assert "synthetic-do-not-copy" not in str(captured.value)


@pytest.mark.parametrize(
    "credential_key",
    [
        "apiKey",
        "APIKey",
        "APIKEY",
        "api_key",
        "api-key",
        "accessToken",
        "access.token",
        "clientSecret",
        "clientsecret",
        "password",
        "passwd",
        "credential",
        "credentials",
        "apiKeys",
        "api_keys",
        "APIKEYS",
        "accessTokens",
        "clientSecrets",
        "passwords",
    ],
)
def test_all_canonical_credential_key_spellings_reject_plaintext(
    tmp_path: Path, credential_key: str
) -> None:
    data = _sanitized_legacy_config()
    data["custom_operational"] = {"nested": [{credential_key: "synthetic-do-not-copy"}]}

    with pytest.raises(ConfigError, match="Keychain") as captured:
        migrate_legacy_json(
            _write_legacy(tmp_path / f"{credential_key}.json", data),
            base_directory=tmp_path,
        )

    assert "synthetic-do-not-copy" not in str(captured.value)


@pytest.mark.parametrize(
    "invalid_reference",
    ["keychain://", "keychain://service", "keychain:///account"],
)
def test_credential_fields_reject_malformed_keychain_references(
    tmp_path: Path, invalid_reference: str
) -> None:
    data = _sanitized_legacy_config()
    data["custom_operational"] = {"accessToken": invalid_reference}

    with pytest.raises(ConfigError, match="Keychain"):
        migrate_legacy_json(
            _write_legacy(tmp_path / "malformed-keychain.json", data),
            base_directory=tmp_path,
        )


def test_valid_keychain_references_survive_nested_legacy_extensions(tmp_path: Path) -> None:
    data = _sanitized_legacy_config()
    data["custom_operational"] = {"credentials": "keychain://omlxc/legacy-backend"}

    migrated = migrate_legacy_json(
        _write_legacy(tmp_path / "valid-keychain.json", data), base_directory=tmp_path
    )

    assert migrated.legacy_extensions["custom_operational"] == {
        "credentials": "keychain://omlxc/legacy-backend"
    }


def test_noncredential_words_are_not_false_positives(tmp_path: Path) -> None:
    data = _sanitized_legacy_config()
    data["custom_operational"] = {
        "monkey": "banana",
        "monkeys": "bananas",
        "hockey": "stick",
        "keychain_service": "omlxc",
        "routingKey": "interactive",
    }

    migrated = migrate_legacy_json(
        _write_legacy(tmp_path / "noncredentials.json", data), base_directory=tmp_path
    )

    assert migrated.legacy_extensions["custom_operational"] == {
        "monkey": "banana",
        "monkeys": "bananas",
        "hockey": "stick",
        "keychain_service": "omlxc",
        "routingKey": "interactive",
    }


def test_repository_legacy_json_migrates_read_only_with_expected_counts(tmp_path: Path) -> None:
    source = REPOSITORY_ROOT / "conf" / "models.json"
    before = source.read_bytes()
    legacy = json.loads(before)

    migrated = migrate_legacy_json(source, base_directory=tmp_path)

    assert source.read_bytes() == before
    assert len(migrated.models) == 23
    assert len(migrated.nodes) == 3
    assert len(migrated.policies.fallbacks) == 22
    assert len(migrated.policies.ollama_fallbacks) == 15
    assert migrated.policies.resident_models
    assert migrated.policies.memory_free_percent_floor is not None
    assert {model.id for model in migrated.models} == set(legacy["models"])
    placements = {placement.model_id: placement for placement in migrated.placements}
    models = {model.id: model for model in migrated.models}
    for model_id, legacy_model in legacy["models"].items():
        assert placements[model_id].model_path == legacy_model["alias"]
        assert models[model_id].parameters == legacy_model["params"]
        assert models[model_id].reasoning is bool(legacy_model.get("reasoning", False))
    assert migrated.policies.resident_models == tuple(legacy["autopilot"]["resident"])
    assert migrated.policies.memory_free_percent_floor == legacy["autopilot"]["mem_free_pct_floor"]
    assert migrated.policies.fallbacks == {
        key: value for key, value in legacy["fallback"].items() if not key.startswith("_")
    }
    assert migrated.policies.ollama_fallbacks == {
        key: value for key, value in legacy["fallback_ollama"].items() if not key.startswith("_")
    }
    assert len(migrated.policies.remote_resident) == len(legacy["autopilot"]["remote_resident"])
    assert (
        migrated.policies.thinking_settings["legacy_request_defaults"]
        == legacy["omlx_app"]["request_defaults"]
    )


def test_atomic_write_sets_private_mode_and_snapshots_existing_target(tmp_path: Path) -> None:
    target = tmp_path / "config.toml"
    target.write_text("schema_version = 0\n", encoding="utf-8")
    target.chmod(0o644)

    result = write_config_atomic(target, "schema_version = 1\n")

    assert target.read_text(encoding="utf-8") == "schema_version = 1\n"
    assert target.stat().st_mode & 0o777 == 0o600
    assert result.snapshot_path is not None
    assert result.snapshot_path.read_text(encoding="utf-8") == "schema_version = 0\n"
    assert result.snapshot_path.stat().st_mode & 0o777 == 0o600
    assert list(tmp_path.glob(".config.toml.*.tmp")) == []


def test_atomic_write_failure_preserves_target_and_cleans_temporary_file(
    tmp_path: Path,
) -> None:
    target = tmp_path / "config.toml"
    target.write_text("original", encoding="utf-8")

    def fail_write(_fd: int, _payload: bytes) -> int:
        raise OSError("injected write failure")

    with pytest.raises(AtomicWriteError, match="write"):
        write_config_atomic(target, "replacement", write=fail_write)

    assert target.read_text(encoding="utf-8") == "original"
    assert list(tmp_path.glob(".config.toml.*.tmp")) == []


def test_atomic_replace_failure_preserves_target_and_cleans_temporary_file(
    tmp_path: Path,
) -> None:
    target = tmp_path / "config.toml"
    target.write_text("original", encoding="utf-8")

    def fail_replace(
        _source: str | bytes | os.PathLike[str] | os.PathLike[bytes],
        _target: str | bytes | os.PathLike[str] | os.PathLike[bytes],
    ) -> None:
        raise OSError("injected replace failure")

    with pytest.raises(AtomicWriteError, match="replace"):
        write_config_atomic(target, "replacement", replace=fail_replace)

    assert target.read_text(encoding="utf-8") == "original"
    assert list(tmp_path.glob(".config.toml.*.tmp")) == []
    snapshots = list(tmp_path.glob("config.toml.snapshot-*"))
    assert len(snapshots) == 1
    assert snapshots[0].read_text(encoding="utf-8") == "original"


def test_atomic_chmod_failure_happens_before_replace_and_preserves_original(
    tmp_path: Path,
) -> None:
    target = tmp_path / "config.toml"
    target.write_text("original", encoding="utf-8")
    target.chmod(0o640)
    replacements: list[tuple[str, str]] = []

    def fail_chmod(_path: str, _mode: int) -> None:
        raise OSError("injected chmod failure")

    def observe_replace(source: str, destination: str) -> None:
        replacements.append((source, destination))
        os.replace(source, destination)

    with pytest.raises(AtomicWriteError, match="chmod"):
        write_config_atomic(
            target,
            "replacement",
            chmod=fail_chmod,
            replace=observe_replace,
        )

    assert replacements == []
    assert target.read_text(encoding="utf-8") == "original"
    assert target.stat().st_mode & 0o777 == 0o640
    assert list(tmp_path.glob(".config.toml.*.tmp")) == []


def test_directory_fsync_failure_rolls_back_original_content_and_mode(
    tmp_path: Path,
) -> None:
    target = tmp_path / "config.toml"
    target.write_text("original", encoding="utf-8")
    target.chmod(0o640)
    sync_calls = 0

    def fail_first_directory_fsync(_directory: Path) -> None:
        nonlocal sync_calls
        sync_calls += 1
        if sync_calls == 1:
            raise OSError("injected directory fsync failure")

    with pytest.raises(AtomicWriteError, match="directory_fsync"):
        write_config_atomic(
            target,
            "replacement",
            fsync_directory=fail_first_directory_fsync,
        )

    assert sync_calls == 2
    assert target.read_text(encoding="utf-8") == "original"
    assert target.stat().st_mode & 0o777 == 0o640
    snapshots = list(tmp_path.glob("config.toml.snapshot-*"))
    assert len(snapshots) == 1
    assert snapshots[0].read_text(encoding="utf-8") == "original"
    assert snapshots[0].stat().st_mode & 0o777 == 0o600
    assert list(tmp_path.glob(".config.toml.*.tmp")) == []
    assert list(tmp_path.glob(".config.toml.*.rollback")) == []


def test_rollback_failure_exposes_both_operation_and_rollback_stages(
    tmp_path: Path,
) -> None:
    target = tmp_path / "config.toml"
    target.write_text("original", encoding="utf-8")
    replacement_calls = 0

    def fail_rollback_replace(source: str, destination: str) -> None:
        nonlocal replacement_calls
        replacement_calls += 1
        if replacement_calls == 2:
            raise OSError("injected rollback replace failure")
        os.replace(source, destination)

    def fail_directory_fsync(_directory: Path) -> None:
        raise OSError("injected directory fsync failure")

    with pytest.raises(AtomicRollbackError) as captured:
        write_config_atomic(
            target,
            "replacement",
            replace=fail_rollback_replace,
            fsync_directory=fail_directory_fsync,
        )

    assert captured.value.operation_stage == "directory_fsync"
    assert captured.value.rollback_stage == "replace"
    assert isinstance(captured.value.operation_error, OSError)
    assert isinstance(captured.value.rollback_error, OSError)
    assert list(tmp_path.glob(".config.toml.*.tmp")) == []
    assert list(tmp_path.glob(".config.toml.*.rollback")) == []
