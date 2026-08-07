"""omo_adjudication.py — AdjudicationRecorded 事件与裁决存储 (BET-Y1Q1-T4-01).

结果面: 系统第一次能记录"人类接受了什么、改了什么".
守 ADR-0372: 决策日志入 bos://memory/mos/*.
关联: decision_outcome.decision_id (do-NNNN).

存储: .omo/_delivery/outcomes/adjudications.jsonl (append-only).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .omo_io import AppendOnlyLog, fcntl_lock
from .omo_paths import DELIVERY_DIR

OUTCOMES_DIR = DELIVERY_DIR / "outcomes"
ADJUDICATIONS_LOG = OUTCOMES_DIR / "adjudications.jsonl"
ADJUDICATION_SCHEMA = "adjudication/v1"
VALID_VERDICTS = frozenset({"accepted", "modified", "rejected"})


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _log() -> AppendOnlyLog:
    OUTCOMES_DIR.mkdir(parents=True, exist_ok=True)
    return AppendOnlyLog(
        path=ADJUDICATIONS_LOG,
        lock=fcntl_lock(ADJUDICATIONS_LOG.with_suffix(".lock")),
    )


@dataclass
class AdjudicationRecord:
    """人类裁决记录 — 关联回 decision_outcome.decision_id."""

    id: str
    decision_id: str
    verdict: str
    adjudicated_at: str = field(default_factory=_utc_now)
    edit_diff: str = ""
    time_spent_seconds: float = 0.0
    adjudicator: str = ""
    notes: str = ""
    schema_version: str = ADJUDICATION_SCHEMA


class AdjudicationStore:
    """裁决存储 — append-only JSONL + 查询."""

    def __init__(self, log: AppendOnlyLog | None = None) -> None:
        self._log = log or _log()
        self._counter: int | None = None

    def _next_id(self) -> str:
        records = self._log.read_all()
        n = len(records) + 1
        return f"adj-{n:04d}"

    def record(
        self,
        *,
        decision_id: str,
        verdict: str,
        edit_diff: str = "",
        time_spent_seconds: float = 0.0,
        adjudicator: str = "",
        notes: str = "",
    ) -> str:
        """记录一条裁决, 返回 adjudication id.

        Args:
            decision_id: 关联的 decision_outcome.id (do-NNNN).
            verdict: accepted | modified | rejected.
            edit_diff: 人类修改的 diff (modified 时建议填).
            time_spent_seconds: 审阅耗时.
            adjudicator: 裁决人标识.
            notes: 自由文本备注.
        """
        if verdict not in VALID_VERDICTS:
            raise ValueError(
                f"verdict must be one of {sorted(VALID_VERDICTS)}, got {verdict!r}"
            )
        adj_id = self._next_id()
        record = AdjudicationRecord(
            id=adj_id,
            decision_id=decision_id,
            verdict=verdict,
            edit_diff=edit_diff,
            time_spent_seconds=time_spent_seconds,
            adjudicator=adjudicator,
            notes=notes,
        )
        self._log.append(asdict(record), sort_keys=True)
        return adj_id

    def query(
        self,
        *,
        decision_id: str | None = None,
        verdict: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """查询裁决记录."""
        records = self._log.read_all()
        if decision_id:
            records = [r for r in records if r.get("decision_id") == decision_id]
        if verdict:
            records = [r for r in records if r.get("verdict") == verdict]
        return records[-limit:]

    def stats(self) -> dict[str, int]:
        """裁决统计 — 按 verdict 计数."""
        records = self._log.read_all()
        counts: dict[str, int] = {"total": len(records)}
        for v in sorted(VALID_VERDICTS):
            counts[v] = sum(1 for r in records if r.get("verdict") == v)
        return counts


__all__ = [
    "ADJUDICATION_SCHEMA",
    "ADJUDICATIONS_LOG",
    "AdjudicationRecord",
    "AdjudicationStore",
    "OUTCOMES_DIR",
    "VALID_VERDICTS",
]
