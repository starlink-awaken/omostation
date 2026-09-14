"""Kronos 配置模块 — 统一路径和参数管理。"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


class KronosConfig:
    """Kronos 配置，优先 ~/.kronos/config.json，其次环境变量，最后默认值。"""

    _instance: KronosConfig | None = None

    def __init__(self) -> None:
        self._data: dict[str, Any] = self._load()

    def _load(self) -> dict[str, Any]:
        config_path = Path.home() / ".kronos" / "config.json"
        if config_path.exists():
            try:
                data: dict[str, Any] = json.loads(config_path.read_text())
                return data
            except Exception:
                pass
        return {}

    @property
    def vault_path(self) -> str:
        """Obsidian vault 根目录"""
        val: str = self._data.get(
            "vault_path",
            os.path.expanduser("~/Library/Mobile Documents/iCloud~md~obsidian/Documents"),
        )
        return val

    @property
    def workspace_path(self) -> str:
        val: str = self._data.get("workspace_path", os.path.expanduser("~/Workspace"))
        return val

    @property
    def concepts_dir(self) -> str:
        return os.path.join(self.vault_path, "99-系统", "knowledge", "concepts")

    @property
    def pending_links_path(self) -> str:
        return os.path.join(self.vault_path, "10-收件箱", "pending-links.md")

    @property
    def ollama_url(self) -> str:
        val: str = self._data.get("ollama_url", "http://localhost:11434")
        return val

    @property
    def default_model(self) -> str:
        val: str = self._data.get("default_model", "qwen3.5:4b")
        return val

    @property
    def fetch_timeout(self) -> int:
        return int(self._data.get("fetch_timeout", 60))

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def save(self) -> None:
        config_dir = Path.home() / ".kronos"
        config_dir.mkdir(parents=True, exist_ok=True)
        (config_dir / "config.json").write_text(json.dumps(self._data, indent=2, ensure_ascii=False))

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value


def get_config() -> KronosConfig:
    if KronosConfig._instance is None:
        KronosConfig._instance = KronosConfig()
    return KronosConfig._instance
