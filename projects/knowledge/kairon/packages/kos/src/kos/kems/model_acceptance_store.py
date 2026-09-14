"""SQLite persistence for redacted KEMS candidate-model acceptance runs."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

_FORBIDDEN_KEYS = {"body", "content", "ocr_text", "raw_text", "text"}


def _reject_private(value: object) -> None:
    if isinstance(value, dict):
        if _FORBIDDEN_KEYS.intersection(str(key).lower() for key in value):
            raise ValueError("raw content fields are forbidden")
        for child in value.values():
            _reject_private(child)
    elif isinstance(value, list):
        for child in value:
            _reject_private(child)


class ModelAcceptanceStore:
    """Persist acceptance evidence without prediction features or source text."""

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)

    def _connect(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS model_acceptance_runs (
                    run_id TEXT PRIMARY KEY,
                    candidate_model_id TEXT NOT NULL,
                    baseline_model_id TEXT NOT NULL,
                    status TEXT NOT NULL CHECK (status IN ('shadow_pass', 'needs_review')),
                    promotion TEXT NOT NULL CHECK (promotion = 'blocked_until_omo_approval'),
                    report_json TEXT NOT NULL
                )
                """
            )

    def record(self, run_id: str, report: dict[str, Any]) -> bool:
        if not run_id.strip():
            raise ValueError("run_id is required")
        if report.get("schema_version") != "kems.model-acceptance.v1":
            raise ValueError("unsupported model acceptance schema")
        if report.get("promotion") != "blocked_until_omo_approval":
            raise ValueError("model acceptance cannot authorize promotion")
        _reject_private(report)
        for field in ("candidate_model_id", "baseline_model_id", "status"):
            if not isinstance(report.get(field), str) or not report[field].strip():
                raise ValueError(f"model acceptance field is required: {field}")
        self.initialize()
        with self._connect() as connection:
            existing = connection.execute(
                "SELECT report_json FROM model_acceptance_runs WHERE run_id=?", (run_id,)
            ).fetchone()
            serialized = json.dumps(report, ensure_ascii=False, sort_keys=True)
            if existing:
                if existing["report_json"] != serialized:
                    raise ValueError("run_id already exists with different output")
                return False
            connection.execute(
                "INSERT INTO model_acceptance_runs VALUES (?, ?, ?, ?, ?, ?)",
                (
                    run_id,
                    report["candidate_model_id"],
                    report["baseline_model_id"],
                    report["status"],
                    report["promotion"],
                    serialized,
                ),
            )
        return True

    def get(self, run_id: str) -> dict[str, Any] | None:
        self.initialize()
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM model_acceptance_runs WHERE run_id=?", (run_id,)).fetchone()
        if not row:
            return None
        result = dict(row)
        result["report"] = json.loads(str(result.pop("report_json")))
        return result
