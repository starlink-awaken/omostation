"""Durable OCR quality reports and immutable human-review records."""

from __future__ import annotations

import json
import re
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .ocr_quality import OCRQualityReport

_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class OCRQualityStore:
    """Persist OCR quality metadata without persisting OCR document bodies."""

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
                CREATE TABLE IF NOT EXISTS ocr_runs (
                    run_id TEXT PRIMARY KEY,
                    document_id TEXT NOT NULL,
                    source_sha256 TEXT NOT NULL,
                    engine TEXT NOT NULL,
                    model_version TEXT NOT NULL,
                    quality_status TEXT NOT NULL,
                    review_status TEXT NOT NULL,
                    report_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS ocr_corrections (
                    correction_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    corrected_sha256 TEXT NOT NULL,
                    correction_ref TEXT NOT NULL,
                    annotator TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (run_id) REFERENCES ocr_runs(run_id)
                );
                CREATE INDEX IF NOT EXISTS idx_ocr_review_queue
                    ON ocr_runs(review_status, created_at);
                """
            )
        self.db_path.chmod(0o600)

    def record_report(self, report: OCRQualityReport, *, source_sha256: str) -> bool:
        """Record a report; return False for an exact idempotent replay."""
        if not _SHA256.fullmatch(source_sha256):
            raise ValueError("source_sha256 must be a lowercase SHA-256 hex digest")
        self.initialize()
        report_json = json.dumps(report.to_dict(), ensure_ascii=False, sort_keys=True)
        review_status = "pending" if report.status in {"review", "reject"} else "not_required"
        with self._connect() as connection:
            existing = connection.execute(
                "SELECT source_sha256, report_json FROM ocr_runs WHERE run_id=?",
                (report.run_id,),
            ).fetchone()
            if existing:
                if existing["source_sha256"] != source_sha256 or existing["report_json"] != report_json:
                    raise ValueError("OCR run already exists with different immutable content")
                return False
            connection.execute(
                """INSERT INTO ocr_runs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    report.run_id,
                    report.document_id,
                    source_sha256,
                    report.engine,
                    report.model_version,
                    report.status,
                    review_status,
                    report_json,
                    datetime.now(UTC).isoformat(),
                ),
            )
        return True

    def review_queue(self, *, limit: int = 100) -> list[dict[str, Any]]:
        if limit < 1:
            raise ValueError("limit must be positive")
        self.initialize()
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT run_id, document_id, source_sha256, engine, model_version,
                          quality_status, review_status, created_at
                     FROM ocr_runs
                    WHERE review_status='pending'
                    ORDER BY created_at, run_id
                    LIMIT ?""",
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def record_correction(
        self,
        run_id: str,
        *,
        corrected_sha256: str,
        correction_ref: str,
        annotator: str,
    ) -> int:
        """Append a correction audit record; never mutate the OCR report."""
        if not _SHA256.fullmatch(corrected_sha256):
            raise ValueError("corrected_sha256 must be a lowercase SHA-256 hex digest")
        if not correction_ref.strip() or not annotator.strip():
            raise ValueError("correction_ref and annotator are required")
        self.initialize()
        with self._connect() as connection:
            if not connection.execute("SELECT 1 FROM ocr_runs WHERE run_id=?", (run_id,)).fetchone():
                raise KeyError(f"unknown OCR run: {run_id}")
            cursor = connection.execute(
                """INSERT INTO ocr_corrections
                   (run_id, corrected_sha256, correction_ref, annotator, created_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (run_id, corrected_sha256, correction_ref, annotator, datetime.now(UTC).isoformat()),
            )
            connection.execute("UPDATE ocr_runs SET review_status='corrected' WHERE run_id=?", (run_id,))
        return int(cursor.lastrowid)  # type: ignore[reportArgumentType]

    def get_report(self, run_id: str) -> dict[str, Any] | None:
        self.initialize()
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM ocr_runs WHERE run_id=?", (run_id,)).fetchone()
        if row is None:
            return None
        result = dict(row)
        result["report"] = json.loads(str(result.pop("report_json")))
        return result

    def can_admit(self, run_id: str) -> bool:
        report = self.get_report(run_id)
        return bool(report and report["quality_status"] == "pass")
