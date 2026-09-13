"""Persistence layer for mind model quartet — YAML-backed hot-reload store."""

from __future__ import annotations

import os
import yaml
from pathlib import Path
from typing import Any

DEFAULT_STATE_DIR = ".omo/state/mindmodel"

SCHEMA_MAP = {
    "persona_profile": "PersonaProfile",
    "agenda_radar": "AgendaRadar",
    "attention_field": "AttentionField",
    "context_anchor": "ContextAnchor",
}


class MindModelStore:
    """Reads/writes mind model YAML files from .omo/state/mindmodel/."""

    def __init__(self, state_dir: str | None = None) -> None:
        self.state_dir = Path(state_dir or DEFAULT_STATE_DIR)

    def _path(self, dimension: str) -> Path:
        return self.state_dir / f"{dimension}.yaml"

    def read(self, dimension: str) -> dict[str, Any]:
        p = self._path(dimension)
        if not p.exists():
            return {}
        with p.open("r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    def write(self, dimension: str, data: dict[str, Any]) -> None:
        p = self._path(dimension)
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("w", encoding="utf-8") as f:
            yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    def load_all(self) -> dict[str, dict[str, Any]]:
        return {dim: self.read(dim) for dim in SCHEMA_MAP}
