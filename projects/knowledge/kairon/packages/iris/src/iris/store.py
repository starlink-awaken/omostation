"""Simple JSON file-based key-value store for local state."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class JSONFileStore:
    """Persistent key-value store backed by a JSON file."""

    def __init__(self, file_path: str | Path):
        self._path = Path(file_path)
        self._data: dict[str, Any] = {}
        self._load()

    def _load(self) -> None:
        if self._path.exists():
            try:
                self._data = json.loads(self._path.read_text())
            except Exception:
                self._data = {}

    def save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(self._data, ensure_ascii=False, indent=2))

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value
        self.save()

    def delete(self, key: str) -> None:
        self._data.pop(key, None)
        self.save()

    def list_keys(self) -> list[str]:
        return list(self._data.keys())

    def get_path(self) -> str:
        return str(self._path)
