"""Configuration schema and precedence contracts."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from omlxc.config import AppConfig, ConfigError, load_config, safe_defaults
from omlxc.domain import RouteProfile


def test_safe_defaults_are_versioned_and_disable_thinking(tmp_path: Path) -> None:
    config = safe_defaults(base_directory=tmp_path)

    assert config.schema_version == 1
    assert config.daemon.socket_path == tmp_path / "omlxcd.sock"
    assert config.storage.database_path == tmp_path / "state.db"
    assert config.storage.retention_days == 30
    assert config.nodes == ()
    assert config.backends == ()
    assert config.models == ()
    assert config.placements == ()
    assert config.policies.default_profile is RouteProfile.INTERACTIVE
    assert config.policies.thinking_enabled is False


def test_config_precedence_is_defaults_toml_env_then_overrides(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        """
schema_version = 1

[storage]
retention_days = 31
""".strip(),
        encoding="utf-8",
    )

    config = load_config(
        config_path,
        env={"OMLXC_STORAGE__RETENTION_DAYS": "32"},
        overrides={"storage": {"retention_days": 33}},
        base_directory=tmp_path,
    )

    assert config.storage.retention_days == 33


def test_nested_environment_values_keep_toml_types(tmp_path: Path) -> None:
    config = load_config(
        None,
        env={
            "OMLXC_STORAGE__RETENTION_DAYS": "45",
            "OMLXC_DAEMON__AUTOSTART": "true",
            "OMLXC_POLICIES__DEFAULT_PROFILE": '"eco"',
        },
        base_directory=tmp_path,
    )

    assert config.storage.retention_days == 45
    assert config.daemon.autostart is True
    assert config.policies.default_profile is RouteProfile.ECO


@pytest.mark.parametrize(
    "environment",
    [
        {"OMLXC_STORAGE__RETENTION_DAYS": '"thirty"'},
        {"OMLXC_UNKNOWN__VALUE": "1"},
        {"OMLXC_STORAGE_RETENTION_DAYS": "31"},
    ],
)
def test_invalid_or_unknown_environment_fails_closed(
    tmp_path: Path, environment: dict[str, str]
) -> None:
    with pytest.raises(ConfigError):
        load_config(None, env=environment, base_directory=tmp_path)


def test_unknown_or_unsupported_toml_schema_fails_closed(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        "schema_version = 2\nunknown = true\n",
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="schema_version"):
        load_config(config_path, env={}, base_directory=tmp_path)


def test_backend_credentials_accept_only_keychain_references(tmp_path: Path) -> None:
    plaintext = tmp_path / "plaintext.toml"
    plaintext.write_text(
        """
schema_version = 1

[[nodes]]
id = "node-a"
display_name = "Node A"
platform = "macos"

[[backends]]
id = "backend-a"
node_id = "node-a"
kind = "ollama"
base_url = "https://node-a.example.invalid"
credential_ref = "plain-secret"
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="Keychain"):
        load_config(plaintext, env={}, base_directory=tmp_path)

    keychain = plaintext.read_text(encoding="utf-8").replace(
        'credential_ref = "plain-secret"',
        'credential_ref = "keychain://omlxc/backend-a"',
    )
    plaintext.write_text(keychain, encoding="utf-8")
    assert load_config(plaintext, env={}, base_directory=tmp_path).backends[0].credential_ref


def test_node_identity_is_not_derived_from_its_address(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        """
schema_version = 1

[[nodes]]
id = "stable-node-id"
display_name = "Node A"
platform = "linux"
addresses = ["https://first.example.invalid"]
""".strip(),
        encoding="utf-8",
    )
    first = load_config(config_path, env={}, base_directory=tmp_path)

    config_path.write_text(
        config_path.read_text(encoding="utf-8").replace("first", "second"),
        encoding="utf-8",
    )
    second = load_config(config_path, env={}, base_directory=tmp_path)

    assert first.nodes[0].id == second.nodes[0].id == "stable-node-id"
    assert first.nodes[0].addresses != second.nodes[0].addresses


def test_embedded_url_auth_material_is_rejected_without_echoing_it(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        """
schema_version = 1

[[nodes]]
id = "node-a"
display_name = "Node A"
platform = "linux"

[[backends]]
id = "backend-a"
node_id = "node-a"
kind = "ollama"
base_url = "https://operator:synthetic-password@node-a.example.invalid"
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="Keychain") as captured:
        load_config(config_path, env={}, base_directory=tmp_path)

    assert "synthetic-password" not in str(captured.value)


def test_malformed_backend_keychain_reference_is_rejected(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        """
schema_version = 1

[[nodes]]
id = "node-a"
display_name = "Node A"
platform = "linux"

[[backends]]
id = "backend-a"
node_id = "node-a"
kind = "ollama"
base_url = "https://node-a.example.invalid"
credential_ref = "keychain:///account"
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="Keychain"):
        load_config(config_path, env={}, base_directory=tmp_path)


