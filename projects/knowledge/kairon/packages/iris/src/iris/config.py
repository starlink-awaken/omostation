"""Three-layer configuration system.

Config resolution order (later overrides earlier):
  1. Default values (compiled-in)
  2. IRIS_* environment variables
  3. ~/.iris/config.json file
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, cast

_SENSITIVE_KEYS = {"wxread.cookie"}
_SENSITIVE_ENV_PATTERNS = ("COOKIE", "TOKEN", "SECRET", "PASSWORD", "KEY")


DEFAULT_CONFIG_DIR = Path.home() / ".iris"
DEFAULT_CONFIG_FILE = DEFAULT_CONFIG_DIR / "config.json"
DEFAULT_DOMAINS_DIR = DEFAULT_CONFIG_DIR / "domains"

# Default Obsidian vault path (macOS iCloud)
DEFAULT_OBSIDIAN_VAULT = Path.home() / "Library/Mobile Documents/iCloud~md~obsidian/Documents"


class IrisConfig:
    """Three-layer config: defaults < env vars < config file."""

    def __init__(self, config_path: str | Path | None = None):
        self._config_path = Path(config_path) if config_path else DEFAULT_CONFIG_FILE
        self._file_config: dict[str, Any] = {}
        self._load()

    def _load(self) -> None:
        """Load config from file if it exists."""
        if self._config_path.exists():
            try:
                self._file_config = json.loads(self._config_path.read_text())
            except Exception:
                self._file_config = {}

    def save(self) -> None:
        """Save current config to file."""
        self._config_path.parent.mkdir(parents=True, exist_ok=True)
        self._config_path.write_text(json.dumps(self._file_config, ensure_ascii=False, indent=2))

    def get(self, key: str, default: Any = None) -> Any:
        """Get a config value (env var > file > default)."""
        env_key = f"IRIS_{key.upper().replace('.', '_')}"
        env_val = os.environ.get(env_key)
        if env_val is not None:
            return env_val

        parts = key.split(".")
        val: Any = self._file_config
        for part in parts:
            if isinstance(val, dict):
                val = val.get(part)
            else:
                val = None
                break
        if val is not None:
            return val

        return default

    def set(self, key: str, value: Any) -> None:
        """Set a config value and persist."""
        parts = key.split(".")
        target = self._file_config
        for part in parts[:-1]:
            if part not in target or not isinstance(target[part], dict):
                target[part] = {}
            target = target[part]
        target[parts[-1]] = value
        self.save()

    @property
    def config_dir(self) -> Path:
        """Get the iris config directory."""
        return self._config_path.parent

    @property
    def domains_dir(self) -> Path:
        """Get the SSOT domains directory."""
        return self.config_dir / "domains"

    @property
    def local_files_dir(self) -> str:
        """Get local files directory path (with env override)."""
        return self.get(  # type: ignore[no-any-return]
            "local_files.directory",
            default=str(Path.home() / "Documents/notes"),
        )

    @property
    def obsidian_vault(self) -> str:
        """Get Obsidian vault path (with env override)."""
        return self.get(  # type: ignore[no-any-return]
            "obsidian.vault",
            default=str(DEFAULT_OBSIDIAN_VAULT),
        )

    @property
    def wxread_cookie(self) -> str:
        """Get WeChat Read cookie from keychain, falling back to config file.

        Keychain takes priority over config file and env var.
        """
        from iris.keychain import get_password

        pw = get_password("wxread_cookie")
        if pw is not None:
            return pw
        return cast("str", self.get("wxread.cookie", default=""))

    @property
    def verbose(self) -> bool:
        val = self.get("verbose", default="false")
        return val.lower() in ("true", "1", "yes")

    def to_dict(self) -> dict[str, Any]:
        """Full config dump (for CLI display)."""
        return {
            "config_path": str(self._config_path),
            "domains_dir": str(self.domains_dir),
            "obsidian_vault": self.obsidian_vault,
            "wxread_configured": bool(self.wxread_cookie),
            "file_config": {k: "***" if k in _SENSITIVE_KEYS else v for k, v in self._file_config.items()},
            "env_overrides": {
                k: "***" if any(p in k.upper() for p in _SENSITIVE_ENV_PATTERNS) else v
                for k, v in os.environ.items()
                if k.startswith("IRIS_")
            },
        }
