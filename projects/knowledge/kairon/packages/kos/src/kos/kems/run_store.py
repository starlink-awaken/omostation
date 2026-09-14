"""Durable SQLite store for KEMS source manifests and pipeline runs."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from .pipeline import PipelineRun, SourceManifest, StepRun


class RunStore:
    """Persist run checkpoints so a connector can resume without duplicating data."""

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)

    def _connect(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS source_manifests (
                    source_id TEXT PRIMARY KEY,
                    source_type TEXT NOT NULL,
                    source_uri TEXT NOT NULL,
                    content_sha256 TEXT NOT NULL,
                    domain TEXT NOT NULL,
                    sensitivity TEXT NOT NULL,
                    redaction_status TEXT NOT NULL,
                    connector_version TEXT NOT NULL,
                    captured_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS pipeline_runs (
                    run_id TEXT PRIMARY KEY,
                    pipeline_id TEXT NOT NULL,
                    source_ids TEXT NOT NULL,
                    status TEXT NOT NULL,
                    error_count INTEGER NOT NULL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS pipeline_steps (
                    run_id TEXT NOT NULL REFERENCES pipeline_runs(run_id) ON DELETE CASCADE,
                    step_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    started_at TEXT,
                    finished_at TEXT,
                    output_sha256 TEXT,
                    error_code TEXT,
                    PRIMARY KEY (run_id, step_id)
                );
                """
            )

    def register_source(self, source: SourceManifest) -> bool:
        """Register a source; return False for an exact replay and reject hash drift."""
        self.initialize()
        with self._connect() as connection:
            existing = connection.execute(
                "SELECT content_sha256 FROM source_manifests WHERE source_id = ?", (source.source_id,)
            ).fetchone()
            if existing:
                if existing["content_sha256"] != source.content_sha256:
                    raise ValueError(f"source_id {source.source_id} changed content_sha256")
                return False
            connection.execute(
                "INSERT INTO source_manifests VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    source.source_id,
                    source.source_type,
                    source.source_uri,
                    source.content_sha256,
                    source.domain,
                    source.sensitivity,
                    source.redaction_status,
                    source.connector_version,
                    source.captured_at,
                ),
            )
        return True

    def create_run(self, run: PipelineRun) -> None:
        self.initialize()
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO pipeline_runs VALUES (?, ?, ?, ?, ?)",
                (run.run_id, run.pipeline_id, json.dumps(run.source_ids), run.status, run.error_count),
            )

    def record_step(self, run_id: str, step: StepRun) -> None:
        self.initialize()
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO pipeline_steps VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_id, step_id) DO UPDATE SET status=excluded.status,
                    started_at=excluded.started_at, finished_at=excluded.finished_at,
                    output_sha256=excluded.output_sha256, error_code=excluded.error_code""",
                (
                    run_id,
                    step.step_id,
                    step.status,
                    step.started_at,
                    step.finished_at,
                    step.output_sha256,
                    step.error_code,
                ),
            )

    def save_run(self, run: PipelineRun) -> None:
        self.initialize()
        with self._connect() as connection:
            connection.execute(
                "UPDATE pipeline_runs SET status = ?, error_count = ?, source_ids = ? WHERE run_id = ?",
                (run.status, run.error_count, json.dumps(run.source_ids), run.run_id),
            )
        for step in run.steps:
            self.record_step(run.run_id, step)

    def get_run(self, run_id: str) -> PipelineRun | None:
        self.initialize()
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM pipeline_runs WHERE run_id = ?", (run_id,)).fetchone()
            if not row:
                return None
            steps = connection.execute(
                "SELECT * FROM pipeline_steps WHERE run_id = ? ORDER BY step_id", (run_id,)
            ).fetchall()
        return PipelineRun(
            run_id=row["run_id"],
            pipeline_id=row["pipeline_id"],
            source_ids=tuple(json.loads(row["source_ids"])),
            steps=[
                StepRun(
                    step_id=step["step_id"],
                    status=step["status"],
                    started_at=step["started_at"],
                    finished_at=step["finished_at"],
                    output_sha256=step["output_sha256"],
                    error_code=step["error_code"],
                )
                for step in steps
            ],
            status=row["status"],
            error_count=row["error_count"],
        )