def test_encoded_legacy_extensions_cannot_bypass_keychain_policy(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        """
schema_version = 1
legacy_extensions_json = '{"nested":[{"apiKey":"synthetic-do-not-copy"}]}'
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="Keychain") as captured:
        load_config(config_path, env={}, base_directory=tmp_path)

    assert "synthetic-do-not-copy" not in str(captured.value)


@pytest.mark.parametrize(
    ("toml_body", "plaintext"),
    [
        (
            """
[[models]]
id = "model-a"
category = "chat"
role = "interactive"
engine = "mlx"

[models.parameters]
apiKey = "synthetic-model-plaintext"
""",
            "synthetic-model-plaintext",
        ),
        (
            """
[policies.sampling_defaults]
accessTokens = "synthetic-sampling-plaintext"
""",
            "synthetic-sampling-plaintext",
        ),
        (
            """
[policies.thinking_settings]
nested = [{ clientSecrets = "synthetic-thinking-plaintext" }]
""",
            "synthetic-thinking-plaintext",
        ),
        (
            """
[policies.thinking_settings]
endpoint = "https://operator:synthetic-url-password@example.invalid"
""",
            "synthetic-url-password",
        ),
    ],
)
def test_handwritten_toml_validates_arbitrary_json_fields_across_entire_tree(
    tmp_path: Path, toml_body: str, plaintext: str
) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text(f"schema_version = 1\n{toml_body}", encoding="utf-8")

    with pytest.raises(ConfigError, match="Keychain") as captured:
        load_config(config_path, env={}, base_directory=tmp_path)

    assert plaintext not in str(captured.value)


def test_environment_injection_cannot_bypass_whole_config_credential_validation(
    tmp_path: Path,
) -> None:
    plaintext = "synthetic-environment-plaintext"

    with pytest.raises(ConfigError, match="Keychain") as captured:
        load_config(
            None,
            env={"OMLXC_POLICIES__SAMPLING_DEFAULTS__APIKEYS": f'"{plaintext}"'},
            base_directory=tmp_path,
        )

    assert plaintext not in str(captured.value)


def test_override_injection_cannot_bypass_nested_list_credential_validation(
    tmp_path: Path,
) -> None:
    plaintext = "synthetic-override-plaintext"

    with pytest.raises(ConfigError, match="Keychain") as captured:
        load_config(
            None,
            env={},
            overrides={
                "policies": {"thinking_settings": {"nested": [{"clientSecrets": plaintext}]}}
            },
            base_directory=tmp_path,
        )

    assert plaintext not in str(captured.value)


def test_whole_config_validation_accepts_keychain_refs_and_business_keys(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        """
schema_version = 1

[policies.sampling_defaults]
apiKeys = "keychain://omlxc/sampling"
monkey = "banana"
monkeys = "bananas"
hockey = "stick"
keychain_service = "omlxc"
routingKey = "interactive"
""".strip(),
        encoding="utf-8",
    )

    loaded = load_config(config_path, env={}, base_directory=tmp_path)

    assert loaded.policies.sampling_defaults["apiKeys"] == "keychain://omlxc/sampling"
    assert loaded.policies.sampling_defaults["routingKey"] == "interactive"


@pytest.mark.parametrize(
    "invalid_reference",
    [
        "keychain://service/account?x=y",
        "keychain://service/account#frag",
        "keychain://user@host/account",
        "keychain://service/account\t",
        "keychain://service/a:b",
        "keychain://service/%2F",
        "keychain://service/a\\b",
        "keychain://service/account/extra",
        "keychain:///account",
        "keychain://service/",
        f"keychain://{'s' * 129}/account",
        f"keychain://service/{'a' * 129}",
    ],
)
def test_loader_rejects_noncanonical_keychain_references(
    tmp_path: Path, invalid_reference: str
) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        f"""
schema_version = 1

[[nodes]]
id = "node-a"
display_name = "Node A"
platform = "linux"

[[backends]]
id = "backend-a"
node_id = "node-a"
kind = "ollama"
base_url = "https://node-a.example.invalid"
credential_ref = {json.dumps(invalid_reference)}
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="Keychain") as captured:
        load_config(config_path, env={}, base_directory=tmp_path)

    assert invalid_reference not in str(captured.value)


@pytest.mark.parametrize(
    "valid_reference",
    [
        "keychain://com.omlxc.backend/node-1",
        "keychain://Service_1/Account.Name-2",
    ],
)
def test_loader_accepts_canonical_keychain_references(tmp_path: Path, valid_reference: str) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        f"""
schema_version = 1

[[nodes]]
id = "node-a"
display_name = "Node A"
platform = "linux"

[[backends]]
id = "backend-a"
node_id = "node-a"
kind = "ollama"
base_url = "https://node-a.example.invalid"
credential_ref = "{valid_reference}"
""".strip(),
        encoding="utf-8",
    )

    assert (
        load_config(config_path, env={}, base_directory=tmp_path).backends[0].credential_ref
        == valid_reference
    )


def test_direct_app_config_credential_rejection_raises_safe_domain_error(
    tmp_path: Path,
) -> None:
    plaintext = "synthetic-direct-model-plaintext"
    payload = safe_defaults(base_directory=tmp_path).model_dump(mode="python")
    payload["policies"]["sampling_defaults"] = {"apiKey": plaintext}

    with pytest.raises(Exception) as captured:
        AppConfig.model_validate(payload)

    assert not isinstance(captured.value, ValidationError)
    assert plaintext not in str(captured.value)
