"""Deterministic configuration loading and merge precedence."""

from __future__ import annotations

import json
import os
import stat
import sys
import tomllib
from collections.abc import Mapping
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
from typing import Any, cast

from platformdirs import user_config_path
from pydantic import ValidationError

from omlxc.domain import CredentialPolicyError, sanitize_sensitive

from .schema import AppConfig, DaemonConfig, PoliciesConfig, StorageConfig


class ConfigError(ValueError):
    """A fail-closed configuration error safe to expose to CLI callers."""


def default_config_directory() -> Path:
    return user_config_path("omlxc", appauthor=False)


def default_config_path() -> Path:
    platform_path = default_config_directory() / "config.toml"
    if sys.platform != "darwin" or platform_path.exists() or platform_path.is_symlink():
        return platform_path
    compatibility_path = _xdg_compatibility_config_path()
    if compatibility_path == platform_path:
        return platform_path
    try:
        return require_private_config_path(compatibility_path)
    except ConfigError:
        return platform_path


def _xdg_compatibility_config_path() -> Path:
    return Path.home() / ".config/omlxc/config.toml"


def config_identity(config: AppConfig) -> str:
    """Return a path-free identity for the fully resolved daemon configuration."""
    canonical = json.dumps(
        config.model_dump(mode="json"),
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )
    return f"sha256:{sha256(canonical.encode('utf-8')).hexdigest()}"


def require_private_config_path(path: Path) -> Path:
    """Resolve and validate a daemon config without exposing its path in errors."""
    if not path.is_absolute():
        raise ConfigError("daemon configuration path is not trusted")
    try:
        resolved = path.resolve(strict=True)
        metadata = path.lstat()
    except OSError:
        raise ConfigError("daemon configuration is unavailable") from None
    if resolved != path or path.is_symlink() or not path.is_file():
        raise ConfigError("daemon configuration path is not trusted")
    if metadata.st_uid != os.geteuid() or stat.S_IMODE(metadata.st_mode) != 0o600:
        raise ConfigError("daemon configuration is not private")
    return resolved


def safe_defaults(*, base_directory: Path | None = None) -> AppConfig:
    directory = base_directory or default_config_directory()
    return AppConfig(
        daemon=DaemonConfig(socket_path=directory / "omlxcd.sock"),
        storage=StorageConfig(database_path=directory / "state.db"),
        policies=PoliciesConfig(),
    )


def load_config(
    path: Path | None = None,
    *,
    env: Mapping[str, str] | None = None,
    overrides: Mapping[str, Any] | None = None,
    base_directory: Path | None = None,
) -> AppConfig:
    merged: dict[str, Any] = safe_defaults(base_directory=base_directory).model_dump(mode="python")
    if path is not None:
        try:
            file_values = tomllib.loads(path.read_text(encoding="utf-8"))
        except (OSError, tomllib.TOMLDecodeError) as exc:
            raise ConfigError("unable to read valid TOML configuration") from exc
        _require_schema_version(file_values)
        file_values = _decode_legacy_extensions(file_values)
        merged = _deep_merge(merged, file_values)
    environment_values = _environment_overrides(os.environ if env is None else env)
    merged = _deep_merge(merged, environment_values)
    if overrides is not None:
        merged = _deep_merge(merged, overrides)
    _require_schema_version(merged)
    try:
        return AppConfig.model_validate(merged)
    except CredentialPolicyError as exc:
        raise ConfigError(f"invalid configuration: {exc}") from exc
    except ValidationError as exc:
        details = sanitize_sensitive(str(exc.errors(include_input=False)))
        raise ConfigError(f"invalid configuration: {details}") from exc


def load_user_config(
    *,
    env: Mapping[str, str] | None = None,
    overrides: Mapping[str, Any] | None = None,
    base_directory: Path | None = None,
) -> AppConfig:
    """Load the platform default file when present, otherwise safe defaults."""
    path = default_config_path()
    return load_config(
        path if path.exists() else None,
        env=env,
        overrides=overrides,
        base_directory=base_directory,
    )


def _require_schema_version(values: Mapping[str, Any]) -> None:
    if values.get("schema_version") != 1:
        raise ConfigError("unsupported schema_version; expected 1")


def _deep_merge(base: Mapping[str, Any], overlay: Mapping[str, Any]) -> dict[str, Any]:
    result = deepcopy(dict(base))
    for key, value in overlay.items():
        current = result.get(key)
        if isinstance(current, Mapping) and isinstance(value, Mapping):
            result[key] = _deep_merge(
                cast(Mapping[str, Any], current), cast(Mapping[str, Any], value)
            )
        else:
            result[key] = deepcopy(value)
    return result


def _environment_overrides(environment: Mapping[str, str]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for name, raw_value in environment.items():
        if not name.startswith("OMLXC_"):
            continue
        nested = name.removeprefix("OMLXC_")
        if not nested or "__" not in nested:
            raise ConfigError(
                "OMLXC_ environment keys must use double underscores between nested keys"
            )
        parts = [part.lower() for part in nested.split("__")]
        if any(not part for part in parts):
            raise ConfigError("OMLXC_ environment key contains an empty segment")
        cursor = result
        for part in parts[:-1]:
            child: Any = cursor.setdefault(part, {})
            if not isinstance(child, dict):
                raise ConfigError("conflicting OMLXC_ environment keys")
            cursor = cast(dict[str, Any], child)
        cursor[parts[-1]] = _parse_environment_value(raw_value)
    return result


def _parse_environment_value(raw_value: str) -> Any:
    try:
        return tomllib.loads(f"value = {raw_value}")["value"]
    except tomllib.TOMLDecodeError:
        return raw_value


def _decode_legacy_extensions(values: dict[str, Any]) -> dict[str, Any]:
    if "legacy_extensions_json" not in values:
        return values
    if "legacy_extensions" in values:
        raise ConfigError(
            "configuration cannot contain both legacy_extensions and legacy_extensions_json"
        )
    encoded = values.pop("legacy_extensions_json")
    if not isinstance(encoded, str):
        raise ConfigError("legacy_extensions_json must be a JSON string")
    try:
        decoded = json.loads(encoded)
    except json.JSONDecodeError as exc:
        raise ConfigError("legacy_extensions_json must contain valid JSON") from exc
    if not isinstance(decoded, dict):
        raise ConfigError("legacy_extensions_json must contain a JSON object")
    values["legacy_extensions"] = cast(dict[str, Any], decoded)
    return values
