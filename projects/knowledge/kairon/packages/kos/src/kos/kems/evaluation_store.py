"""SQLite persistence for redaction-verified KEMS datasets and evaluations."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from .evaluation import EvaluationManifest, EvaluationRun


class EvaluationStore:
    """Persist only dataset metadata, labels, and redacted source references."""

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)

    def _connect(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS datasets (
                    dataset_id TEXT NOT NULL,
                    dataset_version TEXT NOT NULL,
                    schema_version TEXT NOT NULL,
                    redaction_status TEXT NOT NULL,
                    sample_count INTEGER NOT NULL,
                    PRIMARY KEY (dataset_id, dataset_version)
                );
                CREATE TABLE IF NOT EXISTS samples (
                    sample_id TEXT PRIMARY KEY,
                    dataset_id TEXT NOT NULL,
                    dataset_version TEXT NOT NULL,
                    source_sha256 TEXT NOT NULL,
                    source_ref TEXT NOT NULL,
                    scenario_id TEXT NOT NULL,
                    split TEXT NOT NULL,
                    annotation_status TEXT NOT NULL,
                    labels_json TEXT NOT NULL,
                    annotation_version TEXT NOT NULL,
                    FOREIGN KEY (dataset_id, dataset_version)
                        REFERENCES datasets(dataset_id, dataset_version)
                );
                CREATE TABLE IF NOT EXISTS evaluation_runs (
                    run_id TEXT PRIMARY KEY,
                    dataset_id TEXT NOT NULL,
                    dataset_version TEXT NOT NULL,
                    model_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    accuracy REAL NOT NULL,
                    report_json TEXT NOT NULL
                );
                """
            )

    def register_manifest(self, manifest: EvaluationManifest) -> bool:
        """Register a verified manifest; return False for an exact replay."""
        for sample in manifest.samples:
            if not sample.source_ref.startswith("vault://redacted/"):
                raise ValueError("evaluation samples must reference redacted vault material")
        self.initialize()
        with self._connect() as connection:
            existing = connection.execute(
                "SELECT sample_count, redaction_status FROM datasets WHERE dataset_id=? AND dataset_version=?",
                (manifest.dataset_id, manifest.dataset_version),
            ).fetchone()
            if existing:
                if existing["sample_count"] != len(manifest.samples) or existing["redaction_status"] != "verified":
                    raise ValueError("dataset version already exists with different metadata")
                return False
            connection.execute(
                "INSERT INTO datasets VALUES (?, ?, ?, ?, ?)",
                (
                    manifest.dataset_id,
                    manifest.dataset_version,
                    manifest.schema_version,
                    manifest.redaction_status,
                    len(manifest.samples),
                ),
            )
            for sample in manifest.samples:
                connection.execute(
                    "INSERT INTO samples VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        sample.sample_id,
                        manifest.dataset_id,
                        manifest.dataset_version,
                        sample.source_sha256,
                        sample.source_ref,
                        sample.scenario_id,
                        sample.split,
                        sample.annotation_status,
                        json.dumps(dict(sample.labels), ensure_ascii=False, sort_keys=True),
                        sample.annotation_version,
                    ),
                )
        return True

    def record_run(self, run_id: str, run: EvaluationRun) -> None:
        self.initialize()
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO evaluation_runs VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_id) DO UPDATE SET status=excluded.status,
                    accuracy=excluded.accuracy, report_json=excluded.report_json""",
                (
                    run_id,
                    run.dataset_id,
                    run.dataset_version,
                    run.model_id,
                    run.status,
                    run.accuracy,
                    json.dumps(run.to_dict(), ensure_ascii=False, sort_keys=True),
                ),
            )

    def sample_count(self, dataset_id: str, dataset_version: str) -> int:
        self.initialize()
        with self._connect() as connection:
            row = connection.execute(
                "SELECT sample_count FROM datasets WHERE dataset_id=? AND dataset_version=?",
                (dataset_id, dataset_version),
            ).fetchone()
        return int(row["sample_count"]) if row else 0

    def get_run(self, run_id: str) -> dict[str, object] | None:
        self.initialize()
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM evaluation_runs WHERE run_id=?", (run_id,)).fetchone()
        if not row:
            return None
        result = dict(row)
        result["report"] = json.loads(str(result.pop("report_json")))
        return result
