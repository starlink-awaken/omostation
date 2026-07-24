"""ECOS 统一配置管理"""

import json
import os
from pathlib import Path
from typing import Any, Optional


class ECOSConfig:
    """统一配置管理器"""

    _instance: Optional["ECOSConfig"] = None

    def __init__(self, config_path: str | None = None):
        self.config_path = config_path or os.environ.get("ECOS_CONFIG", "ecos.json")
        self._config: dict[str, Any] = {}
        self._load_config()

    @classmethod
    def get_instance(cls) -> "ECOSConfig":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _load_config(self) -> None:
        try:
            if Path(self.config_path).exists():
                with open(self.config_path, "r") as f:
                    self._config = json.load(f)
        except Exception:  # defensive fallback
            self._config = {}

    def get(self, key: str, default: Any = None) -> Any:
        env_key = f"ECOS_{key.upper().replace('.', '_')}"
        env_value = os.environ.get(env_key)
        if env_value:
            return env_value

        keys = key.split(".")
        value = self._config
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default

        return value

    def set(self, key: str, value: Any) -> None:
        keys = key.split(".")
        config = self._config
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        config[keys[-1]] = value

    def save(self) -> bool:
        try:
            with open(self.config_path, "w") as f:
                json.dump(self._config, f, indent=2)
            return True
        except Exception:  # defensive fallback
            return False
